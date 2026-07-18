#!/usr/bin/env python3
"""deploy-worker — SUPERSEDED reference implementation.

The self-deploy pipeline now runs as a first-class kind:script spec (see
self-deploy.steps.json next to this file) executed by a stock roam worker.
This python worker remains as documentation of the engine-agnostic protocol.

Original notes: a DETERMINISTIC roam-hub worker. No LLM anywhere.

Proof that the worker protocol is engine-agnostic: this ~150-line script speaks
the same wire as a roam agent — polls GET /v1/work, journals steps via
/v1/run/events, PARKS before the service restart via /v1/run/needs-human and
polls /v1/run/decision for the human verdict (one-tap email / rhub approve),
reports the outcome with /v1/run/done {result}. The hub meters nothing (no
model calls), so a green deploy bills the flat run fee only.

Pipeline per run: fetch → drift-check → build → smoke → [gate] → swap →
restart → health-verify → rollback-on-failure.

Env: RHUB_URL, RHUB_WORKER_TOKEN, DEPLOY_REPO (git checkout), DEPLOY_BIN,
DEPLOY_SERVICE, DEPLOY_HEALTH (url), MACHIN (compiler path), SMOKE_PORT.
"""
import json, os, subprocess, time, urllib.request, urllib.error

HUB = os.environ.get("RHUB_URL", "https://hub.roam.intrane.fr")
WTOK = os.environ["RHUB_WORKER_TOKEN"]
REPO = os.environ.get("DEPLOY_REPO", "/opt/roam-hub/src")
BIN = os.environ.get("DEPLOY_BIN", "/opt/roam-hub/roam-hub")
SERVICE = os.environ.get("DEPLOY_SERVICE", "roam-hub")
HEALTH = os.environ.get("DEPLOY_HEALTH", "http://127.0.0.1:8810/_health")
MACHIN = os.environ.get("MACHIN", "/opt/roam-hub/machin")
SMOKE_PORT = os.environ.get("SMOKE_PORT", "8890")
SHA_FILE = os.environ.get("DEPLOY_SHA_FILE", "/opt/roam-hub/DEPLOYED_SHA")
POLL = int(os.environ.get("POLL_SECS", "10"))
GATE_TIMEOUT = int(os.environ.get("GATE_TIMEOUT_SECS", "1800"))


