import json
import os
import ssl
import sys
import urllib.error
import urllib.request

LOGIN = os.environ.get("GH_LOGIN", "casour")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("OUT_DIR", HERE)
CACHE = os.path.join(HERE, "contributions.json")


def fetch():
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN not set and no cache available")
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { contributionCount date weekday } }
          }
        }
      }
    }
    """
    body = json.dumps({"query": query, "variables": {"login": LOGIN}}).encode("utf-8")
    req = urllib.request.Request("https://api.github.com/graphql", data=body, method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "wb-profile-setup")
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
        payload = json.loads(r.read().decode("utf-8"))
    if "errors" in payload:
        raise SystemExit(json.dumps(payload["errors"], ensure_ascii=False))
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cal, f, ensure_ascii=False)
    return cal


cal = fetch() if os.environ.get("GH_TOKEN") else json.load(open(CACHE, encoding="utf-8"))

weeks = cal["weeks"]
COLS = len(weeks)
ROWS = 7
CELL = 12
GAP = 4
STEP = CELL + GAP
PAD = 10

W = PAD * 2 + COLS * STEP - GAP
H = PAD * 2 + ROWS * STEP - GAP


def build_snake(length=14):
    """蛇头落在最后一个有贡献的格子上，蛇身向左下方蜿蜒。"""
    active = []
    for ci, week in enumerate(weeks):
        for day in week["contributionDays"]:
            if day["contributionCount"] > 0:
                active.append((ci, day["weekday"]))

    if active:
        head_c, head_r = max(active, key=lambda p: (p[0], -p[1]))
    else:
        head_c, head_r = COLS - 1, 0

    cells = [(head_c, head_r)]
    for i in range(1, length):
        c = head_c - i
        r = min(ROWS - 1, head_r + i // 3)
        if c < 0:
            break
        cells.append((c, r))
    cells.reverse()  # 尾 -> 头
    return cells


SNAKE = build_snake()

THEMES = {
    "dark": {
        "empty": "#161b22",
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "snake": "#a855f7",
        "snake_tail": "#6d28d9",
        "eye": "#0d1117",
    },
    "light": {
        "empty": "#ebedf0",
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "snake": "#7c3aed",
        "snake_tail": "#a78bfa",
        "eye": "#ffffff",
    },
}


def level(count):
    if count <= 0:
        return 0
    if count <= 3:
        return 1
    if count <= 6:
        return 2
    if count <= 9:
        return 3
    return 4


def build(theme_name):
    t = THEMES[theme_name]
    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="contribution snake">'
    )
    out.append("<defs>")
    out.append(
        f'<linearGradient id="body-{theme_name}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{t["snake_tail"]}"/>'
        f'<stop offset="100%" stop-color="{t["snake"]}"/>'
        f"</linearGradient>"
    )
    out.append("</defs>")

    # 贡献网格
    out.append("<g>")
    for ci, week in enumerate(weeks):
        for day in week["contributionDays"]:
            r = day["weekday"]
            x = PAD + ci * STEP
            y = PAD + r * STEP
            fill = t["levels"][level(day["contributionCount"])]
            out.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" ry="2" fill="{fill}"/>'
            )
    out.append("</g>")

    # 蛇身：16x16 连成一条，覆盖格子间隙
    out.append('<g stroke-linejoin="round">')
    for idx, (c, r) in enumerate(SNAKE):
        x = PAD + c * STEP - (STEP - CELL) // 2
        y = PAD + r * STEP - (STEP - CELL) // 2
        is_head = idx == len(SNAKE) - 1
        size = 16 if not is_head else 17
        offset = -2 if not is_head else -2.5
        fill = (
            f'url(#body-{theme_name})' if not is_head else t["snake"]
        )
        out.append(
            f'<rect x="{x + offset + 2}" y="{y + offset + 2}" width="{size}" '
            f'height="{size}" rx="4" ry="4" fill="{fill}"/>'
        )
    out.append("</g>")

    # 眼睛（朝右）
    hc, hr = SNAKE[-1]
    ex = PAD + hc * STEP + CELL / 2 + 2
    ey = PAD + hr * STEP + CELL / 2
    out.append(
        f'<g fill="{t["eye"]}">'
        f'<circle cx="{ex}" cy="{ey - 3}" r="1.9"/>'
        f'<circle cx="{ex}" cy="{ey + 3}" r="1.9"/>'
        f"</g>"
    )

    out.append("</svg>")
    return "\n".join(out)


for name in ("dark", "light"):
    path = os.path.join(HERE, f"snake-{name}.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build(name))
    print("wrote", path, os.path.getsize(path), "bytes")

print(f"grid {COLS}x{ROWS}  total contributions: {cal['totalContributions']}")
