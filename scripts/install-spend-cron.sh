#!/bin/bash
# Install the daily Claude-spend-chart refresh as a launchd agent on this Mac.
# Run once per machine:  bash scripts/install-spend-cron.sh
set -euo pipefail
LABEL="dev.mitchzink.ccspend"
SRC="$(cd "$(dirname "$0")" && pwd)/${LABEL}.plist"
DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"

chmod +x "$(dirname "$0")/refresh-spend.sh"
mkdir -p "$HOME/Library/LaunchAgents"
sed "s#__HOME__#${HOME}#g" "$SRC" > "$DEST"

# reload cleanly (ignore "not loaded" on first run)
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "installed $DEST"
echo "runs daily 18:00 -> $HOME/Library/Logs/ccspend.log"
echo "run now:  launchctl kickstart -k gui/$(id -u)/${LABEL}"
echo "remove:   launchctl bootout gui/$(id -u)/${LABEL} && rm $DEST"
