#!/usr/bin/env python3
"""Render self-contained animated SVG cards for the @isthatleo GitHub profile."""
from __future__ import annotations

import base64
import html
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CARDS = ROOT / "cards"
PROFILE_PATH = DATA / "profile.json"
CONTRIB_PATH = DATA / "contributions.json"
STATIC = os.getenv("STATIC", "0") == "1"

PALETTE = {
    "bg": "#07090c", "surface": "#0e1116", "raised": "#161b22",
    "line": "#222933", "line2": "#2c343e", "white": "#eef1f5",
    "text": "#a8b1be", "muted": "#7f8a98", "faint": "#5d6774",
    "signal": "#2bb0cf", "signal2": "#1b93b1", "success": "#2f9d74",
}
LIGHT = {"bg": "#f8f6f1", "surface": "#ffffff", "line": "#e4e0d5",
         "white": "#1a1d21", "text": "#4b4f55", "muted": "#70716c",
         "signal": "#0b8fad"}

def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)

def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def font_css() -> str:
    """Subset local WOFF/TTF fonts when present; system fallbacks remain deterministic."""
    font_dir = ROOT / "fonts"
    rules = []
    if font_dir.exists():
        for family, filename in (("Geist", "Geist-Regular.woff"), ("Geist Mono", "GeistMono-Regular.woff")):
            source = font_dir / filename
            if not source.exists():
                continue
            subset = font_dir / (source.stem + "-subset.woff")
            if not subset.exists() or subset.stat().st_mtime < source.stat().st_mtime:
                try:
                    subprocess.run([
                        "pyftsubset", str(source), f"--output-file={subset}",
                        "--flavor=woff", "--unicodes=U+0020-007E,U+00A0-00FF",
                    ], check=True, capture_output=True)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            encoded = base64.b64encode(subset.read_bytes()).decode("ascii")
            rules.append(f"@font-face{{font-family:'{family}';src:url(data:font/woff;base64,{encoded}) format('woff');font-display:swap}}")
    return "".join(rules)

