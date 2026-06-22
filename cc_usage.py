#!/usr/bin/env python3
"""Claude Code token-spend charts for the profile README.

  parse  -> reads ~/.claude/projects/**/*.jsonl, writes data/usage_<machine>.csv
  svg    -> merges every data/usage_*.csv, writes claude-spend-chart{,-mobile}.svg

The per-machine CSV is the unit of merge: run `parse` on each computer, commit its
data/usage_<machine>.csv, then `svg` re-merges them all. Timestamps bucket by UTC
date so machines in different timezones line up. SVG style matches the sibling
charts in this repo (Snowflake palette, animated top bar, dark #0D1117).

NOTE: this chart can only refresh from a machine with local Claude transcripts —
CI has no access to ~/.claude, so unlike the repo-derived charts it is not
auto-updated by a GitHub Action. Re-run locally to refresh.

# ponytail: prices are a static per-MTok table — edit when Anthropic pricing
# changes; cache-creation billed at the 5m rate (1.25x input), which is what
# Claude Code uses ~always.
"""
import csv, glob, json, os, re, sys, socket
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CLAUDE_DIR = os.path.expanduser("~/.claude/projects")

# $ per 1M tokens: (input, output, cache_write_5m, cache_read). Matched by substring.
PRICES = {
    "opus":   (15.0, 75.0, 18.75, 1.50),
    "sonnet": (3.0,  15.0, 3.75,  0.30),
    "haiku":  (1.0,  5.0,  1.25,  0.10),
    "fable":  (3.0,  15.0, 3.75,  0.30),  # ponytail: no public price yet — sonnet-tier; fix when known
}

def family(model):
    m = (model or "").lower()
    for k in PRICES:
        if k in m:
            return k
    return "other"

# ---------- parse ----------
def parse(machine):
    files = glob.glob(os.path.join(CLAUDE_DIR, "**", "*.jsonl"), recursive=True)
    print(f"parsing {len(files)} transcripts...", file=sys.stderr)
    agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0.0])  # msgs,in,out,cc,cr,cost
    seen, unpriced = set(), set()
    for i, path in enumerate(files):
        if i % 300 == 0:
            print(f"  {i}/{len(files)}", file=sys.stderr)
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"assistant"' not in line or '"usage"' not in line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if o.get("type") != "assistant":
                    continue
                msg = o.get("message", {}); u = msg.get("usage")
                if not u:
                    continue
                key = f"{msg.get('id')}:{o.get('requestId')}"
                if key in seen:
                    continue
                seen.add(key)
                date = (o.get("timestamp") or "")[:10]
                if not date:
                    continue
                fam = family(msg.get("model"))
                p = PRICES.get(fam)
                if p is None:
                    unpriced.add(msg.get("model")); p = (0.0, 0.0, 0.0, 0.0)
                inp = u.get("input_tokens", 0) or 0
                out = u.get("output_tokens", 0) or 0
                cc = u.get("cache_creation_input_tokens", 0) or 0
                cr = u.get("cache_read_input_tokens", 0) or 0
                r = agg[(date, fam)]
                r[0] += 1; r[1] += inp; r[2] += out; r[3] += cc; r[4] += cr
                r[5] += inp/1e6*p[0] + out/1e6*p[1] + cc/1e6*p[2] + cr/1e6*p[3]
    os.makedirs(DATA, exist_ok=True)
    out_path = os.path.join(DATA, f"usage_{machine}.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "model_family", "messages", "input_tokens",
                    "output_tokens", "cache_creation_tokens", "cache_read_tokens", "cost_usd"])
        for k in sorted(agg):
            r = agg[k]; w.writerow([k[0], k[1], r[0], r[1], r[2], r[3], r[4], f"{r[5]:.4f}"])
    print(f"wrote {out_path}: {len(agg)} rows, ${sum(r[5] for r in agg.values()):,.2f}", file=sys.stderr)
    if unpriced:
        print(f"  unpriced (counted $0, non-Claude): {sorted(unpriced)}", file=sys.stderr)

# ---------- svg ----------
def money(v):
    return f"${v/1000:.1f}k" if v >= 1000 else f"${v:.0f}"

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

TOPGRAD = ('<linearGradient id="topgrad" x1="0" x2="1" y1="0" y2="0">'
    '<stop offset="0%" stop-color="#29B5E8"><animate attributeName="stop-color" values="#29B5E8;#7B42BC;#3FCF8E;#29B5E8" dur="30s" repeatCount="indefinite"/></stop>'
    '<stop offset="50%" stop-color="#7B42BC"><animate attributeName="stop-color" values="#7B42BC;#3FCF8E;#29B5E8;#7B42BC" dur="30s" repeatCount="indefinite"/></stop>'
    '<stop offset="100%" stop-color="#3FCF8E"><animate attributeName="stop-color" values="#3FCF8E;#29B5E8;#7B42BC;#3FCF8E" dur="30s" repeatCount="indefinite"/></stop></linearGradient>')
CGRAD = '<linearGradient id="cgrad" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#29B5E8"/><stop offset="100%" stop-color="#1A5F8E"/></linearGradient>'

