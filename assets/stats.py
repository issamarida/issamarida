"""Draw a pen-plotter style SVG of a GitHub user's last 6 months: a
monthly contribution chart, language bars and a few facts.

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
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      commitContributionsByRepository(maxRepositories: 100) { contributions { totalCount } repository { primaryLanguage { name } } }
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""

W, H = 720, 560


def fetch(login, token, since):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login, "from": f"{since}T00:00:00Z",
                                              "to": dt.datetime.now(dt.timezone.utc).isoformat()}}).encode(),
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


def smooth(pts):
    """SVG path through pts as a monotone cubic curve, so it bends without overshooting."""
    n = len(pts)
    if n < 3:
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    d = [(pts[i + 1][1] - pts[i][1]) / (pts[i + 1][0] - pts[i][0]) for i in range(n - 1)]
    m = [d[0]] + [0 if d[i - 1] * d[i] <= 0 else (d[i - 1] + d[i]) / 2 for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):  # Fritsch-Carlson: clamp tangents to keep each segment monotone
        if d[i] == 0:
            m[i] = m[i + 1] = 0
        else:
            a, b = m[i] / d[i], m[i + 1] / d[i]
            if a * a + b * b > 9:
                t = 3 / math.hypot(a, b)
                m[i], m[i + 1] = t * a * d[i], t * b * d[i]
    path = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for (xa, ya), (xb, yb), ma, mb in zip(pts, pts[1:], m, m[1:]):
        h = (xb - xa) / 3
        path += f" C{xa + h:.1f},{ya + ma * h:.1f} {xb - h:.1f},{yb - mb * h:.1f} {xb:.1f},{yb:.1f}"
    return path


def timeseries(days, x0, y0, x1, y1):
    """Running total of contributions, checked on the 1st of each month and today."""
    starts = sorted({dt.date.fromisoformat(d["date"][:7] + "-01") for d in days})[-6:]
    days = [d for d in days if d["date"] >= starts[0].isoformat()]  # drop calendar padding
    last = dt.date.fromisoformat(days[-1]["date"])
    checks = starts + [last + dt.timedelta(1)] if last >= starts[-1] else starts
    totals = [sum(d["contributionCount"] for d in days if d["date"] < c.isoformat()) for c in checks]
    step = nice_step(max(totals) or 1)
    top = step * math.ceil((max(totals) or 1) / step)
    sx = lambda c: x0 + (x1 - x0) * (c - starts[0]).days / max((checks[-1] - starts[0]).days, 1)
    sy = lambda v: y1 - (y1 - y0) * v / top
    pts = [(sx(c), sy(t)) for c, t in zip(checks, totals)]
    line = smooth(pts)
    out = []
    v = 0
    while v <= top:  # y axis: gridline, tick and label per step
        y = sy(v)
        if v:
            out.append(f'<line class="grid" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}"/>')
        out.append(f'<line class="axis" x1="{x0 - 4}" y1="{y:.1f}" x2="{x0}" y2="{y:.1f}"/>')
        out.append(f'<text class="dim ax" x="{x0 - 8}" y="{y + 3.5:.1f}" text-anchor="end">{v:g}</text>')
        v += step
    out += [f'<path class="area" d="M{x0},{y1} L{line[1:]} L{pts[-1][0]:.1f},{y1}Z"/>',
            f'<path class="trend" d="{line}"/>',
            f'<line class="axis" x1="{x0}" y1="{y0 - 6}" x2="{x0}" y2="{y1}"/>',
            f'<line class="axis" x1="{x0}" y1="{y1}" x2="{x1 + 6}" y2="{y1}"/>',
            f'<text class="dim ax" transform="translate({x0 - 44} {(y0 + y1) / 2}) rotate(-90)" '
            'text-anchor="middle">total contributions</text>']
    for m in starts:  # x axis: the 1st of each month
        x = sx(m)
        out.append(f'<line class="axis" x1="{x:.1f}" y1="{y1}" x2="{x:.1f}" y2="{y1 + 4}"/>')
        out.append(f'<text class="dim ax" x="{x:.1f}" y="{y1 + 16}" text-anchor="middle">{m:%b 1}</text>'.lower())
    return out


def render(user):
    cc = user["contributionsCollection"]
    weeks = [w["contributionDays"] for w in cc["contributionCalendar"]["weeks"]]
    days = [d for w in weeks for d in w]
    longest, current = streaks(days)
    langs = Counter()
    for r in cc["commitContributionsByRepository"]:
        if r["repository"]["primaryLanguage"]:
            langs[r["repository"]["primaryLanguage"]["name"]] += r["contributions"]["totalCount"]

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
           "<style>",
           ":root{--ink:#1b1b1b;--pen:#d9480f;--green:#2da44e;--faint:#1b1b1b1f}",
           "@media (prefers-color-scheme:dark){:root{--ink:#e8e6e1;--pen:#ff8a4c;--green:#3fb950;--faint:#e8e6e11f}}",
           "text{font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:var(--ink)}",
           ".m{font-size:10px;letter-spacing:.12em;fill:var(--pen)}.b{font-size:20px}.lg{font-size:14px}.dim{opacity:.55}",
           ".l{stroke:var(--pen);stroke-width:.8;fill:none}",
           ".hl{stroke:var(--ink);stroke-width:.45}.ax{font-size:10px}",
           ".grid{stroke:var(--faint);stroke-dasharray:2 3}.axis{stroke:var(--ink);stroke-width:.6;opacity:.5}",
           ".area{fill:url(#fade)}.trend{fill:none;stroke:var(--green);stroke-width:1.6;stroke-linejoin:round}",
           ".s0{stop-color:var(--green);stop-opacity:.85}.s1{stop-color:var(--green);stop-opacity:.35}",
           '</style><defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
           '<stop class="s0" offset="0"/><stop class="s1" offset="1"/></linearGradient></defs>']
    # plotter furniture, same as the cat
    out.append(f'<rect class="l" x="24" y="24" width="{W - 48}" height="{H - 48}" stroke-dasharray="2 4"/>')
    for x, y, dx, dy in [(16, 16, 1, 1), (W - 16, 16, -1, 1), (16, H - 16, 1, -1), (W - 16, H - 16, -1, -1)]:
        out.append(f'<path class="l" d="M{x} {y + 14 * dy}V{y}H{x + 14 * dx}"/>')
    out.append('<text class="m" x="44" y="52">contributions in the last 6 months</text>')
    out += timeseries(days, 92, 84, 668, 300)

    # languages: hatched bars, a different pen angle per language
    total = sum(langs.values()) or 1
    out.append('<text class="m" x="44" y="380">top languages by commit</text>')
    for i, (name, size) in enumerate(langs.most_common(5)):
        y, frac = 396 + i * 28, size / total
        out.append(f'<pattern id="l{i}" width="3" height="3" patternUnits="userSpaceOnUse" '
                   f'patternTransform="rotate({-60 + 30 * i})"><line class="hl" x1="0" y1="0" x2="0" y2="3"/></pattern>')
        out.append(f'<text class="lg" x="44" y="{y + 12}">{name.lower().replace("&", "&amp;")}</text>')
        out.append(f'<rect x="196" y="{y}" width="{max(2, 110 * frac):.1f}" height="14" fill="url(#l{i})" '
                   'stroke="var(--ink)" stroke-width=".6"/>')
        out.append(f'<text class="dim lg" x="{204 + 110 * frac:.1f}" y="{y + 12}">{frac:.0%}</text>')

    facts = [
        (f'{sum(d["contributionCount"] for d in days):,}', "contributions in the last 6 months"),
        (f"{longest}d", "longest streak"),
        (f"{current}d", "current streak"),
    ]
    out.append('<text class="m" x="372" y="380">facts</text>')
    for i, (big, small) in enumerate(facts):
        out.append(f'<text x="372" y="{412 + i * 30}"><tspan class="b">{big}</tspan>'
                   f'<tspan class="dim" dx="8" style="font-size:13px">{small}</tspan></text>')
    out.append("</svg>")
    return "\n".join(out)


def six_months_ago(today):
    """The 1st of the month five months back, so the window holds six month starts."""
    y, m = divmod(today.year * 12 + today.month - 1 - 5, 12)
    return dt.date(y, m + 1, 1)


if __name__ == "__main__":
    print(render(fetch(sys.argv[1], os.environ["GITHUB_TOKEN"], six_months_ago(dt.date.today()))))
