"""Build a "Most Used Languages" SVG card from all owned repos (public + private).

Runs in GitHub Actions with LANGS_TOKEN (read-only fine-grained PAT).
Only language byte totals are written to the SVG; no repo names are exposed.
"""
import json
import os
import urllib.request
from html import escape

TOKEN = os.environ["LANGS_TOKEN"]
HIDE = {"HTML", "CSS", "VBA", "Rich Text Format", "SCSS", "Jupyter Notebook",
        "Dockerfile", "Makefile", "Procfile", "Batchfile", "Roff"}
TOP_N = 8
OUT = "assets/langs.svg"

QUERY = """
query($cursor: String) {
  viewer {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def gql(cursor):
    body = json.dumps({"query": QUERY, "variables": {"cursor": cursor}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["viewer"]["repositories"]


totals, colors, cursor, repo_count = {}, {}, None, 0
while True:
    page = gql(cursor)
    for repo in page["nodes"]:
        repo_count += 1
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            if name in HIDE:
                continue
            totals[name] = totals.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#858585"
    if not page["pageInfo"]["hasNextPage"]:
        break
    cursor = page["pageInfo"]["endCursor"]

top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
whole = sum(v for _, v in top) or 1
items = [(n, v / whole * 100, colors[n]) for n, v in top]

# --- SVG (tokyonight-like, same size as the stats card) ---
W, PAD = 350, 25
rows = (len(items) + 1) // 2
H = 90 + rows * 25
bar_w = W - PAD * 2

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Most Used Languages">',
    '<style>.t{font:600 18px "Segoe UI",Ubuntu,sans-serif;fill:#70a5fd}'
    '.l{font:400 11px "Segoe UI",Ubuntu,sans-serif;fill:#38bdae}</style>',
    f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="4.5" fill="#1a1b27"/>',
    f'<text x="{PAD}" y="35" class="t">Most Used Languages</text>',
    f'<clipPath id="c"><rect x="{PAD}" y="55" width="{bar_w}" height="8" rx="5"/></clipPath>',
    '<g clip-path="url(#c)">',
]
x = PAD
for name, pct, color in items:
    w = bar_w * pct / 100
    parts.append(f'<rect x="{x:.2f}" y="55" width="{w + 0.5:.2f}" height="8" fill="{escape(color)}"/>')
    x += w
parts.append("</g>")

for i, (name, pct, color) in enumerate(items):
    col, row = i % 2, i // 2
    cx = PAD + col * 150
    cy = 85 + row * 25
    parts.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{escape(color)}"/>')
    parts.append(f'<text x="{cx + 15}" y="{cy}" class="l">{escape(name)} {pct:.2f}%</text>')

parts.append("</svg>")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(parts) + "\n")

print(f"repos counted: {repo_count}")
for name, pct, _ in items:
    print(f"{name}: {pct:.2f}%")
