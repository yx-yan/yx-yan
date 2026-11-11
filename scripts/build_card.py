"""Build the neofetch-style profile card (dark_mode.svg and light_mode.svg).

Fetches live numbers from the GitHub GraphQL API. The token comes from
CARD_TOKEN, then GITHUB_TOKEN, then `gh auth token` for local runs.

    python3 scripts/build_card.py
"""

import json
import os
import subprocess
import urllib.request
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

LOGIN = "yx-yan"
ROOT = Path(__file__).resolve().parent.parent
WIDTH = 60  # characters in the right-hand column

FONT_SIZE = 15
LINE_HEIGHT = 20
# Widest common monospace fallback (Menlo is ~0.60 em); narrower fonts just leave margin.
CHAR_WIDTH = 9.1
PAD = 28
GAP = 4  # characters between the fish and the text

THEMES = {
    "dark": {"bg": "#14213D", "border": "#14213D", "art": "#F4F1EA", "key": "#FFB020",
             "value": "#F4F1EA", "dots": "#4A5A80", "rule": "#7D8BB0"},
    "light": {"bg": "#F6F8FA", "border": "#D0D7DE", "art": "#22386B", "key": "#2F5BB7",
              "value": "#14213D", "dots": "#C4CCD8", "rule": "#8A96AD"},
}


def token() -> str:
    for name in ("CARD_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    return subprocess.run(["gh", "auth", "token"], check=True,
                          capture_output=True, text=True).stdout.strip()


def graphql(query: str, auth: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {auth}"},
    )
    with urllib.request.urlopen(req) as resp:
        body = json.load(resp)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch_stats() -> dict:
    auth = token()
    user = graphql(f"""{{
      user(login: "{LOGIN}") {{
        createdAt
        followers {{ totalCount }}
        repositories(ownerAffiliations: OWNER, privacy: PUBLIC, first: 100) {{
          totalCount
          nodes {{ stargazerCount }}
        }}
      }}
    }}""", auth)["user"]

    # contributionsCollection spans at most one year, so ask for each year since joining.
    created = datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    years = range(created.year, now.year + 1)
    fields = " ".join(
        f'y{y}: contributionsCollection(from: "{max(created, datetime(y, 1, 1, tzinfo=timezone.utc)).isoformat()}", '
        f'to: "{min(now, datetime(y, 12, 31, 23, 59, 59, tzinfo=timezone.utc)).isoformat()}") '
        "{ totalCommitContributions }"
        for y in years
    )
    yearly = graphql(f'{{ user(login: "{LOGIN}") {{ {fields} }} }}', auth)["user"]

    return {
        "created": created.date(),
        "repos": user["repositories"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in user["repositories"]["nodes"]),
        "followers": user["followers"]["totalCount"],
        "commits": sum(v["totalCommitContributions"] for v in yearly.values()),
    }


def uptime(since: date, today: date) -> str:
    years = today.year - since.year
    months = today.month - since.month
    days = today.day - since.day
    if days < 0:
        months -= 1
        prev_month_end = date(today.year, today.month, 1).toordinal() - 1
        days += date.fromordinal(prev_month_end).day
    if months < 0:
        years -= 1
        months += 12

    def unit(n: int, word: str) -> str:
        return f"{n} {word}{'' if n == 1 else 's'}"

    return f"{unit(years, 'year')}, {unit(months, 'month')}, {unit(days, 'day')}"


# A line is a list of (text, style) segments; style is a key in THEMES.
def entry(key: str, value: str, width: int = WIDTH) -> list:
    dots = width - len(key) - len(value) - 4
    return [(". ", "dots"), (key + ":", "key"), (" " + "." * dots + " ", "dots"), (value, "value")]


def pair(left: tuple, right: tuple) -> list:
    half = (WIDTH - 3) // 2
    return entry(*left, width=half) + [(" | ", "dots")] + entry(*right, width=WIDTH - half - 3)


def header(title: str) -> list:
    prefix = "- " + title + " " if title else ""
    return [(prefix, "value"), ("─" * (WIDTH - len(prefix)), "rule")]


def card_lines(stats: dict) -> list:
    return [
        [("yuxuan", "key"), ("@", "value"), ("yan", "key"), (" ", "value")]
        + [("─" * (WIDTH - 11), "rule")],
        entry("Seeking", "AI Engineer roles · Singapore"),
        entry("Uptime", uptime(stats["created"], date.today())),
        [],
        entry("Focus", "LLM agents, tool calling, evals"),
        entry("Stack", "Python, PyTorch, DeepSeek API"),
        [],
        header("Contact"),
        entry("Email.Personal", "cainiao314@gmail.com"),
        entry("Email.Work", "im.yuxuanyan@gmail.com"),
        entry("Website", "yuxuanyan.com"),
        entry("LinkedIn", "yanyuxuan"),
        [],
        header("GitHub Stats"),
        pair(("Repos", str(stats["repos"])), ("Stars", str(stats["stars"]))),
        pair(("Commits", f"{stats['commits']:,}"), ("Followers", str(stats["followers"]))),
    ]


def read_art() -> list:
    lines = (ROOT / "ascii" / "fish.txt").read_text().rstrip("\n").split("\n")
    indent = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    return [l[indent:] for l in lines]


def render(theme: dict, art: list, lines: list) -> str:
    art_cols = max(len(l) for l in art)
    text_x = PAD + (art_cols + GAP) * CHAR_WIDTH
    rows = max(len(art), len(lines))
    width = round(text_x + WIDTH * CHAR_WIDTH + PAD)
    height = PAD * 2 + rows * LINE_HEIGHT
    art_top = (rows - len(art)) // 2
    text_top = (rows - len(lines)) // 2

    def y(row: int) -> int:
        return PAD + row * LINE_HEIGHT + FONT_SIZE

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Consolas, \'SFMono-Regular\', Menlo, '
        f'\'DejaVu Sans Mono\', monospace" font-size="{FONT_SIZE}px">',
        "<style>"
        + "".join(f".{k}{{fill:{v}}}" for k, v in theme.items() if k not in ("bg", "border"))
        + "text,tspan{white-space:pre}</style>",
        f'<rect width="{width}" height="{height}" rx="12" fill="{theme["bg"]}" '
        f'stroke="{theme["border"]}" stroke-width="2"/>',
        f'<text class="art" xml:space="preserve">',
    ]
    for i, line in enumerate(art):
        out.append(f'<tspan x="{PAD}" y="{y(art_top + i)}">{escape(line)}</tspan>')
    out.append("</text>")
    out.append('<text xml:space="preserve">')
    for i, line in enumerate(lines):
        if not line:
            continue
        spans = "".join(f'<tspan class="{style}">{escape(text)}</tspan>' for text, style in line)
        out.append(f'<tspan x="{text_x:.1f}" y="{y(text_top + i)}">{spans}</tspan>')
    out.append("</text></svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    art = read_art()
    lines = card_lines(fetch_stats())
    for name, theme in THEMES.items():
        (ROOT / f"{name}_mode.svg").write_text(render(theme, art, lines))


if __name__ == "__main__":
    main()
