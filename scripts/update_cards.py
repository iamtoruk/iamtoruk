#!/usr/bin/env python3
"""Nightly profile-card updater. Regenerates the four SVG cards from live
CodeBurn data (this machine) + GitHub stats, re-pins the README image URLs
to the new commit, and pushes. Publishes ONLY the aggregates rendered below."""
import html, json, re, subprocess, sys, os
from datetime import datetime, timezone

REPO = os.path.expanduser("~/Projects/iamtoruk")
ART = {n: open(os.path.join(REPO, "assets", f"art-{n}.txt")).read().rstrip("\n").split("\n")
       for n in ("identity", "codeburn", "eywa")}

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, check=True, **kw).stdout

def gh(path):
    return json.loads(run(["gh", "api", path]))

os.chdir(REPO)
subprocess.run(["git","pull","--rebase","-q","origin","main"],check=True)

# ---------- data ----------
month = json.loads(run(["codeburn", "report", "--period", "month", "--format", "json"]))
models = json.loads(run(["codeburn", "models", "--period", "month", "--format", "json"]))
mrows = models.get("models") if isinstance(models, dict) else models
ov = month.get("overview") or month
mcost = ov.get("cost", 0); mcalls = ov.get("calls", 0); mcache = ov.get("cacheHitPercent", 0)
prov = {}
for r in mrows: prov[r.get("provider", "?")] = prov.get(r.get("provider", "?"), 0) + (r.get("costUSD") or r.get("cost") or 0)
top3 = sorted(prov.items(), key=lambda kv: -kv[1])[:3]
proj = {"eywa": 0.0, "codeburn": 0.0}
for p in (month.get("projects") or []):
    n = (p.get("project") or p.get("name") or "").lower()
    for k in proj:
        if k in n: proj[k] += p.get("cost", 0)
daily = [(d.get("cost") or 0) for d in (month.get("daily") or [])][-14:] or [0]
peak = max(daily) or 1
spark = "".join("▁▂▃▄▅▆▇█"[min(7, int(v / peak * 7.99))] for v in daily)

user = gh("users/iamtoruk")
cbrepo = gh("repos/getagentseal/codeburn")
commits = gh("search/commits?q=author:iamtoruk").get("total_count", 0)
prs = gh("search/issues?q=author:iamtoruk+type:pr").get("total_count", 0)
prs_m = gh("search/issues?q=author:iamtoruk+type:pr+is:merged").get("total_count", 0)
created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
now = datetime.now(timezone.utc)
yrs = now.year - created.year - ((now.month, now.day) < (created.month, created.day))
mos = (now.month - created.month) % 12
uptime = f"{yrs} years, {mos} months"

# ---------- card generator ----------
A_FS, A_CW, A_LH = 5.6, 3.38, 6.1
D_FS, D_CW, D_LH = 12, 7.25, 20
DW = 58; PAD = 8
THEME = (".m{fill:#57606a;font-size:12px} .d{fill:#d0d7de;font-size:12px} .v{fill:#1f2328;font-size:12px}\n"
         "@media (prefers-color-scheme: dark){ .m{fill:#8b8f97} .d{fill:#33373e} .v{fill:#e8e6e1} }")
def esc(x): return html.escape(x, quote=False)

def card(fname, gid, title, art, rows, accent, grad, note=None):
    art_w = 82 * A_CW; art_h = len(art) * A_LH; data_x = PAD + art_w + 30
    n_rows = 1 + len(rows) + (1 if note else 0); inner_h = max(art_h, n_rows * D_LH)
    width = data_x + DW * D_CW + PAD; height = inner_h + 16
    ay = 8 + (inner_h - art_h) / 2; dy = 8 + (inner_h - n_rows * D_LH) / 2 + D_FS
    stops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in grad)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
         f'<defs><linearGradient id="{gid}" x1="0" y1="{ay:.0f}" x2="0" y2="{ay+art_h:.0f}" gradientUnits="userSpaceOnUse">{stops}</linearGradient></defs>',
         f'<style>text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre}}\n'
         f'.a{{fill:url(#{gid});font-size:{A_FS}px}} .t{{fill:{accent};font-size:{D_FS}px;font-weight:bold}}\n{THEME}</style>']
    y = ay
    for line in art:
        if line.strip(): o.append(f'<text x="{PAD}" y="{y:.1f}" class="a">{esc(line)}</text>')
        y += A_LH
    y = dy; hdr = title + " "
    o.append(f'<text x="{data_x}" y="{y:.1f}" class="t">{esc(hdr)}</text>'
             f'<text x="{data_x+len(hdr)*D_CW:.1f}" y="{y:.1f}" class="d">{"─"*(DW-len(hdr))}</text>'); y += D_LH
    for label, value in rows:
        lab = f" . {label}: "; dots = "." * max(2, DW - len(label) - len(value) - 6)
        x1 = data_x + len(lab) * D_CW; x2 = x1 + len(dots) * D_CW
        attr = f'fill="{accent}"' if any(c.isdigit() for c in value) else 'class="v"'
        o.append(f'<text x="{data_x}" y="{y:.1f}" class="m">{esc(lab)}</text>'
                 f'<text x="{x1:.1f}" y="{y:.1f}" class="d">{dots}</text>'
                 f'<text x="{x2:.1f}" y="{y:.1f}" {attr} font-size="{D_FS}">{esc(value)}</text>'); y += D_LH
    if note: o.append(f'<text x="{data_x}" y="{y:.1f}" class="m"> . {esc(note)}</text>')
    o.append("</svg>")
    open(os.path.join(REPO, "assets", fname), "w").write("\n".join(o))

