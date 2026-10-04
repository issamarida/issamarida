"""Draw a pen-plotter style SVG of a GitHub user's last year: a 6-month
weekly contribution chart, language bars and a few facts.

    GITHUB_TOKEN=... python3 assets/stats.py issamarida > assets/stats.svg
"""
import datetime as dt
import json
import math
import os
import sys
import urllib.request
from collections import Counter

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      commitContributionsByRepository(maxRepositories: 100) { contributions { totalCount } repository { primaryLanguage { name } } }
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""

W, H = 720, 560


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    body = json.load(urllib.request.urlopen(req))
    if "errors" in body:
        sys.exit(body["errors"])
    return body["data"]["user"]


def streaks(days):
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        longest = max(longest, run)
    current = 0
    for d in reversed(days):
        if d["contributionCount"]:
            current += 1
        elif current or d is not days[-1]:  # today may still be empty
            break
    return longest, current


def nice_step(peak, ticks=4):
    raw = peak / ticks
    mag = 10 ** math.floor(math.log10(raw)) if raw >= 1 else 1
    return next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)


def timeseries(days, x0, y0, x1, y1):
    """Weekly totals as a filled green area chart with a month on each x tick."""
    first, last = (dt.date.fromisoformat(days[i]["date"]) for i in (0, -1))
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    totals = [sum(d["contributionCount"] for d in w) for w in weeks]
    step = nice_step(max(totals, default=0) or 1)
    top = step * math.ceil((max(totals, default=0) or 1) / step)
    sx = lambda d: x0 + (x1 - x0) * (d - first).days / max((last - first).days, 1)
    sy = lambda v: y1 - (y1 - y0) * v / top
    pts = [(sx(dt.date.fromisoformat(w[-1]["date"])), sy(t)) for w, t in zip(weeks, totals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in [(x0, sy(totals[0]))] + pts)
    out = []
    v = 0
    while v <= top:  # y axis: gridline, tick and label per step
        y = sy(v)
        if v:
            out.append(f'<line class="grid" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}"/>')
        out.append(f'<line class="axis" x1="{x0 - 4}" y1="{y:.1f}" x2="{x0}" y2="{y:.1f}"/>')
        out.append(f'<text class="dim ax" x="{x0 - 8}" y="{y + 3.5:.1f}" text-anchor="end">{v:g}</text>')
        v += step
    out += [f'<polygon class="area" points="{x0},{y1} {line} {pts[-1][0]:.1f},{y1}"/>',
            f'<polyline class="trend" points="{line}"/>',
            f'<line class="axis" x1="{x0}" y1="{y0 - 6}" x2="{x0}" y2="{y1}"/>',
            f'<line class="axis" x1="{x0}" y1="{y1}" x2="{x1 + 6}" y2="{y1}"/>',
            f'<text class="dim ax" transform="translate({x0 - 44} {(y0 + y1) / 2}) rotate(-90)" '
            'text-anchor="middle">contributions / week</text>']
    m = dt.date(first.year + first.month // 12, first.month % 12 + 1, 1)
    while m <= last:  # x axis: a tick and label at the start of each month
        x = sx(m)
        out.append(f'<line class="axis" x1="{x:.1f}" y1="{y1}" x2="{x:.1f}" y2="{y1 + 4}"/>')
        out.append(f'<text class="dim ax" x="{x:.1f}" y="{y1 + 16}" text-anchor="middle">{m:%b}</text>'.lower())
        m = dt.date(m.year + m.month // 12, m.month % 12 + 1, 1)
    return out


def render(user):
    cc = user["contributionsCollection"]
    weeks = [w["contributionDays"] for w in cc["contributionCalendar"]["weeks"]]
    days = [d for w in weeks for d in w]
    longest, current = streaks(days)
    recent = days[-182:]  # roughly the last 6 months
    langs = Counter()
    for r in cc["commitContributionsByRepository"]:
        if r["repository"]["primaryLanguage"]:
            langs[r["repository"]["primaryLanguage"]["name"]] += r["contributions"]["totalCount"]

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
           "<style>",
           ":root{--ink:#1b1b1b;--pen:#d9480f;--green:#2da44e;--faint:#1b1b1b1f}",
           "@media (prefers-color-scheme:dark){:root{--ink:#e8e6e1;--pen:#ff8a4c;--green:#3fb950;--faint:#e8e6e11f}}",
           "text{font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:var(--ink)}",
           ".m{font-size:10px;letter-spacing:.12em;fill:var(--pen)}.b{font-size:16px}.dim{opacity:.55}",
           ".l{stroke:var(--pen);stroke-width:.8;fill:none}",
           ".hl{stroke:var(--ink);stroke-width:.45}.ax{font-size:10px}",
           ".grid{stroke:var(--faint);stroke-dasharray:2 3}.axis{stroke:var(--ink);stroke-width:.6;opacity:.5}",
           ".area{fill:url(#fade)}.trend{fill:none;stroke:var(--green);stroke-width:1.6;stroke-linejoin:round}",
           ".s0{stop-color:var(--green);stop-opacity:.55}.s1{stop-color:var(--green);stop-opacity:.04}",
           '</style><defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
           '<stop class="s0" offset="0"/><stop class="s1" offset="1"/></linearGradient></defs>']
    # plotter furniture, same as the cat
    out.append(f'<rect class="l" x="24" y="24" width="{W - 48}" height="{H - 48}" stroke-dasharray="2 4"/>')
    for x, y, dx, dy in [(16, 16, 1, 1), (W - 16, 16, -1, 1), (16, H - 16, 1, -1), (W - 16, H - 16, -1, -1)]:
        out.append(f'<path class="l" d="M{x} {y + 14 * dy}V{y}H{x + 14 * dx}"/>')
    out.append('<text class="m" x="44" y="52">contributions in the last 6 months</text>')
    out += timeseries(recent, 92, 84, 668, 300)

    # languages: hatched bars, a different pen angle per language
    total = sum(langs.values()) or 1
    out.append('<text class="m" x="44" y="380">top languages by commit</text>')
    for i, (name, size) in enumerate(langs.most_common(5)):
        y, frac = 398 + i * 24, size / total
        out.append(f'<pattern id="l{i}" width="3" height="3" patternUnits="userSpaceOnUse" '
                   f'patternTransform="rotate({-60 + 30 * i})"><line class="hl" x1="0" y1="0" x2="0" y2="3"/></pattern>')
        out.append(f'<text x="44" y="{y + 11}">{name.lower().replace("&", "&amp;")}</text>')
        out.append(f'<rect x="172" y="{y + 1}" width="{max(2, 150 * frac):.1f}" height="12" fill="url(#l{i})" '
                   'stroke="var(--ink)" stroke-width=".6"/>')
        out.append(f'<text class="dim" x="{180 + 150 * frac:.1f}" y="{y + 11}">{frac:.0%}</text>')

    facts = [
        (f'{sum(d["contributionCount"] for d in recent):,}', "contributions in the last 6 months"),
        (f"{longest}d", "longest streak"),
        (f"{current}d", "current streak"),
    ]
    out.append('<text class="m" x="380" y="380">facts</text>')
    for i, (big, small) in enumerate(facts):
        out.append(f'<text x="380" y="{411 + i * 22}"><tspan class="b">{big}</tspan>'
                   f'<tspan class="dim" dx="8" style="font-size:11px">{small}</tspan></text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    print(render(fetch(sys.argv[1], os.environ["GITHUB_TOKEN"])))
