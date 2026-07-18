# Case study — guarded remediation: outage to verified recovery in 61 seconds, one approval

**Date:** 2026-07-18 · **Stack:** [perrus-cli](https://github.com/javimosch/perrus-cli)
(monitoring) → roam-hub (control plane) → roam worker (execution) →
[roam-panel](https://github.com/javimosch/roam-panel) (human verdicts) ·
**Billing:** peage, actual metered model cost

The claim this demonstrates: **an agent can hold operational responsibility for a
server — detect an outage, diagnose it on the box, propose the fix, and apply it —
while a human stays in the loop for exactly one approval, and every step is
journaled, budgeted, and billed per run.**

## What is staged and what is real

This is a **drill**, and it says so. Being precise about the boundary:

- **Staged:** the outage (`sudo systemctl stop demo-victim`) and the victim itself —
  a sacrificial HTTP service (`Restart=no`) created so the loop is its only safety
  net. The approval in this run was written directly into roam-panel's decision
  table — the **same row the one-tap email button writes**; the email tap itself
  (real phone, real inbox) was separately live-verified the day before on the same
  gate machinery.
- **Real:** everything else. Production perrus monitoring on a production server,
  a real webhook, a real LLM diagnosing over a real shell, a genuine parked
  `systemctl restart`, a real restart, a verified recovery, and a real 3¢ charge
  with a receipt.

## The run (timestamps from the journal)

```
09:27:23  sudo systemctl stop demo-victim            (the staged outage)
09:27:35~ perrus detects (15s interval) and fires:
          {"source":"perrus","event":"down","endpoint":"demo-victim",...}
          → roam-hub queues a run, alert JSON injected into the agent's goal
09:27:36  dk1 worker claims (10s poll)
09:27:38  diagnosis begins: systemctl status / journalctl, read-only
09:27:41  agent proposes: sudo systemctl restart demo-victim → the gate PARKS it
09:28:11  approval lands via roam-panel's decision channel
09:28:13  restart executed; agent verifies is-active + HTTP 200
09:28:15  finish: "demo-victim service was down (killed with SIGTERM); restarted;
                   service now active and responding on http://127.0.0.1:8123"
09:28:15  billed 3¢ (actual metered cost ×1.3 + 1¢), receipt in the journal
09:28:16  report webhook delivered
```

Kill to verified recovery: **61 seconds**, ~30 of which were the approval sitting
parked. Total human involvement: one approve. The agent's diagnosis independently
identified *how* the service died (SIGTERM) from the journal — it wasn't told.

## The failure case (same day, unscripted)

An honest loop has to be judged on its bad day. When the perrus webhooks first went
live they fired for endpoints that were already down elsewhere on the network —
including gitea, which runs on a **different machine**. The responder investigated
locally, found no such unit, and eventually proposed `sudo systemctl restart gitea`
on the wrong box. That run **failed, safely, at every layer built for it**:

- the gate parked the wrong-box restart instead of executing it;
- the human verdict was **deny**; the agent adapted and kept investigating;
- at €0.10 of metered spend the proxy refused the next model call and the run
  halted (`budget_exhausted`);
- it was billed 15¢ for what it actually consumed, and the failure was **reported
  to the owner's webhook** — silence is never an outcome.

Cost of a bad alert reaching a confused agent: fifteen cents, zero commands
executed on the box, full audit trail. We're publishing the failure because the
product's claim is not "the agent is always right" — it's "the agent can't hurt
you when it's wrong."

(Separately, that incident also exercised run reclaim: a worker restart killed the
first attempt mid-run and the hub's staleness pass re-queued it automatically.)

## Why this needs roam-hub (and not a cron + a restart script)

A restart script can't diagnose an unfamiliar failure, and a fully-trusted agent
shouldn't hold root on your box. The hub's specific contributions: the **trigger**
(monitoring speaks HTTP, not cron), the **metered proxy** (the agent thinks on
platform keys, inside a hard budget, killable in one turn), the **traveling
confirm-gate** (the park reaches a human anywhere — email one-tap, panel, or CLI —
and the verdict reaches the worker), and the **journal** (every incident is an
auditable, billable artifact).

## Run it yourself

Everything here is MIT: [roam](https://github.com/javimosch/roam) ·
[roam-panel](https://github.com/javimosch/roam-panel) ·
[roam-hub](https://github.com/javimosch/roam-hub) ·
[perrus-cli](https://github.com/javimosch/perrus-cli). Use the hosted hub
(`https://hub.roam.intrane.fr/llms.txt`) or self-host with your own keys — the
loop is identical. The full setup is: one perrus `webhooks:` block, one
`rhub create` with the alert URL as a webhook trigger, one worker with
`--allow-shell --confirm` on the box you're protecting.
