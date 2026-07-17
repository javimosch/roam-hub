# Vision — machin-agents

**Last updated:** 2026-07-17
**Status:** Active — M0 underway

> **Agent-facing north star.** Read this before touching the repo. Like machin's
> `NORTH-STAR-*.md` files, this records direction so the next session knows which
> gap is worth driving and which is a dead end. Tiers below are ideas, not promises.

## North star

**The place a machine leaves another machine working.** POST a spec, walk away,
get a webhook. machin-agents is a hosted autonomous-agent runtime whose
customers are themselves agents (Claude Code sessions, roam instances, CI jobs)
— never humans clicking a dashboard.

The lineage: multi-assistant/Supergato's own VISION.md names its biggest gap —
"the Agent tier does not exist": no trigger model, no persistent runtime, no
outbound reporting, no autonomous safety budgets. Every one of those five gaps
is *naturally agent-first*. We build only that tier, and nothing below it.

## The bet

- **Customers are machines.** No chat UI, no widget, no human dashboard — the
  "dashboard" is `maa runs list --json`. This is set in stone (same rule as
  machin core: agent-first positioning, no human-DX tooling).
- **Pull-based execution.** Workers (roam binaries) poll the hub for due runs.
  The hub never SSHes into customer boxes. Fragile prod machines stay safe.
- **Platform model keys, metered through the hub.** Workers hold no LLM keys —
  every model call proxies through the hub, which forwards with its own key,
  counts exact tokens, and enforces the budget centrally. This buys, for free:
  exact metering (no trusting worker-reported usage), a real kill switch
  (kill a run = the proxy starves its loop within one turn), and hard budget
  cut-off mid-run. The cost: every LLM call hops through the hub. Acceptable —
  autonomous runs have nobody waiting on latency. **Deliberate trade.**
- **peage is the billing rail.** Per run: `token_cost × margin + flat run fee`,
  charged as a peage merchant. Insolvent tenant → triggers simply don't fire,
  with a `payment_required` event in the journal. No invoices, no Stripe UI here.

## Architecture (one paragraph)

One MFL binary (`machin-agents`), SQLite, fronted by Traefik at
`agents.intrane.fr` (hotify). Modules under `src/*.src`, composed by
`machin encode` — **max 500 LOC per file, no exceptions**. Workers are stock
roam binaries running `roam --worker <hub-url> --token maa_...` — roam already
has the engine (LLM tool-loop, workdir sandbox, gated shell, goal-verify,
deny-budget); the worker mode only adds poll → execute → report.

```
agent spec ──POST /v1/agents──▶ hub ──cron tick──▶ run queued
                                 ▲                      │
      worker polls GET /v1/work ─┘                      ▼
      worker executes, LLM calls ──▶ POST /v1/llm (metered proxy)
      worker streams  ──▶ POST /v1/run/events (journal)
      worker finishes ──▶ POST /v1/run/done ──▶ peage charge ──▶ webhook out
```

## The autonomy ladder (inverted)

Multi-assistant climbs chatbot → copilot → agent and never reaches the top.
We *start* at the top and the ladder runs the other way — how much a run may do:

| Rung | What it may do | Status |
|---|---|---|
| **Report** | Read-only runs: check, summarize, notify | M0 |
| **Act** | Gated side effects via roam's existing shell gate + deny-budget | M1 |
| **Extend** | Agent edits its own spec / schedules follow-up runs | far, maybe never |

"Earn autonomy" survives from the Supergato playbook: an agent is promoted a
rung only after its journal proves it reliable.

## Bible compliance (AGENTS_FRIENDLY_TOOLS.md)

The multi-assistant doc `docs/AGENTS_FRIENDLY_TOOLS.md` is the design bible:

- Every endpoint returns versioned JSON: `{"v":"1", ...}`.
- Errors are typed objects: `{type, code, recoverable, retry_after, suggestions}`.
- Semantic exit codes in the `maa` CLI: 0 ok, 80–89 input, 90–99 resource/state,
  100–109 external/transient, 110–119 internal bug.
- stdout = data, stderr = progress. No colors when not a TTY. No prompts, ever.
- The hub does not retry outbound calls on the customer's behalf — it reports
  typed failure and lets the calling agent decide.
- `llms.txt` is the front door; `GET /v1/guide` is the in-band capability doc.

## Roadmap (dogfood order)

Grown by building real things — same loop as machin. Each item is driven by a
real consumer, starting with our own boxes.

1. **M0 — the loop, end to end** (see `docs/M0.md`). First customer: the
   **rbm21 sentinel** — a nightly health/disk/service check on the fragile prod
   box, reporting via webhook → WhatsApp bridge. Exercises cron trigger, worker
   poll, metered proxy, journal, peage charge, webhook-out in one slice.
   Trigger model in M0 is `every_secs` intervals, not full cron syntax — honest
   simplification, upgrade when a real agent needs calendar semantics.
2. **M1 — Act rung**: side-effecting runs through roam's shell gate; deny-budget
   and pause-on-uncertainty surfaced as first-class run states (`needs_human`),
   escalation via roam-panel (approve/deny from the phone).
3. **M2 — webhook-inbound triggers**: an external event (mail, form, alert)
   fires a run. Deferred from M0 because it adds auth surface.
4. **M3 — multi-worker routing**: labels on workers (`host=rbm21`, `has=docker`),
   specs pin or select. Only when there are ≥2 real workers.

## What NOT to build (dead ends)

- **Any human UI.** No chat box, no Vue, no dashboard. If a human wants to look,
  they ask their agent.
- **RAG / vector search.** Multi-assistant's heaviest subsystem; nothing in the
  autonomous tier needs it. Revisit only if a dogfood agent hits the wall.
- **MCP gateway, sessions, HITL streaming.** Copilot-tier machinery — the tier
  we deliberately don't have.
- **Push-based execution** (hub SSHes into workers). Breaks the fragile-box rule.
- **BYOK model keys.** Metering through the hub *is* the product's spine; a BYOK
  side door would fork billing, budgets, and the kill switch into two paths.
- **Internal retry loops.** The bible forbids it; typed errors out, callers decide.

## Method

Build a real thing, hit the wall, fill it in, ship, record. Every capability is
driven by a real agent needing it — the rbm21 sentinel first, grepapi's GTM loop
next. When a gap is filled, update this file and `docs/M0.md`'s successor.
