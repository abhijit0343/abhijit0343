#!/usr/bin/env python3
"""Generate profile-card.svg, a dark terminal-style GitHub profile card.

The card shows a contribution heatmap, an ASCII portrait, stat tiles and a
contributions-per-month bar chart. Standard library only.

Usage
  python3 generate_card.py --user abhijit0343 --out profile-card.svg   # needs GITHUB_TOKEN
  python3 generate_card.py --demo --out preview.svg                    # sample data, no network
"""
import argparse
import calendar
import json
import math
import os
import random
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from html import escape

# ----------------------------------------------------------------------------
# Edit these to change the text on the card
# ----------------------------------------------------------------------------
USER = "abhijit0343"
PROMPT = "abhijit@github"
ABOUT = [
    ("name", "Abhijit Karmakar"),
    ("study", "B.Tech CSE, BCREC Durgapur"),
    ("intern", "NIT Durgapur, Systems Research Lab"),
    ("focus", "AI / ML, computer vision, RAG"),
    ("built", "brain-tumor MRI explorer, F1 dynamics simulator, OpenCV apps"),
    ("now", "DSA in Java on LeetCode :)"),
]

# ASCII portrait. Replace it with your own art if you like, but keep every
# line the same length.
PORTRAIT = r"""
                                                    
                                                    
                                 ..                 
                       #         .@                 
                       *.         %#                
                       .%        ..@.    .          
                .       @.  ......*%.    .%         
                #+      =%*##%#%*+%%*=.   %*++      
              . .@   .==-+%####**@%@#+*...##=       
              ...@#.+==+=-*%%**+####*.+%%#+:=.      
            .  .+*@%+=--:::+.+*#%%%#*+===--=+% .    
            .*  ---==::.::+*+*##%%*+==----:-##=.    
             @#*=.::.::---%--=--==--::::.:-=-::+.   
          :- .@*::.:--::. *+:-==+++*==-:. :*:-*@#.  
            +-:::.:.    .:-#-==--------::-.#-:-..   
             =...:..:::---.+-  ..:-----:...*-.:     
             ::::  .:.     :=:----::::-::. +.:      
            ---.....  .-.:-:-:..:-=***=:...= :      
               ...    ...:. .:.:-=++**+=   .::      
               :..  .....   ..:::::-=+==.. ::       
                 ..:..    ......:::.:-:: . :        
                : ::      ...::::..::. .  .         
                .     ......    :==:  ..  .         
                  .   ..     ....:::. :  .          
                . .      ..  ....   .-. .           
                :. ...    .....    .-. .:           
                .: .  .       .:.::::               
              =: :- :  ..       -::::  :            
             ---= -: :  ..      :.     -            
           +-:.:=: -: :. ...         ..             
      ...===:.--::. =: :.   .        -              
    -==+=-::=:-:.:-: -: .:.          ..             
    :------=:-::.:-::.-:  :.          :::.          
  :=:=--:-::=:-=--:-:-:::  ...        .:.-=         
    :----:-..---=--::.:--:.           ..: :-.       
     :------. :------:.  .::.         .:..-:==-.    
       :-----  .::-=-::-:......     ..:..:.--:--=-  
          :--:   :..-=:..:--::::..:::--:-:-----:.   
            :-.   :: .--:   .::::::-::..::....      
"""

# ----------------------------------------------------------------------------
# Look and feel
# ----------------------------------------------------------------------------
FONT = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'Liberation Mono', 'DejaVu Sans Mono', monospace")
BG, PANEL, TILE, LINE = "#0a0d12", "#0d1117", "#10151c", "#1f2630"
TEXT, MUTED, GREEN, BRIGHT, ASCII = "#e6edf3", "#7d8590", "#3fdc66", "#8dffa8", "#a3acb6"
HEAT = ["#122018", "#0f5a2c", "#1b8f43", "#2fd160", "#8dffa8"]
DOTS = ["#ff5f56", "#ffbd2e", "#27c93f"]


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def fetch_weeks(login, token):
    query = (
        "query($login:String!){user(login:$login){contributionsCollection{"
        "contributionCalendar{totalContributions weeks{contributionDays{"
        "date contributionCount}}}}}}"
    )
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "profile-card-generator",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as err:
        raise SystemExit("GitHub API returned HTTP %d: %s" % (err.code, err.read()[:200].decode("utf-8", "replace")))
    if payload.get("errors") or not payload.get("data", {}).get("user"):
        raise RuntimeError("GitHub API error: %s" % payload.get("errors", "user not found"))
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [
        [(date.fromisoformat(d["date"]), d["contributionCount"]) for d in w["contributionDays"]]
        for w in cal["weeks"]
    ]
    return cal["totalContributions"], weeks


def demo_weeks():
    rnd = random.Random(7)
    today = date.today()
    start = today - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # weeks start on Sunday
    weeks, cur, d = [], [], start
    while d <= today:
        if (d.weekday() + 1) % 7 == 0 and cur:
            weeks.append(cur)
            cur = []
        n = 0 if rnd.random() < 0.38 else int(rnd.expovariate(1 / 3.2)) + 1
        cur.append((d, n))
        d += timedelta(days=1)
    weeks.append(cur)
    return sum(c for w in weeks for _, c in w), weeks


