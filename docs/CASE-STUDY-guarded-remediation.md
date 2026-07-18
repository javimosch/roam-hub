# Case study — guarded remediation: the outage a phone tap fixed

**Date:** 2026-07-18 · **Stack:** [perrus-cli](https://github.com/javimosch/perrus-cli)
(monitoring) → roam-hub (control plane) → roam worker (execution) → roam-panel /
`rhub` (human verdicts) · **Billing:** peage, actual model cost

The claim this demonstrates: **an agent can hold operational responsibility for a
server — diagnose outages, propose fixes, and act — while a human stays in the loop
for exactly one tap, and every step is journaled, budgeted, and billed per run.**

## The setup

- `demo-victim.service` on dk1: a deliberately fragile HTTP service, `Restart=no` —
  the monitoring + agent loop is its only safety net.
- perrus-cli monitors it every 15 s. perrus gained **webhook alerting** for this
  (down-transition → one JSON POST; a ~120-line notifier — the loop's only new code
  outside roam-hub itself).
- The alert URL is a roam-hub **webhook trigger** in `inject` mode, owned by a
  dedicated `dk1-ops` tenant whose worker runs *on dk1* with
  `--allow-shell --confirm`. (Tenant = routing domain: one tenant per box means a
  box's alerts are always executed by that box's worker — no label scheduler needed.)
- The agent spec (`incident-responder`, claude-haiku via the metered proxy):
  diagnose read-only first, restart only the alerted service if that's the obvious
  fix, verify recovery, report one line. Budget: €0.10/run.

## The drill (timestamps real)

```
08:34:01  sudo systemctl stop demo-victim          (the "outage")
08:34:12  perrus fires: {"source":"perrus","event":"down","endpoint":"demo-victim",...}
          → hub queues a run, the alert JSON injected into the agent's goal
08:34:2x  dk1 worker claims; agent runs systemctl status / journalctl (read-only)
08:35:xx  agent proposes: sudo systemctl restart demo-victim
          → roam's gate PARKS it → hub journals needs_human → park email sent
08:36:xx  rhub approve <run>   (or the one-tap email button — same decision channel)
          agent restarts the service, verifies is-active + HTTP 200
          finish: "demo-victim service was inactive; restarted successfully;
                   endpoint http://127.0.0.1:8123 now responding with HTTP 200"
          billed 3¢ (actual metered cost ×1.3 + 1¢), receipt in the journal,
          report webhook delivered
```

Total human involvement: one approval. Total cost: three cents.

## The unplanned second act (the safety rails, live)

When the new perrus webhooks went live, they immediately fired for endpoints that
were *already* down elsewhere on the network — including gitea on a **different
box**. The responder investigated, found no such unit locally, and eventually
proposed `sudo systemctl restart gitea` on the wrong machine. What happened next is
the entire safety model firing in sequence, unscripted:

1. **Reclaim** — a worker restart had killed the first attempt mid-run; the hub's
   staleness pass reclaimed the run and a fresh worker re-claimed it.
2. **The gate** — the wrong-box restart parked instead of executing.
3. **Human deny** — `rhub deny`; the agent adapted and kept investigating.
4. **Budget cut-off** — at €0.10 of metered spend the proxy refused the next model
   call and the run halted.
5. **Honest accounting** — billed 15¢ for what it actually consumed, receipt
   journaled, failure reported to the owner's webhook. Silence was never an outcome.

A bad alert cost fifteen cents and zero damage. That is the pitch.

## Why this needs roam-hub (and not a cron + a script)

A restart script can't diagnose an unfamiliar failure, and a fully-trusted agent
shouldn't hold root on your prod box. The hub's specific contributions: the
**trigger** (monitoring speaks HTTP, not cron), the **metered proxy** (the agent
thinks on platform keys, within a hard budget, killable in one turn), the
**traveling confirm-gate** (the park reaches a phone, the verdict reaches the
worker), and the **journal** (every incident is an auditable, billable artifact).

## Run it yourself

Everything here is MIT: [roam](https://github.com/javimosch/roam) ·
[roam-panel](https://github.com/javimosch/roam-panel) ·
[roam-hub](https://github.com/javimosch/roam-hub) ·
[perrus-cli](https://github.com/javimosch/perrus-cli). Use the hosted hub
(`https://hub.roam.intrane.fr/llms.txt`) or self-host the binary with your own
keys — the loop is the same.
