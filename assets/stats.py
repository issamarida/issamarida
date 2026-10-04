"""Draw a pen-plotter style SVG of a GitHub user's last year: an isometric
contribution skyline, language bars and a few facts.

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
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount weekday } } }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
    }
  }
}"""

W, H = 720, 560
WEEK, DAY = (9.4, -2.6), (-6.2, 5.6)  # screen offset of one step along each grid axis
WEEKDAYS = ["sundays", "mondays", "tuesdays", "wednesdays", "thursdays", "fridays", "saturdays"]


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


def poly(points, cls):
    return f'<polygon class="{cls}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in points)}"/>'


def skyline(weeks, x0, y0):
    peak = max((d["contributionCount"] for w in weeks for d in w), default=0) or 1
    at = lambda w, d, h=0: (x0 + w * WEEK[0] + d * DAY[0], y0 + w * WEEK[1] + d * DAY[1] - h)
    out = []
    # back to front: low weekday rows first, later weeks (further up the slope) first
    for d in range(7):
        for w in reversed(range(len(weeks))):
            day = next((x for x in weeks[w] if x["weekday"] == d), None)
            if day is None:
                continue
            c = day["contributionCount"]
            if not c:
                out.append(poly([at(w, d), at(w + 1, d), at(w + 1, d + 1), at(w, d + 1)], "g"))
                continue
            h = 4 + 72 * math.sqrt(c / peak)
            out.append(poly([at(w, d + 1), at(w + 1, d + 1), at(w + 1, d + 1, h), at(w, d + 1, h)], "s1"))
            out.append(poly([at(w, d), at(w, d + 1), at(w, d + 1, h), at(w, d, h)], "s2"))
            out.append(poly([at(w, d, h), at(w + 1, d, h), at(w + 1, d + 1, h), at(w, d + 1, h)],
                            "t" if c < peak * 0.6 else "t hot"))
    return out


def render(user, today):
    cc = user["contributionsCollection"]
    weeks = [w["contributionDays"] for w in cc["contributionCalendar"]["weeks"]]
    days = [d for w in weeks for d in w]
    longest, current = streaks(days)
    busiest = max(days, key=lambda d: d["contributionCount"])
    by_weekday = Counter()
    for d in days:
        by_weekday[d["weekday"]] += d["contributionCount"]
    langs = Counter()
    for r in user["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] += e["size"]
    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    busy_date = dt.date.fromisoformat(busiest["date"]).strftime("%b %d").lower()

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
           "<style>",
           ":root{--ink:#1b1b1b;--pen:#d9480f;--bg:#ffffff;--faint:#1b1b1b2e}",
           "@media (prefers-color-scheme:dark){:root{--ink:#e8e6e1;--pen:#ff8a4c;--bg:#0d1117;--faint:#e8e6e12e}}",
           "text{font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:var(--ink)}",
           ".m{font-size:10px;letter-spacing:.12em;fill:var(--pen)}.b{font-size:16px}.dim{opacity:.55}",
           ".l{stroke:var(--pen);stroke-width:.8;fill:none}",
           "polygon{stroke:var(--ink);stroke-width:.55;stroke-linejoin:round}",
           ".g{fill:none;stroke:var(--faint)}.t{fill:var(--bg)}.hot{fill:var(--pen)}",
           ".s1{fill:url(#h1)}.s2{fill:url(#h2)}.hl{stroke:var(--ink);stroke-width:.45}.pb{fill:var(--bg)}",
           "</style><defs>",
           '<pattern id="h1" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(-20)">'
           '<rect class="pb" width="3" height="3"/><line class="hl" x1="0" y1="0" x2="0" y2="3"/></pattern>',
           '<pattern id="h2" width="2" height="2" patternUnits="userSpaceOnUse" patternTransform="rotate(40)">'
           '<rect class="pb" width="2" height="2"/><line class="hl" x1="0" y1="0" x2="0" y2="2"/></pattern>',
           "</defs>"]
    # plotter furniture, same as the cat
    out.append(f'<rect class="l" x="24" y="24" width="{W - 48}" height="{H - 48}" stroke-dasharray="2 4"/>')
    for x, y, dx, dy in [(16, 16, 1, 1), (W - 16, 16, -1, 1), (16, H - 16, 1, -1), (W - 16, H - 16, -1, -1)]:
        out.append(f'<path class="l" d="M{x} {y + 14 * dy}V{y}H{x + 14 * dx}"/>')
    out.append('<text class="m" x="44" y="52">a year of commits, as a skyline</text>')
    out.append(f'<text class="m" x="{W - 44}" y="52" text-anchor="end">plotted {today}</text>')

    out += skyline(weeks, 130, 292)

    # languages: hatched bars, a different pen angle per language
    total = sum(langs.values()) or 1
    out.append('<text class="m" x="44" y="380">languages</text>')
    for i, (name, size) in enumerate(langs.most_common(5)):
        y, frac = 398 + i * 24, size / total
        out.append(f'<pattern id="l{i}" width="3" height="3" patternUnits="userSpaceOnUse" '
                   f'patternTransform="rotate({-60 + 30 * i})"><line class="hl" x1="0" y1="0" x2="0" y2="3"/></pattern>')
        out.append(f'<text x="44" y="{y + 11}">{name.lower().replace("&", "&amp;")}</text>')
        out.append(f'<rect x="150" y="{y + 1}" width="{max(2, 150 * frac):.1f}" height="12" fill="url(#l{i})" '
                   'stroke="var(--ink)" stroke-width=".6"/>')
        out.append(f'<text class="dim" x="{158 + 150 * frac:.1f}" y="{y + 11}">{frac:.0%}</text>')

    facts = [
        (f'{cc["contributionCalendar"]["totalContributions"]:,}', "contributions this year"),
        (f"{longest}d", f"longest streak · current {current}d"),
        (str(busiest["contributionCount"]), f"busiest day · {busy_date}"),
        (WEEKDAYS[by_weekday.most_common(1)[0][0]] if days else "-", "favourite day to ship"),
        (f'{cc["totalCommitContributions"]:,}',
         f'commits · {cc["totalPullRequestContributions"]} prs · {cc["totalIssueContributions"]} issues'),
        (f'{user["repositories"]["totalCount"]}', f"public repos · {stars} stars"),
    ]
    out.append('<text class="m" x="380" y="380">facts</text>')
    for i, (big, small) in enumerate(facts):
        y = 411 + i * 22
        out.append(f'<text class="b" x="490" y="{y}" text-anchor="end">{big}</text>')
        out.append(f'<text class="dim" x="500" y="{y}" style="font-size:11px">{small}</text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    print(render(fetch(sys.argv[1], os.environ["GITHUB_TOKEN"]), dt.date.today().isoformat()))
