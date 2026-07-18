# roam-hub

**The place a machine leaves another machine working.** POST a spec, walk away, get a webhook.

roam-hub is the hosted half of the [roam](https://github.com/javimosch/roam) stack — a
control plane that **schedules, meters, bills, and reports** autonomous agent runs. Your
agents (a Claude Code session, a CI job, another service) are the customers: they register
an agent spec over plain HTTP and get back a working, billed, observable autonomous agent.
No dashboard, no signup form — the API *is* the product.

```
             the roam family — one story in three binaries
┌─────────────┐      ┌────────────────┐      ┌─────────────────────────┐
│    roam     │      │   roam-panel   │      │        roam-hub         │
│ run it      │─────▶│ approve it     │◀────▶│ we schedule, meter,     │
│ yourself    │ park │ from your phone│      │ bill & report it        │
└─────────────┘      └────────────────┘      └─────────────────────────┘
   the engine          the human touchpoint      the cloud half (this repo)
```

Live instance: **https://hub.roam.intrane.fr** · agent front door: [`llms.txt`](llms.txt) · `GET /v1/guide`

## What a hosted run looks like

```bash
# 1. one-time: a tenant + tokens (attach a peage wallet for billing)
curl -s -X POST https://hub.roam.intrane.fr/v1/signup \
  -d '{"email":"you@example.com","peage_wallet":"pw_..."}'

# 2. register an agent spec — cron (every_secs) and/or webhook-triggered
curl -s -X POST https://hub.roam.intrane.fr/v1/agents -H "Authorization: Bearer rh_..." \
  -d '{"name":"sentinel","prompt":"Check disk and load; call finish with a one-line summary.",
       "every_secs":3600,"budget_microeur":100000,"report_url":"https://your.site/hook"}'
# -> {"id":"...","trigger_url":"https://hub.roam.intrane.fr/t/<id>/<secret>"}

# 3. walk away. Runs fire on schedule (or POST the trigger_url), a worker executes,
#    the report lands on your webhook, the run is billed per use via peage.
```

Every run leaves an append-only **journal** — `queued → claimed → llm_call(tokens, cost) →
done → billed(receipt) → reported` — readable at `GET /v1/run?id=`.

## The design in five decisions

1. **Pull-based workers.** Stock roam binaries run `roam worker --hub <url> --token rhw_...`
   and poll for due runs. The hub never reaches into your machines. The worker protocol is
   **engine-agnostic**: anything that polls `GET /v1/work` and speaks an anthropic- or
   openai-shaped wire format can be a worker — roam is the first engine, not a dependency.
2. **Workers hold no model keys.** Every LLM call proxies through the hub (`/v1/llm`, run id
   in an `x-roam-run` header), which forwards with its own key and counts exact tokens.
   That one choice buys exact metering, a hard mid-run **budget cut-off**, and a **kill
   switch** that starves a runaway loop within one turn.
3. **Billing is per run, on the actual cost.** The hub bills the upstream's real generation
   cost when the provider reports it (`cost_source:"actual"`), ×1.3 margin + €0.01 flat,
   charged to the tenant's [peage](https://peage.intrane.fr) wallet with the run id as the
   idempotency key. An insolvent tenant's triggers simply don't fire — recorded in the
   journal, never silent.
4. **Autonomy is gated.** Shell-enabled runs go through roam's confirm-gate: a destructive
   command parks the run (`needs_human` in the journal), the owner approves or denies —
   from the CLI (`rhub approve <run>`) or a one-tap email via
   [roam-panel](https://github.com/javimosch/roam-panel) — and the worker resumes. Kill,
   budget, and payment states are all first-class run statuses.
5. **Agent-first, forever.** Versioned JSON everywhere, typed errors
   (`{type, code, recoverable, suggestions}`), semantic exit codes in the CLI, no prompts,
   no colors, no internal retries — and **no human web UI, ever**. The human touchpoint is
   roam-panel; the dashboard is `rhub runs --json`.

## Self-hosting

One static MFL binary + SQLite. Needs the [machin](https://github.com/javimosch/machin)
compiler to build.

```bash
./build.sh                      # -> ./roam-hub  (machin encode + build)
RHUB_DB=hub.db \
RHUB_LLM_PROVIDER=openrouter RHUB_OPENROUTER_KEY=sk-or-... \
PEAGE_URL=https://peage.intrane.fr PEAGE_MERCHANT_KEY=pm_... \
./roam-hub serve 8810
```

Point a worker at it: `roam worker --hub http://your-host:8810 --token <rhw_...>`.
Without a peage merchant key the hub runs fine and journals `billing_skipped` — useful for
a keys-only private deployment.

## Layout

```
src/*.src     hub modules (≤500 LOC each, composed by machin encode)
cli/rhub.src  the thin client CLI (semantic exit codes 80–119)
docs/         VISION.md (north star + what we will NOT build) · M0.md (shipped milestone)
llms.txt      the front door for agents
```

## Status

M0–M2 shipped and live-proven end to end: scheduled + webhook triggers, metered
actual-cost billing over peage, shell runs with the traveling confirm-gate and one-tap
email approvals, kill switch, budget cut-off, webhook report-out. See `docs/VISION.md`
for direction and the deliberate dead-ends.

Built with [machin](https://github.com/javimosch/machin) — the whole stack is MFL.

## License

MIT
