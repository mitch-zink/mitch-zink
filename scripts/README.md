# Claude-spend chart automation

The `claude-spend-chart.svg` on the profile is built from `../cc_usage.py`, which
parses local Claude Code transcripts (`~/.claude/projects`). CI can't read those,
so each machine refreshes its own slice on a schedule and pushes; `svg` re-merges
every `data/usage_<machine>.csv` so the chart reflects all machines.

| file | what |
|---|---|
| `refresh-spend.sh` | pull → `parse` (this machine) → `svg` (merge all) → commit+push if changed |
| `dev.mitchzink.ccspend.plist` | macOS launchd agent, runs the above daily 18:00 |
| `install-spend-cron.sh` | installs the launchd agent on a Mac |

## Add a machine

**macOS**
```bash
bash scripts/install-spend-cron.sh            # label = hostname
bash scripts/install-spend-cron.sh macbook-pro-2   # explicit label (see warning)
```
⚠️ **Unique label per machine.** The label is the CSV bucket
(`data/usage_<label>.csv`). Two Macs with the same computer name both derive the
same hostname label and would clobber one CSV — pass an explicit label as the
first arg on any machine that would collide.

⚠️ macOS TCC blocks background agents from `~/Documents` and `~/.claude`, so the
unattended run fails with `Operation not permitted` until you grant **Full Disk
Access** to `/bin/bash` (System Settings → Privacy & Security → Full Disk Access).
Until then, refresh manually anytime (an interactive shell already has access):
```bash
CCSPEND_MACHINE=macbook-pro-2 bash scripts/refresh-spend.sh   # match the install label
```

The installer also sets `cleanupPeriodDays: 3650` in `~/.claude/settings.json` so
Claude Code stops pruning transcripts at 30 days — otherwise spend history older
than ~30 days is deleted before it can be parsed.

**Linux (e.g. the home server / devbox)** — no TCC, just cron:
```bash
git clone https://github.com/mitch-zink/mitch-zink.git ~/Documents/GitHub/mitch-zink
( crontab -l 2>/dev/null; echo "30 6 * * * /bin/bash $HOME/Documents/GitHub/mitch-zink/scripts/refresh-spend.sh >> $HOME/.ccspend.log 2>&1" ) | crontab -
```

Each machine names its CSV by hostname; override with `CCSPEND_MACHINE` (the Mac
launchd sets `macbook-pro`). One label per machine = no double-counting.

Note: the figure is **API-equivalent list price** (per `cc_usage.py` price table),
not subscription cost. Prices verified against platform.claude.com/docs 2026-06-21.