def render(dims, title, subtitle_parts, bars, footer, label_every=1):
    """bars: list of (xlabel, value, value_display). subtitle_parts: list of (text, is_accent)."""
    W, H = dims["W"], dims["H"]
    left, right = dims["left"], dims["right"]
    base_y, top_y, lab_y = dims["base_y"], dims["top_y"], dims["lab_y"]
    ts, tsz, sub_y, sub_sz = dims["title_y"], dims["title_sz"], dims["sub_y"], dims["sub_sz"]
    n = len(bars)
    area = W - left - right
    step = area / max(n, 1)
    barw = min(48, step * 0.72)
    maxv = max((b[1] for b in bars), default=1) or 1
    span = base_y - top_y
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Inter,system-ui,sans-serif">']
    out.append(f"<defs>{CGRAD}{TOPGRAD}</defs>")
    out.append(f'<rect width="{W}" height="{H}" fill="#0D1117" rx="12"/>')
    out.append(f'<rect x="0" y="0" width="{W}" height="4" fill="url(#topgrad)" rx="12"/>')
    out.append(f'<text x="{left}" y="{ts}" fill="#29B5E8" font-size="{tsz}" font-weight="700">{esc(title)}</text>')
    sub = [f'<text x="{left}" y="{sub_y}" font-size="{sub_sz}" fill="#C9D1D9">']
    for txt, accent in subtitle_parts:
        sub.append(f'<tspan fill="{"#29B5E8" if accent else "#8B949E"}"{" font-weight=\"700\"" if accent else ""}>{esc(txt)}</tspan>')
    sub.append("</text>")
    out.append("".join(sub))
    for i, (xlab, val, disp) in enumerate(bars):
        cx = left + step * i + step / 2
        h = max(2, val / maxv * span)
        y = base_y - h
        x = cx - barw / 2
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{barw:.1f}" height="{h:.1f}" rx="3" fill="url(#cgrad)"/>')
        out.append(f'<text x="{cx:.1f}" y="{y-5:.1f}" fill="#FFFFFF" font-size="11" text-anchor="middle" font-weight="600">{esc(disp)}</text>')
        if i % label_every == 0:
            out.append(f'<text x="{cx:.1f}" y="{lab_y}" fill="#8B949E" font-size="11" text-anchor="middle">{esc(xlab)}</text>')
    out.append(f'<line x1="{left-6}" y1="{base_y}" x2="{W-right}" y2="{base_y}" stroke="#30363D" stroke-width="1"/>')
    out.append(f'<text x="{W-right}" y="{H-14}" fill="#6E7681" font-size="9" text-anchor="end">{esc(footer)}</text>')
    out.append("</svg>")
    return "\n".join(out)

def svg():
    files = sorted(glob.glob(os.path.join(DATA, "usage_*.csv")))
    if not files:
        sys.exit("no data/usage_*.csv — run `parse` first")
    machines = [re.sub(r"^usage_|\.csv$", "", os.path.basename(f)) for f in files]
    cost_by_day, tok_by_day = defaultdict(float), defaultdict(int)
    for f in files:
        for row in csv.DictReader(open(f)):
            cost_by_day[row["date"]] += float(row["cost_usd"])
            tok_by_day[row["date"]] += (int(row["input_tokens"]) + int(row["output_tokens"])
                + int(row["cache_creation_tokens"]) + int(row["cache_read_tokens"]))
    days = sorted(cost_by_day)
    # L12M: last 12 calendar months ending this month (matches the sibling charts).
    now = datetime.now()
    months = []
    y, mo = now.year, now.month
    for _ in range(12):
        months.append(f"{y:04d}-{mo:02d}")
        mo -= 1
        if mo == 0:
            mo = 12; y -= 1
    months.reverse()
    cost_by_mo = defaultdict(float)
    tok_by_mo = defaultdict(int)
    for d in days:
        cost_by_mo[d[:7]] += cost_by_day[d]
        tok_by_mo[d[:7]] += tok_by_day[d]
    bars = [(datetime.strptime(m, "%Y-%m").strftime("%b"), cost_by_mo.get(m, 0.0),
             money(cost_by_mo[m]) if cost_by_mo.get(m) else "") for m in months]
    grand = sum(cost_by_mo.get(m, 0.0) for m in months)
    toks = sum(tok_by_mo.get(m, 0) for m in months)
    avg = grand / 12
    peak = max((cost_by_mo.get(m, 0.0) for m in months), default=0)
    title = "Claude Code Spend Per Month"

    sub = [(f"${grand:,.2f}", True), (" total · ", False),
           (money(avg), True), ("/mo avg · ", False),
           (money(peak), True), (" peak · ", False),
           (f"{toks/1e9:.1f}B", True), (" tokens", False)]
    today = now.strftime("%Y-%m-%d")
    footer = f"L12M · {len(machines)} machine{'s' if len(machines)!=1 else ''} · {today}"

    desk = dict(W=880, H=452, left=40, right=24, base_y=396, top_y=120, lab_y=414,
                title_y=44, title_sz=22, sub_y=76, sub_sz=13)
    mob = dict(W=440, H=338, left=28, right=18, base_y=288, top_y=104, lab_y=304,
               title_y=36, title_sz=17, sub_y=62, sub_sz=11)
    le_desk = max(1, len(bars) // 16)
    le_mob = max(1, len(bars) // 7)
    open(os.path.join(HERE, "claude-spend-chart.svg"), "w").write(
        render(desk, title, sub, bars, footer, le_desk))
    open(os.path.join(HERE, "claude-spend-chart-mobile.svg"), "w").write(
        render(mob, title, sub, bars, footer, le_mob))
    print(f"wrote claude-spend-chart.svg (+mobile): ${grand:,.2f}, {toks/1e9:.1f}B tokens, "
          f"{len(machines)} machine(s), {days[0]}->{days[-1]}", file=sys.stderr)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "parse":
        machine = (sys.argv[sys.argv.index("--machine")+1] if "--machine" in sys.argv
                   else re.sub(r"[^a-z0-9-]", "-", socket.gethostname().split(".")[0].lower()))
        parse(machine)
    elif cmd == "svg":
        svg()
    else:
        sys.exit("usage: cc_usage.py {parse [--machine NAME] | svg}")
