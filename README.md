# roam-hub

**The place a machine leaves another machine working.** POST a spec, walk away,
get a webhook.

A hosted autonomous-agent runtime, agent-first: the customers are agents
(Claude Code sessions, roam instances, CI jobs), not humans. One MFL/machin
binary + SQLite on the hub; stock [roam](https://github.com/javimosch/roam)
binaries as pull-based workers. Model calls are metered through the hub
(platform keys, exact token counts, central budgets, real kill switch); runs
are billed per-use via [peage](https://peage.intrane.fr).

- Start here: [`llms.txt`](llms.txt) (agents) · [`docs/VISION.md`](docs/VISION.md) (direction)
- Current milestone: [`docs/M0.md`](docs/M0.md)
- Design bible: agent-friendly CLI/API principles (versioned JSON, typed errors,
  semantic exit codes, stdout=data/stderr=progress, no prompts, no internal retries)

## Build

```sh
./build.sh          # machin encode src/*.src → build/server.mfl → ./roam-hub
./roam-hub serve 8810
```

## Layout

```
src/*.src     hub modules (≤500 LOC each) composed by machin encode
cli/          rhub — the thin client CLI
docs/         VISION.md (north star) · M0.md (current slice plan)
llms.txt      the front door for agents
```

No web UI exists and none is planned.
