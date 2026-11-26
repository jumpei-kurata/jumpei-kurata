"""Build a GitHub stats SVG card that also counts private work.

Runs in GitHub Actions with LANGS_TOKEN (read-only fine-grained PAT).
Only totals are written; no repo names are exposed.
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape

TOKEN = os.environ["LANGS_TOKEN"]
OUT = "assets/stats.svg"

now = datetime.now(timezone.utc)
year_ago = now - timedelta(days=365)


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]


v = gql("""
query($from: DateTime!, $to: DateTime!) {
  viewer {
    name
    login
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER) { totalCount }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
      totalCommitContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
      totalRepositoriesWithContributedCommits
    }
  }
}
""", {"from": year_ago.isoformat(), "to": now.isoformat()})["viewer"]

login = v["login"]
s = gql("""
query($prq: String!, $isq: String!, $rvq: String!) {
  prs: search(query: $prq, type: ISSUE) { issueCount }
  issues: search(query: $isq, type: ISSUE) { issueCount }
  reviews: search(query: $rvq, type: ISSUE) { issueCount }
}
""", {"prq": f"author:{login} is:pr", "isq": f"author:{login} is:issue",
      "rvq": f"reviewed-by:{login} is:pr -author:{login}"})

cc = v["contributionsCollection"]
commits = cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
prs = max(v["pullRequests"]["totalCount"], s["prs"]["issueCount"])
issues = max(v["issues"]["totalCount"], s["issues"]["issueCount"])

rows = [
    ("Total Commits (last year)", commits),
    ("Pull Requests (all time)", prs),
    ("Contributions (last year)", cc["contributionCalendar"]["totalContributions"]),
    ("Issues (all time)", issues),
    ("Repositories", v["repositories"]["totalCount"]),
    ("Repos Committed To (last year)", cc["totalRepositoriesWithContributedCommits"]),
]

W, PAD = 467, 25
H = 75 + len(rows) * 26 + 10
name = v["name"] or login

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub Stats">',
    '<style>.t{font:600 18px "Segoe UI",Ubuntu,sans-serif;fill:#70a5fd}'
    '.k{font:600 14px "Segoe UI",Ubuntu,sans-serif;fill:#38bdae}'
    '.v{font:700 14px "Segoe UI",Ubuntu,sans-serif;fill:#38bdae}'
    '.n{font:400 10px "Segoe UI",Ubuntu,sans-serif;fill:#a9b1d6}</style>',
    f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="4.5" fill="#1a1b27"/>',
    f'<text x="{PAD}" y="35" class="t">{escape(name)}\'s GitHub Stats</text>',
]
for i, (label, value) in enumerate(rows):
    y = 72 + i * 26
    parts.append(f'<circle cx="{PAD + 6}" cy="{y - 5}" r="4" fill="#bf91f3"/>')
    parts.append(f'<text x="{PAD + 20}" y="{y}" class="k">{escape(label)}:</text>')
    parts.append(f'<text x="{W - PAD}" y="{y}" class="v" text-anchor="end">{value:,}</text>')
parts.append(f'<text x="{PAD}" y="{H - 12}" class="n">Includes private repositories · updated {now:%Y-%m-%d}</text>')
parts.append("</svg>")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(parts) + "\n")

for label, value in rows:
    print(f"{label}: {value}")
print(f"viewer PRs={v['pullRequests']['totalCount']} search PRs={s['prs']['issueCount']}")
