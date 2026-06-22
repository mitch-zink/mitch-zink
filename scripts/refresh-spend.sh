#!/bin/bash
# Auto-refresh the Claude Code spend chart from THIS machine's local transcripts.
# Runs under a launchd agent (scripts/dev.mitchzink.ccspend.plist). `parse` needs
# local ~/.claude; `svg` merges every data/usage_*.csv so the chart reflects all
# machines that have pushed. Install on each computer with scripts/install-spend-cron.sh.
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REPO="$HOME/Documents/GitHub/mitch-zink"
cd "$REPO" || { echo "$(date '+%F %T') repo missing: $REPO"; exit 1; }

git pull --rebase --autostash origin main >/dev/null 2>&1 || { echo "$(date '+%F %T') pull failed"; exit 1; }
# Stable per-machine label (override with CCSPEND_MACHINE) so the same machine
# always writes the same data/usage_<label>.csv and never double-counts.
MACHINE="${CCSPEND_MACHINE:-$(hostname -s | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9-' '-' | sed 's/-*$//')}"
python3 cc_usage.py parse --machine "$MACHINE" || { echo "$(date '+%F %T') parse failed"; exit 1; }
python3 cc_usage.py svg   || { echo "$(date '+%F %T') svg failed"; exit 1; }

if git diff --quiet -- data/ claude-spend-chart.svg claude-spend-chart-mobile.svg; then
  echo "$(date '+%F %T') no change"
  exit 0
fi
git add data/ claude-spend-chart.svg claude-spend-chart-mobile.svg
git commit -m "chore: refresh claude-spend chart ($(hostname -s))" >/dev/null
if git push origin main >/dev/null 2>&1; then
  echo "$(date '+%F %T') pushed"
else
  echo "$(date '+%F %T') push failed"; exit 1
fi