def api(method, path, body=None, retries=1):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(HUB + path, method=method,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Authorization": "Bearer " + WTOK, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return 204, {}
            return e.code, {}
        except Exception:
            if attempt == retries - 1:
                return 0, {}
            time.sleep(3)


def sh(cmd, cwd=None, timeout=600):
    p = subprocess.run(cmd, shell=True, cwd=cwd, timeout=timeout,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout[-1500:]


def ev(rid, kind, data):
    api("POST", "/v1/run/events", {"run_id": rid, "kind": kind, "data": json.dumps(data)}, retries=3)


def done(rid, reason, result):
    api("POST", "/v1/run/done", {"run_id": rid, "exit_reason": reason, "result": result}, retries=10)
    print(f"run {rid[:8]}: {reason} — {result}", flush=True)


def step(rid, name, cmd, cwd=None, timeout=600):
    rc, out = sh(cmd, cwd=cwd, timeout=timeout)
    ev(rid, "step", {"name": name, "ok": rc == 0, "exit": rc, "tail": out[-400:]})
    return rc, out


def health_ok(url, tries=15, sleep_s=2):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(sleep_s)
    return False


def deploy(rid):
    # 1. fetch + drift check
    rc, out = step(rid, "fetch", "git fetch -q origin main && git rev-parse origin/main", cwd=REPO)
    if rc != 0:
        return done(rid, "error", "fetch failed: " + out[-200:])
    new_sha = out.strip().splitlines()[-1][:12]
    cur_sha = open(SHA_FILE).read().strip()[:12] if os.path.exists(SHA_FILE) else "none"
    if new_sha == cur_sha:
        return done(rid, "completed", f"in sync at {new_sha} — nothing to deploy")
    # 2. checkout + build + smoke
    if step(rid, "checkout", "git reset -q --hard origin/main", cwd=REPO)[0] != 0:
        return done(rid, "error", "checkout failed")
    rc, out = step(rid, "build", f"MACHIN={MACHIN} bash build.sh", cwd=REPO, timeout=900)
    if rc != 0:
        return done(rid, "error", f"build failed at {new_sha}: " + out[-200:])
    rc, out = step(rid, "smoke",
        f"RHUB_DB=/tmp/deploy-smoke.db ./roam-hub serve {SMOKE_PORT} & SP=$!; sleep 2; "
        f"curl -sf localhost:{SMOKE_PORT}/_health; RC=$?; kill $SP 2>/dev/null; rm -f /tmp/deploy-smoke.db; exit $RC",
        cwd=REPO)
    if rc != 0:
        return done(rid, "error", f"smoke test failed at {new_sha}")
    # 3. the GATE — park for a human verdict before touching the live service
    api("POST", "/v1/run/needs-human",
        {"run_id": rid, "command": f"sudo systemctl restart {SERVICE} (deploy {cur_sha} -> {new_sha})"}, retries=3)
    print(f"run {rid[:8]}: parked for approval ({cur_sha} -> {new_sha})", flush=True)
    deadline = time.time() + GATE_TIMEOUT
    verdict = ""
    while time.time() < deadline:
        st, d = api("GET", f"/v1/run/decision?run={rid}")
        verdict = d.get("decision", "")
        if verdict:
            break
        time.sleep(2)
    if verdict == "stop":
        return print(f"run {rid[:8]}: killed during gate", flush=True)
    if verdict != "approve":
        return done(rid, "completed", f"deploy to {new_sha} {'denied' if verdict == 'deny' else 'timed out at the gate'} — still on {cur_sha}")
    ev(rid, "approved", {"deploy": new_sha})
    # 4. swap + restart + verify (the hub restarts under us — done() retries cover it)
    step(rid, "backup", f"cp {BIN} {BIN}.prev")
    # mv, not cp: rename() is atomic and legal on a busy running binary ("Text
    # file busy" bit us on cp). Then PROVE the swap took before claiming it.
    rc, _ = step(rid, "swap", f"install -m755 {REPO}/roam-hub {BIN}.new && mv -f {BIN}.new {BIN}")
    if rc != 0:
        return done(rid, "error", f"swap failed — still on {cur_sha}, service untouched")
    rc, _ = step(rid, "verify-binary", f"cmp -s {REPO}/roam-hub {BIN}")
    if rc != 0:
        return done(rid, "error", f"swap verification failed — aborting before restart, still on {cur_sha}")
    step(rid, "restart", f"sudo systemctl restart {SERVICE}")
    if health_ok(HEALTH):
        open(SHA_FILE, "w").write(new_sha)
        return done(rid, "completed", f"deployed {new_sha} — {SERVICE} healthy")
    # 5. rollback
    step(rid, "rollback", f"cp {BIN}.prev {BIN} && sudo systemctl restart {SERVICE}")
    ok = health_ok(HEALTH)
    return done(rid, "error",
        f"deploy {new_sha} FAILED health check — rolled back to {cur_sha} ({'healthy' if ok else 'STILL UNHEALTHY'})")


def main():
    print(f"deploy-worker: polling {HUB}/v1/work every {POLL}s (deterministic, no LLM)", flush=True)
    while True:
        st, work = api("GET", "/v1/work")
        if st == 200 and work.get("run_id"):
            rid = work["run_id"]
            print(f"claimed run {rid}", flush=True)
            try:
                deploy(rid)
            except Exception as e:
                done(rid, "error", f"deploy worker crashed: {e}")
        time.sleep(POLL)


if __name__ == "__main__":
    main()