def svg_start(width: int, height: int, delay: float = 0) -> str:
    animation = "" if STATIC else f"""
      @keyframes rise{{from{{opacity:0;transform:translateY(18px)}}to{{opacity:1;transform:translateY(0)}}}}
      @keyframes reveal{{from{{opacity:0}}to{{opacity:1}}}}
      @keyframes sweep{{0%{{transform:translateX(-120%)}}100%{{transform:translateX(220%)}}}}
      .enter{{opacity:0;animation:rise .75s cubic-bezier(.2,.8,.2,1) {delay:.2f}s both}}
      .fade{{opacity:0;animation:reveal .7s ease {delay+.18:.2f}s both}}
      .shine{{animation:sweep 5s ease-in-out {delay+1.5:.2f}s infinite}}
    """
    reduce = "" if STATIC else "@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;opacity:1!important;transform:none!important}animate,animateTransform,set{display:none!important}}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
    <title>NOTLXNRD profile card</title><defs>
      <linearGradient id="accent" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{PALETTE['signal']}"/><stop offset="1" stop-color="{PALETTE['signal2']}"/></linearGradient>
      <clipPath id="clip"><rect x="1" y="1" width="{width-2}" height="{height-2}" rx="18"/></clipPath>
    </defs><style>
      {font_css()}
      text{{font-family:Geist,'Arial',sans-serif}} .mono{{font-family:'Geist Mono',monospace}}
      {animation}
      {reduce}
    </style>
    <rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="18" fill="{PALETTE['surface']}" stroke="{PALETTE['line']}"/>
    <g clip-path="url(#clip)">'''

def svg_end() -> str:
    return "</g></svg>"

def label(x: int, y: int, text: str, size: int = 11, color: str | None = None, mono: bool = True) -> str:
    cls = "mono" if mono else ""
    return f'<text class="{cls}" x="{x}" y="{y}" font-size="{size}" fill="{color or PALETTE["muted"]}">{esc(text)}</text>'

def rect(x: int, y: int, w: int, h: int, fill: str, rx: int = 8, opacity: float = 1) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" opacity="{opacity}"/>'

def render_hero(profile: dict) -> str:
    name = profile["name"]
    role = profile["role"]
    tagline = profile["tagline"]
    loc = profile["location"]
    s = svg_start(960, 230, 0)
    s += f'<circle cx="850" cy="35" r="115" fill="{PALETTE["signal"]}" opacity=".06"/>'
    s += f'<circle cx="850" cy="35" r="78" fill="none" stroke="{PALETTE["signal"]}" opacity=".18"/>'
    if not STATIC:
        s += '<circle cx="850" cy="35" r="78" fill="none" stroke="url(#accent)" stroke-width="1.5" opacity=".22"><animate attributeName="opacity" values=".08;.34;.08" dur="5s" begin="1s" repeatCount="indefinite"/></circle>'
    s += label(42, 48, "NOTLXNRD  /  ENGINEERING PROFILE", 11, PALETTE["signal"])
    s += f'<text class="enter" x="40" y="112" font-size="54" font-weight="650" letter-spacing="-2.4" fill="{PALETTE["white"]}">{esc(name)}</text>'
    s += f'<text class="fade" x="43" y="151" font-size="17" fill="{PALETTE["signal"]}">{esc(role)}</text>'
    s += f'<text class="fade" x="43" y="181" font-size="13" fill="{PALETTE["text"]}">{esc(tagline)}</text>'
    s += label(43, 207, loc.upper(), 10, PALETTE["muted"])
    s += f'<path d="M790 170h105" stroke="{PALETTE["line2"]}"/><circle cx="900" cy="170" r="4" fill="{PALETTE["signal"]}"/>'
    return s + svg_end()

def derive_stats(data: dict) -> dict:
    days = data.get("days", [])
    parsed = []
    for item in days:
        try:
            parsed.append((date.fromisoformat(item["date"]), max(0, int(item["count"]))))
        except (KeyError, ValueError, TypeError):
            continue
    parsed.sort()
    active = [d for d, count in parsed if count > 0]
    current = 0
    cursor = date.today()
    by_date = dict(parsed)
    # A contribution today extends the streak; otherwise start from yesterday.
    if by_date.get(cursor, 0) == 0:
        cursor -= timedelta(days=1)
    while by_date.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    months: dict[str, int] = defaultdict(int)
    for day, count in parsed:
        months[day.strftime("%b %Y")] += count
    busiest = max(parsed, key=lambda pair: pair[1], default=(None, 0))
    return {
        "total": sum(c for _, c in parsed),
        "active_days": len(active),
        "current_streak": current,
        "busiest_date": busiest[0].isoformat() if busiest[0] else "—",
        "busiest_count": busiest[1],
        "months": list(months.items())[-12:],
        "days": parsed,
    }

def render_contributions(data: dict) -> str:
    stats = derive_stats(data)
    s = svg_start(960, 210, 1.0)
    s += label(34, 35, "ACTIVITY / LAST 12 MONTHS", 11, PALETTE["signal"])
    metrics = [("CURRENT STREAK", f'{stats["current_streak"]} days'),
               ("ACTIVE DAYS", str(stats["active_days"])),
               ("BUSIEST DAY", f'{stats["busiest_date"]} · {stats["busiest_count"]}')]
    for i, (key, val) in enumerate(metrics):
        x = 36 + i * 300
        s += label(x, 76, key, 10)
        s += f'<text x="{x}" y="112" font-size="27" font-weight="600" fill="{PALETTE["white"]}">{esc(val)}</text>'
    months = stats["months"]
    maxv = max((v for _, v in months), default=1) or 1
    chart_x, base_y, bar_w, gap = 40, 174, 48, 22
    for i, (month, value) in enumerate(months):
        h = max(3, int(52 * value / maxv))
        x = chart_x + i * (bar_w + gap)
        s += rect(x, base_y-h, bar_w, h, PALETTE["signal"] if value == maxv else PALETTE["raised"], 5)
        s += label(x, 193, month.split()[0].upper(), 8, PALETTE["muted"])
    return s + svg_end()

def render_tile(title: str, subtitle: str, href: str, accent: str, delay: float) -> str:
    # Tiles are 640x150 and are displayed at 32.5% each in README.
    s = svg_start(640, 150, delay)
    s += f'<path d="M0 0h640v150H0z" fill="{PALETTE["surface"]}"/>'
    s += f'<rect x="1" y="1" width="638" height="148" rx="17" fill="none" stroke="{PALETTE["line"]}"/>'
    s += f'<circle cx="570" cy="38" r="18" fill="{accent}" opacity=".14"/>'
    s += f'<path d="M562 38h16m-7-7 7 7-7 7" fill="none" stroke="{accent}" stroke-width="1.5"/>'
    s += f'<text class="enter" x="28" y="63" font-size="25" font-weight="650" fill="{PALETTE["white"]}">{esc(title)}</text>'
    s += f'<text x="29" y="91" font-size="13" fill="{PALETTE["muted"]}">{esc(subtitle)}</text>'
    s += label(29, 124, "OPEN DESTINATION  ↗", 9, accent)
    return s + svg_end()

def render_repo(repo: dict, delay: float) -> str:
    s = svg_start(960, 178, delay)
    s += label(30, 36, repo.get("eyebrow", "SELECTED WORK").upper(), 10, PALETTE["signal"])
    s += f'<text class="enter" x="30" y="78" font-size="27" font-weight="620" fill="{PALETTE["white"]}">{esc(repo["name"])}</text>'
    s += f'<text x="30" y="108" font-size="13" fill="{PALETTE["text"]}">{esc(repo["description"])}</text>'
    s += label(30, 145, repo.get("status", "In development").upper(), 9, PALETTE["muted"])
    s += f'<path d="M865 85h45m-8-8 8 8-8 8" stroke="{PALETTE["signal"]}" fill="none" stroke-width="1.5"/>'
    return s + svg_end()

def render_graph(data: dict) -> str:
    days = derive_stats(data)["days"]
    s = svg_start(960, 176, 6.0)
    s += label(30, 34, "CONTRIBUTION MAP  /  GITHUB", 10, PALETTE["signal"])
    if not days:
        s += f'<text x="30" y="91" font-size="16" fill="{PALETTE["text"]}">Contribution data will appear after the first successful refresh.</text>'
        return s + svg_end()
    lookup = {d: c for d, c in days}
    start = days[0][0]
    start -= timedelta(days=(start.weekday() + 1) % 7)
    maxv = max(lookup.values(), default=1) or 1
    for idx in range(371):
        day = start + timedelta(days=idx)
        if day > date.today():
            break
        count = lookup.get(day, 0)
        level = 0 if count == 0 else min(4, 1 + int(3 * count / maxv))
        fills = [PALETTE["raised"], "#12313a", "#155366", "#1b7d98", PALETTE["signal"]]
        col, row = idx // 7, idx % 7
        x, y = 30 + col * 17, 55 + row * 15
        s += f'<rect x="{x}" y="{y}" width="11" height="10" rx="2" fill="{fills[level]}"><title>{day.isoformat()}: {count} contributions</title></rect>'
    s += label(30, 166, f'{derive_stats(data)["total"]:,} contributions · {len(days)} days tracked', 9)
    return s + svg_end()

def main() -> None:
    profile = load_json(PROFILE_PATH, {})
    contributions = load_json(CONTRIB_PATH, {"days": []})
    if not profile:
        raise SystemExit(f"Missing profile configuration: {PROFILE_PATH}")
    CARDS.mkdir(parents=True, exist_ok=True)
    (CARDS / "hero.svg").write_text(render_hero(profile), encoding="utf-8")
    (CARDS / "contributions.svg").write_text(render_contributions(contributions), encoding="utf-8")
    (CARDS / "contribution-graph.svg").write_text(render_graph(contributions), encoding="utf-8")
    for i, tile in enumerate(profile["tiles"]):
        target = CARDS / "links" / f'{tile["id"]}.svg'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_tile(tile["title"], tile["subtitle"], tile["href"], tile["accent"], 1.8+i*.35), encoding="utf-8")
    for i, repo in enumerate(profile["featured_repos"]):
        target = CARDS / "repos" / f'{repo["id"]}.svg'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_repo(repo, 3.2+i*.45), encoding="utf-8")
    # Fail closed: every generated SVG must be parseable XML.
    for path in CARDS.rglob("*.svg"):
        ET.parse(path)
    print(f"Rendered {len(list(CARDS.rglob('*.svg')))} SVG cards ({'static' if STATIC else 'animated'}).")

if __name__ == "__main__":
    main()