def compute_stats(weeks, total):
    days = [x for w in weeks for x in w]
    counts = [c for _, c in days]

    longest, run = (0, None, None), 0
    for i, c in enumerate(counts):
        if c > 0:
            run += 1
            if run > longest[0]:
                longest = (run, days[i - run + 1][0], days[i][0])
        else:
            run = 0

    end = len(days) - 1
    if counts[end] == 0 and end > 0:  # today may not have any activity yet
        end -= 1
    i = end
    while i >= 0 and counts[i] > 0:
        i -= 1
    length = end - i
    current = (length, days[i + 1][0], days[end][0]) if length else (0, None, None)

    months = {}
    for d, c in days:
        months[(d.year, d.month)] = months.get((d.year, d.month), 0) + c
    months = list(months.items())[-12:]

    best_i = max(range(len(days)), key=lambda k: counts[k])
    active = sum(1 for c in counts if c > 0)
    return {
        "total": total,
        "days": len(days),
        "active": active,
        "best": (counts[best_i], days[best_i][0]),
        "avg": (total / active) if active else 0.0,
        "current": current,
        "longest": longest,
        "months": months,
        "max": max(counts) or 1,
    }


# ----------------------------------------------------------------------------
# SVG helpers
# ----------------------------------------------------------------------------
def fmt_date(d):
    return "%s %d" % (d.strftime("%b"), d.day)


def span(streak):
    if not streak[0]:
        return "no active streak"
    if streak[1] == streak[2]:
        return fmt_date(streak[1])
    return "%s - %s" % (fmt_date(streak[1]), fmt_date(streak[2]))


def txt(x, y, s, size=12, fill=TEXT, weight="normal", anchor="start", extra=""):
    return ('<text x="%s" y="%s" font-size="%s" fill="%s" font-weight="%s" '
            'text-anchor="%s" %s>%s</text>' % (x, y, size, fill, weight, anchor, extra, escape(str(s))))


def rect(x, y, w, h, fill, stroke=None, rx=0):
    s = ' stroke="%s"' % stroke if stroke else ""
    return '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s"%s/>' % (x, y, w, h, rx, fill, s)


def panel(x, y, w, h, caption):
    out = [rect(x + 0.5, y + 0.5, w - 1, h - 1, PANEL, LINE, 8)]
    for i, c in enumerate(DOTS):
        out.append('<circle cx="%s" cy="%s" r="3.5" fill="%s" opacity="0.85"/>' % (x + 16 + i * 12, y + 16, c))
    out.append(txt(x + w / 2, y + 19, caption, 9.5, MUTED, anchor="middle"))
    return out


def tile(x, y, w, h, label, value, suffix, sub, value_fill=TEXT):
    out = [rect(x + 0.5, y + 0.5, w - 1, h - 1, TILE, LINE, 6)]
    out.append(txt(x + 12, y + 18, "$ " + label, 9.5, MUTED))
    out.append(txt(x + 12, y + 45, value, 26, value_fill, "bold"))
    if suffix:
        out.append(txt(x + 12 + len(str(value)) * 15.6 + 6, y + 45, suffix, 10.5, MUTED))
    out.append(txt(x + 12, y + 59, sub, 9, MUTED))
    return out


