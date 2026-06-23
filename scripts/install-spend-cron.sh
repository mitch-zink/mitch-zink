#!/bin/bash
# Install the daily Claude-spend-chart refresh as a launchd agent on this Mac.
# Run once per machine:  bash scripts/install-spend-cron.sh [machine-label]
#
# The machine label is the CSV bucket (data/usage_<label>.csv). It MUST be unique
# per machine — two Macs with the same computer name both derive the same hostname
# label and would clobber one CSV. Pass an explicit label as $1 on any machine that
# would otherwise collide (e.g. a second MacBook Pro):
#   bash scripts/install-spend-cron.sh macbook-pro-2
set -euo pipefail
LABEL="dev.mitchzink.ccspend"
SRC="$(cd "$(dirname "$0")" && pwd)/${LABEL}.plist"
DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"

# Stable per-machine bucket. Explicit arg wins; else hostname-normalized.
MACHINE="${1:-$(hostname -s | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9-' '-' | sed 's/-*$//')}"

# Stop Claude Code from pruning transcripts (default 30d) so spend history survives.
# Safe JSON merge — never touches/echoes any other key (settings.json holds secrets).
SETTINGS="$HOME/.claude/settings.json"
if [ -f "$SETTINGS" ]; then
  python3 - "$SETTINGS" <<'PY' || echo "warn: could not set cleanupPeriodDays (set it manually)"
import json, sys
p = sys.argv[1]
d = json.load(open(p))
if d.get("cleanupPeriodDays", 0) < 3650:
    d["cleanupPeriodDays"] = 3650
    json.dump(d, open(p, "w"), indent=2)
    print("set cleanupPeriodDays=3650 (transcripts no longer auto-pruned)")
else:
    print("cleanupPeriodDays already >= 3650")
PY
fi

chmod +x "$(dirname "$0")/refresh-spend.sh"
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s#__HOME__#${HOME}#g" -e "s#__MACHINE__#${MACHINE}#g" "$SRC" > "$DEST"
echo "machine label: ${MACHINE}  (CSV: data/usage_${MACHINE}.csv)"

# reload cleanly (ignore "not loaded" on first run)
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "installed $DEST"
echo "runs daily 18:00 -> $HOME/Library/Logs/ccspend.log"
echo "run now:  launchctl kickstart -k gui/$(id -u)/${LABEL}"
echo "remove:   launchctl bootout gui/$(id -u)/${LABEL} && rm $DEST"
