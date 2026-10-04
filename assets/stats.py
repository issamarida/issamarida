"""Draw a pen-plotter style SVG of a GitHub user's last year: a
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
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions totalPullRequestContributions totalIssueContributions
      commitContributionsByRepository(maxRepositories: 100) { contributions { totalCount } repository { primaryLanguage { name } } }
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount weekday } } }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount }
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


def timeseries(weeks, x0, y0, x1, y1):
    """Weekly totals as a filled green area chart with labelled axes."""
    totals = [sum(d["contributionCount"] for d in w) for w in weeks]
    step = nice_step(max(totals, default=0) or 1)
    top = step * math.ceil((max(totals, default=0) or 1) / step)
    dx = (x1 - x0) / max(len(totals) - 1, 1)
    sy = lambda v: y1 - (y1 - y0) * v / top
    pts = [(x0 + i * dx, sy(t)) for i, t in enumerate(totals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    out = []
    v = 0
    while v <= top:  # y axis: gridline, tick and label per step
        y = sy(v)
        if v:
            out.append(f'<line class="grid" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}"/>')
        out.append(f'<line class="axis" x1="{x0 - 4}" y1="{y:.1f}" x2="{x0}" y2="{y:.1f}"/>')
        out.append(f'<text class="dim ax" x="{x0 - 8}" y="{y + 3.5:.1f}" text-anchor="end">{v:g}</text>')
        v += step
    out += [f'<polygon class="area" points="{x0},{y1} {line} {x1},{y1}"/>',
            f'<polyline class="trend" points="{line}"/>',
            f'<line class="axis" x1="{x0}" y1="{y0 - 6}" x2="{x0}" y2="{y1}"/>',
            f'<line class="axis" x1="{x0}" y1="{y1}" x2="{x1 + 6}" y2="{y1}"/>',
            f'<text class="dim ax" transform="translate({x0 - 44} {(y0 + y1) / 2}) rotate(-90)" '
            'text-anchor="middle">contributions / week</text>']
    month = None
    for (x, _), w in zip(pts, weeks):  # x axis: tick and label where a month starts
        d = dt.date.fromisoformat(w[0]["date"])
        m = d.strftime("%b").lower()
        if month is not None and d.month != month:
            out.append(f'<line class="axis" x1="{x:.1f}" y1="{y1}" x2="{x:.1f}" y2="{y1 + 4}"/>')
            out.append(f'<text class="dim ax" x="{x:.1f}" y="{y1 + 16}" text-anchor="middle">{m}</text>')
        month = d.month
    peak = max(totals, default=0)
    if peak:
        px, py = pts[totals.index(peak)]
        out.append(f'<circle class="peak" cx="{px:.1f}" cy="{py:.1f}" r="3"/>')
        out.append(f'<text class="ax" x="{px - 7:.1f}" y="{py + 4:.1f}" text-anchor="end">best week · {peak}</text>')
    return out


def render(user):
    cc = user["contributionsCollection"]
    weeks = [w["contributionDays"] for w in cc["contributionCalendar"]["weeks"]]
    days = [d for w in weeks for d in w]
    longest, current = streaks(days)
    busiest = max(days, key=lambda d: d["contributionCount"])
    langs = Counter()
    for r in cc["commitContributionsByRepository"]:
        if r["repository"]["primaryLanguage"]:
            langs[r["repository"]["primaryLanguage"]["name"]] += r["contributions"]["totalCount"]
    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    busy_date = dt.date.fromisoformat(busiest["date"]).strftime("%b %d").lower()

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
           ".peak{fill:var(--green)}.s0{stop-color:var(--green);stop-opacity:.55}.s1{stop-color:var(--green);stop-opacity:.04}",
           '</style><defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
           '<stop class="s0" offset="0"/><stop class="s1" offset="1"/></linearGradient></defs>']
    # plotter furniture, same as the cat
    out.append(f'<rect class="l" x="24" y="24" width="{W - 48}" height="{H - 48}" stroke-dasharray="2 4"/>')
    for x, y, dx, dy in [(16, 16, 1, 1), (W - 16, 16, -1, 1), (16, H - 16, 1, -1), (W - 16, H - 16, -1, -1)]:
        out.append(f'<path class="l" d="M{x} {y + 14 * dy}V{y}H{x + 14 * dx}"/>')
    out.append('<text class="m" x="44" y="52">contributions in the last year</text>')
    out += timeseries(weeks, 92, 84, 668, 300)

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

    prs, issues = cc["totalPullRequestContributions"], cc["totalIssueContributions"]
    repos = user["repositories"]["totalCount"]
    # (value, label, worth showing?) so weak numbers drop out as the year changes
    facts = [
        (f'{cc["contributionCalendar"]["totalContributions"]:,}', "contributions this year", True),
        (f"{longest}d", "longest streak" + (f" · current {current}d" if current >= 3 else ""), longest >= 5),
        (str(busiest["contributionCount"]), f"on {busy_date}, my busiest day",
         busiest["contributionCount"] >= 10),
        (f'{cc["totalCommitContributions"]:,}', "commits" + "".join(
            f" · {n} {k}" for n, k in ((prs, "prs"), (issues, "issues")) if n >= 10), True),
        (str(repos), "public repos" + (f" · {stars} stars" if stars >= 10 else ""), repos >= 10),
        (str(stars), "stars earned", stars >= 10 and repos < 10),
    ]
    facts = [(big, small) for big, small, keep in facts if keep]
    out.append('<text class="m" x="380" y="380">facts</text>')
    for i, (big, small) in enumerate(facts):
        out.append(f'<text x="380" y="{411 + i * 22}"><tspan class="b">{big}</tspan>'
                   f'<tspan class="dim" dx="8" style="font-size:11px">{small}</tspan></text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    print(render(fetch(sys.argv[1], os.environ["GITHUB_TOKEN"])))