# ----------------------------------------------------------------------------
# Card
# ----------------------------------------------------------------------------
def render(total, weeks):
    st = compute_stats(weeks, total)
    W, PAD = 900, 40
    pitch, cell = 15, 12
    ncols = len(weeks)
    parts = []

    # --- contributions.sh -----------------------------------------------------
    parts.append(txt(W / 2, 46, PROMPT + " ~ $ ./contributions.sh", 18, TEXT, "bold", "middle"))
    gx = (W - (ncols * pitch - 3)) / 2 + 14
    gy = 96
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        parts.append(txt(gx - 8, gy + row * pitch + 10, name, 10, MUTED, anchor="end"))
    last_col, prev_month = -10, None
    for ci, wk in enumerate(weeks):
        m = wk[0][0].month
        if m != prev_month:
            if ci - last_col >= 3:
                parts.append(txt(gx + ci * pitch, gy - 10, calendar.month_abbr[m], 10, MUTED))
                last_col = ci
            prev_month = m
    for ci, wk in enumerate(weeks):
        for d, c in wk:
            row = (d.weekday() + 1) % 7
            lvl = 0 if c == 0 else max(1, math.ceil(4 * c / st["max"]))
            parts.append(rect(round(gx + ci * pitch, 1), gy + row * pitch, cell, cell, HEAT[lvl], rx=2.5))
    parts.append(txt(gx, gy + 7 * pitch + 20, "{:,} contributions in the last year".format(total), 11, TEXT, "bold"))

    # --- whoami ----------------------------------------------------------------
    parts.append(txt(W / 2, 272, PROMPT + " ~ $ whoami", 18, TEXT, "bold", "middle"))
    PY, PH = 296, 410
    lx, lw = PAD, 400
    rx_, rw = PAD + lw + 16, W - 2 * PAD - lw - 16

    parts += panel(lx, PY, lw, PH, "portrait.txt")
    lines = PORTRAIT.strip("\n").split("\n")
    cols = max(len(l) for l in lines)
    cw, lh, fs = 5.5, 9.3, 9.1
    x0 = lx + (lw - cols * cw) / 2
    for i, line in enumerate(lines):
        if line.strip():
            parts.append(txt(round(x0, 1), round(PY + 40 + i * lh, 1), line.ljust(cols), fs, ASCII,
                             extra='xml:space="preserve" textLength="%s" lengthAdjust="spacing"' % (cols * cw)))

    parts += panel(rx_, PY, rw, PH, "stats.json")
    tw, th, gap = (rw - 28 - 8) / 2, 66, 8
    tx0, ty0 = rx_ + 14, PY + 34
    cur, lon = st["current"], st["longest"]
    pct = round(100.0 * st["active"] / st["days"]) if st["days"] else 0
    best_n, best_d = st["best"]
    tiles = [
        ("current streak", cur[0], "day" if cur[0] == 1 else "days", span(cur), GREEN),
        ("longest streak", lon[0], "day" if lon[0] == 1 else "days", span(lon), TEXT),
        ("contributions", "{:,}".format(total), "", "in the last year", TEXT),
        ("active days", st["active"], "/ %d" % st["days"], "%d%% of the year" % pct, TEXT),
        ("best day", best_n, "", fmt_date(best_d) if best_n else "-", TEXT),
        ("avg / active day", "%.1f" % st["avg"], "", "contributions", TEXT),
    ]
    for k, (label, value, suffix, sub, fill) in enumerate(tiles):
        r, c = divmod(k, 2)
        parts += tile(tx0 + c * (tw + gap), ty0 + r * (th + gap), tw, th, label, value, suffix, sub, fill)

    cx, cy = tx0, ty0 + 3 * (th + gap)
    cwid, chei = rw - 28, PY + PH - 14 - cy
    parts.append(rect(cx + 0.5, cy + 0.5, cwid - 1, chei - 1, TILE, LINE, 6))
    parts.append(txt(cx + 12, cy + 18, "$ contributions / month", 9.5, MUTED))
    months = st["months"]
    mmax = max([v for _, v in months] + [1])
    base, top = cy + chei - 26, cy + 50
    slot = (cwid - 24) / max(1, len(months))
    bw = slot * 0.6
    peak = max(range(len(months)), key=lambda k: months[k][1]) if months else 0
    for k, ((yy, mm), v) in enumerate(months):
        h = max(2.0, (base - top) * v / mmax)
        x = cx + 12 + k * slot + (slot - bw) / 2
        parts.append(rect(round(x, 1), round(base - h, 1), round(bw, 1), round(h, 1),
                          BRIGHT if k == peak and v else GREEN, rx=1.5))
        parts.append(txt(round(x + bw / 2, 1), cy + chei - 10, calendar.month_abbr[mm][0], 9, MUTED, anchor="middle"))
        if k == peak and v:
            parts.append(txt(round(x + bw / 2, 1), round(base - h - 6, 1), "{:,}".format(v), 9, TEXT, anchor="middle"))

    # --- about.txt -------------------------------------------------------------
    ay = PY + PH + 16
    ah = 38 + len(ABOUT) * 20 + 10
    parts += panel(PAD, ay, W - 2 * PAD, ah, "about.txt")
    for i, (k, v) in enumerate(ABOUT):
        yy = ay + 46 + i * 20
        parts.append(txt(PAD + 28, yy, k, 12, MUTED))
        parts.append(txt(PAD + 28 + 90, yy, v, 12, TEXT))

    H = ay + ah + 28
    head = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
        'role="img" aria-label="Terminal-style GitHub profile card">\n'
        '<title>%s profile card</title>\n'
        '<rect x="0.5" y="0.5" width="%d" height="%d" rx="16" fill="%s" stroke="%s"/>\n'
        '<g font-family="%s">\n' % (W, H, W, H, escape(PROMPT), W - 1, H - 1, BG, LINE, FONT)
    )
    return head + "\n".join(parts) + "\n</g>\n</svg>\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", default=USER)
    ap.add_argument("--out", default="profile-card.svg")
    ap.add_argument("--demo", action="store_true", help="use sample data instead of the GitHub API")
    a = ap.parse_args()

    if a.demo:
        total, weeks = demo_weeks()
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            sys.exit("Set GITHUB_TOKEN (or GH_TOKEN), or run with --demo.")
        total, weeks = fetch_weeks(a.user, token)

    with open(a.out, "w", encoding="utf-8") as f:
        f.write(render(total, weeks))
    print("wrote %s (%d contributions)" % (a.out, total))


if __name__ == "__main__":
    main()