card("card-identity.svg", "profileg", "iamtoruk@github", ART["identity"], [
    ("Name", "Resham"), ("Founder", "CodeBurn · Eywa · AgentSeal"), ("Location", "Germany"),
    ("Before", "7y embedded C++, self-driving cars"), ("Detour", "Web3"),
    ("Now", "breaking AI agents before someone else does"), ("Open.Source", "by default"),
    ("Languages", "TypeScript, Python, Swift, C++"), ("Philosophy", "Keep trying."),
    ("AI usage (API-equiv, this month)", f"${mcost:,.0f}"),
    ("Commits", f"{commits:,}"), ("PRs", f"{prs} · {prs_m} merged"), ("Followers", str(user["followers"])),
], "#7B8CFF", [("0%", "#7FD8FF"), ("50%", "#7B8CFF"), ("100%", "#B08BEB")])

card("card-codeburn.svg", "cbg", "codeburn@local", ART["codeburn"], [
    ("What", "AI agent usage & cost analytics"), ("Users", "150,000+"),
    ("Stars", f"{cbrepo['stargazers_count']:,}"), ("Forks", f"{cbrepo['forks_count']:,}"),
    ("Stack", "TS · Node · Swift · C++"), ("Privacy", "100% local"),
    ("AI spend this month", f"${proj['codeburn']:,.0f} API-equiv"),
], "#F0793B", [("0%", "#FFE08A"), ("35%", "#F0793B"), ("75%", "#E03A1A"), ("100%", "#8a1a0a")],
    note="(it tracks its own construction)")

card("card-eywa.svg", "eywag", "eywa@local", ART["eywa"], [
    ("What", "memory that survives the session"), ("Facts", "atomic, each with its verbatim source"),
    ("Graph", "entities linked, queryable"), ("Lifecycle", "new truth supersedes old"),
    ("Dreaming", "background consolidation"), ("Defense", "provenance beats poisoned memory"),
    ("Stack", "TypeScript · Python · MCP"), ("AI spend this month", f"${proj['eywa']:,.0f} API-equiv"),
    ("Status", "building · still in the forge"),
], "#3FBDB4", [("0%", "#7FE8C9"), ("60%", "#3FBDB4"), ("100%", "#1e7a74")])

# usage panel
PCOL = {"claude": "#F0793B", "codex": "#6BCB77", "kimicode": "#B08BEB", "grok": "#6BCB77"}
BARW = 26; width = 760
height = (1 + len(top3)) * D_LH + 2 * D_LH + 24
maxc = top3[0][1] or 1
o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height:.0f}" viewBox="0 0 {width} {height:.0f}">',
     f'<style>text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre;font-size:12px}}\n'
     f'.t{{fill:#F0793B;font-weight:bold}}\n{THEME}</style>']
y = 8 + D_FS; hdr = "ai.agents@month · top 3 "
o.append(f'<text x="{PAD}" y="{y}" class="t">{hdr}</text><text x="{PAD+len(hdr)*D_CW:.0f}" y="{y}" class="d">{"─"*(96-len(hdr))}</text>'); y += D_LH
for name, cost in top3:
    nb = max(1, round(cost / maxc * BARW)); bars = "█" * nb
    o.append(f'<text x="{PAD}" y="{y}" class="m"> {name:<10}</text>'
             f'<text x="{PAD+11*D_CW:.0f}" y="{y}" fill="{PCOL.get(name, "#8b8f97")}">{bars}</text>'
             f'<text x="{PAD+(11+BARW+2)*D_CW:.0f}" y="{y}" class="v">${cost:,.2f}</text>'); y += D_LH
y += 6
o.append(f'<text x="{PAD}" y="{y}" class="m"> last 14 days </text>'
         f'<text x="{PAD+14*D_CW:.0f}" y="{y}" fill="#F0793B" font-size="14">{spark}</text>'
         f'<text x="{PAD+(14+len(spark)+1)*7.9:.0f}" y="{y}" class="m"> peak ${peak:,.0f}/day</text>'); y += D_LH
o.append(f'<text x="{PAD}" y="{y}" class="m"> month </text>'
         f'<text x="{PAD+7*D_CW:.0f}" y="{y}" class="v">${mcost:,.0f} API-equiv · {mcalls:,} calls · </text>'
         f'<text x="{PAD+7*D_CW+len(f"${mcost:,.0f} API-equiv · {mcalls:,} calls · ")*D_CW:.0f}" y="{y}" fill="#6BCB77">{mcache}% cache hit</text>')
o.append("</svg>")
open(os.path.join(REPO, "assets", "card-usage.svg"), "w").write("\n".join(o))

# ---------- commit if changed, re-pin README ----------
if not subprocess.run(["git", "diff", "--quiet", "--", "assets"]).returncode:
    print("no changes"); sys.exit(0)
run(["git", "add", "assets"])
run(["git", "commit", "-q", "-m", "profile: nightly numbers refresh"])
run(["git", "push", "-q", "origin", "main"])
sha = run(["git", "rev-parse", "HEAD"]).strip()
rd = open("README.md").read()
rd2 = re.sub(r"(raw\.githubusercontent\.com/iamtoruk/iamtoruk/)[0-9a-f]{40}(/assets/)", rf"\g<1>{sha}\g<2>", rd)
rd2 = re.sub(r"GitHub-[\d,]+★", f"GitHub-{cbrepo['stargazers_count']:,}★", rd2)
if rd2 != rd:
    open("README.md", "w").write(rd2)
    run(["git", "commit", "-q", "-am", "profile: re-pin cards to fresh commit"])
    run(["git", "push", "-q", "origin", "main"])
print("updated to", sha[:8])
