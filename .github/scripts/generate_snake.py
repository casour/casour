import json
import os
import ssl
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

SNAKE_LEN = 12
ROUTE_COLS = (34, COLS - 1)   # 蛇活动的矩形回路，贴着最近几周
ROUTE_ROWS = (0, 4)

THEMES = {
    "dark": {
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "snake": "#a855f7",
        "tail": "#6d28d9",
        "eye": "#0d1117",
    },
    "light": {
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "snake": "#7c3aed",
        "tail": "#a78bfa",
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


def build_route():
    """沿矩形边框走一圈，首尾相接，形成无缝循环。"""
    c0, c1 = ROUTE_COLS
    r0, r1 = ROUTE_ROWS
    route = []
    for c in range(c0, c1 + 1):
        route.append((c, r0))
    for r in range(r0 + 1, r1 + 1):
        route.append((c1, r))
    for c in range(c1 - 1, c0 - 1, -1):
        route.append((c, r1))
    for r in range(r1 - 1, r0, -1):
        route.append((c0, r))
    return route


ROUTE = build_route()
N = len(ROUTE)
STEP_TIME = 0.42
DUR = round(N * STEP_TIME, 2)


def build_anim(i):
    """第 i 节沿回路行走的 SMIL 动画：values 是相对自身基准位置的位移。"""
    base_c, base_r = ROUTE[(-i) % N]
    values = []
    times = []
    for t in range(N + 1):
        tc, tr = ROUTE[(t - i) % N]
        dx = (tc - base_c) * STEP
        dy = (tr - base_r) * STEP
        values.append(f"{dx} {dy}")
        times.append(f"{t / N:.4f}")
    return (
        f'<animateTransform attributeName="transform" attributeType="XML" type="translate" '
        f'values="{";".join(values)}" keyTimes="{";".join(times)}" '
        f'dur="{DUR}s" repeatCount="indefinite"/>'
    )


def build(theme_name):
    t = THEMES[theme_name]
    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="contribution snake">'
    )
    out.append("<style>rect{shape-rendering:geometricPrecision}</style>")
    out.append(
        f'<defs><linearGradient id="g-{theme_name}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{t["tail"]}"/>'
        f'<stop offset="100%" stop-color="{t["snake"]}"/>'
        f"</linearGradient></defs>"
    )

    # 贡献网格：尺寸全部写死，不依赖任何 CSS
    out.append("<g>")
    for ci, week in enumerate(weeks):
        for day in week["contributionDays"]:
            r = day["weekday"]
            x = PAD + ci * STEP
            y = PAD + r * STEP
            fill = t["levels"][level(day["contributionCount"])]
            out.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                f'rx="2" ry="2" fill="{fill}"/>'
            )
    out.append("</g>")

    # 蛇：每节一个 16x16 方块，靠 transform 逐节跟随
    def cell_xy(c, r):
        return PAD + c * STEP - 2, PAD + r * STEP - 2

    for i in range(SNAKE_LEN - 1, 0, -1):  # 先画尾巴，后画头
        bc, br = ROUTE[(-i) % N]
        x, y = cell_xy(bc, br)
        ratio = i / SNAKE_LEN
        fill = t["tail"] if ratio > 0.65 else f"url(#g-{theme_name})"
        out.append(
            f'<g>{build_anim(i)}'
            f'<rect x="{x}" y="{y}" width="16" height="16" '
            f'rx="4" ry="4" fill="{fill}"/></g>'
        )

    # 头部（含眼睛），与 i=0 同步
    hc, hr = ROUTE[0]
    hx, hy = cell_xy(hc, hr)
    out.append(f"<g>{build_anim(0)}")
    out.append(
        f'<rect x="{hx - 0.5}" y="{hy - 0.5}" width="17" height="17" '
        f'rx="4.5" ry="4.5" fill="{t["snake"]}"/>'
    )
    ex = hx - 0.5 + 17 - 4.5
    ey = hy - 0.5 + 8.5
    out.append(
        f'<circle cx="{ex}" cy="{ey - 3}" r="1.9" fill="{t["eye"]}"/>'
        f'<circle cx="{ex}" cy="{ey + 3}" r="1.9" fill="{t["eye"]}"/>'
    )
    out.append("</g>")

    out.append("</svg>")
    return "\n".join(out)


for name in ("dark", "light"):
    path = os.path.join(OUT_DIR, f"snake-{name}.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build(name))
    print("wrote", path, os.path.getsize(path), "bytes")

print(f"grid {COLS}x{ROWS}  route {N} cells  {DUR}s/loop  contributions {cal['totalContributions']}")
