#!/usr/bin/env bash
# Build roam-hub: mint canonical .mfl from framework + app modules, compile
# to one native binary. Point at a local machin build with MACHIN=/path/to/machin.
set -euo pipefail
cd "$(dirname "$0")"
MACHIN="${MACHIN:-machin}"
mkdir -p build

"$MACHIN" encode \
  framework/machweb.src \
  src/types.src \
  src/util.src \
  src/db.src \
  src/handlers_agents.src \
  src/handlers_runs.src \
  src/trigger.src \
  src/proxy.src \
  src/billing.src \
  src/report.src \
  src/server.src \
  src/entry.src \
  > build/server.mfl

"$MACHIN" build build/server.mfl -o roam-hub
echo "built ./roam-hub  —  run: ./roam-hub serve 8810"
