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
from urllib.parse import urlparse

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

def validate_profile(profile: dict) -> None:
    """Validate profile configuration before writing any generated assets."""
    required_text = ("name", "role", "tagline", "location", "website")
    for field in required_text:
        if not isinstance(profile.get(field), str) or not profile[field].strip():
            raise ValueError(f"profile.{field} must be a non-empty string")

    def validate_url(value: Any, field: str) -> None:
        parsed = urlparse(value) if isinstance(value, str) else None
        if not parsed or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{field} must be an absolute HTTP(S) URL")

    validate_url(profile["website"], "profile.website")

    repos = profile.get("featured_repos")
    if not isinstance(repos, list) or not repos:
        raise ValueError("profile.featured_repos must be a non-empty list")
    repo_ids = set()
    for index, repo in enumerate(repos):
        prefix = f"profile.featured_repos[{index}]"
        if not isinstance(repo, dict):
            raise ValueError(f"{prefix} must be an object")
        for field in ("id", "name", "description", "url"):
            if not isinstance(repo.get(field), str) or not repo[field].strip():
                raise ValueError(f"{prefix}.{field} must be a non-empty string")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", repo["id"]):
            raise ValueError(f"{prefix}.id contains unsafe path characters")
        if repo["id"] in repo_ids:
            raise ValueError(f"Duplicate featured project id: {repo['id']}")
        repo_ids.add(repo["id"])
        validate_url(repo["url"], f"{prefix}.url")

    tiles = profile.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        raise ValueError("profile.tiles must be a non-empty list")
    tile_ids = set()
    for index, tile in enumerate(tiles):
        prefix = f"profile.tiles[{index}]"
        if not isinstance(tile, dict):
            raise ValueError(f"{prefix} must be an object")
        for field in ("id", "title", "subtitle", "href", "accent"):
            if not isinstance(tile.get(field), str) or not tile[field].strip():
                raise ValueError(f"{prefix}.{field} must be a non-empty string")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", tile["id"]):
            raise ValueError(f"{prefix}.id contains unsafe path characters")
        if tile["id"] in tile_ids:
            raise ValueError(f"Duplicate tile id: {tile['id']}")
        tile_ids.add(tile["id"])
        validate_url(tile["href"], f"{prefix}.href")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", tile["accent"]):
            raise ValueError(f"{prefix}.accent must be a six-digit hex colour")

    groups = profile.get("stack_groups")
    if not isinstance(groups, list) or len(groups) > 3:
        raise ValueError("profile.stack_groups must be a list of at most three groups")
    for index, group in enumerate(groups):
        if not isinstance(group, dict) or not isinstance(group.get("title"), str) or not group["title"].strip():
            raise ValueError(f"profile.stack_groups[{index}].title must be a non-empty string")
        items = group.get("items")
        if not isinstance(items, list) or len(items) > 6 or any(not isinstance(item, str) or not item.strip() for item in items):
            raise ValueError(f"profile.stack_groups[{index}].items must contain at most six non-empty strings")


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
    """Render the editorial NOTLXNRD hero banner."""
    name, role = profile["name"], profile["role"]
    tagline, loc = profile["tagline"], profile["location"]
    s = svg_start(1200, 330, 0)
    s += '<defs><linearGradient id="hero-bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#101820"/><stop offset=".58" stop-color="#090d12"/><stop offset="1" stop-color="#10151c"/></linearGradient><radialGradient id="hero-glow"><stop stop-color="#2bb0cf" stop-opacity=".22"/><stop offset="1" stop-color="#2bb0cf" stop-opacity="0"/></radialGradient><pattern id="hero-grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="#9eb5c3" stroke-opacity=".055"/></pattern></defs>'
    s += '<rect width="1200" height="330" rx="22" fill="url(#hero-bg)"/><rect width="1200" height="330" rx="22" fill="url(#hero-grid)"/><circle cx="1000" cy="120" r="280" fill="url(#hero-glow)"/><path d="M0 1H1200" stroke="url(#accent)" stroke-width="2"/>'
    s += label(58, 58, "NOTLXNRD  /  PERSONAL ENGINEERING PROFILE", 12, "#58c7dc")
    s += '<rect x="58" y="82" width="42" height="3" rx="1.5" fill="url(#accent)"/>'
    s += f'<text class="enter" x="54" y="166" font-size="67" font-weight="720" letter-spacing="-3.5" fill="{PALETTE["white"]}">{esc(name)}</text>'
    s += f'<text class="fade" x="59" y="207" font-size="22" font-weight="550" fill="#62c9dd">{esc(role)}</text>'
    s += f'<text class="fade" x="59" y="249" font-size="15" fill="{PALETTE["text"]}">{esc(tagline)}</text>'
    s += label(59, 310, loc.upper(), 10, PALETTE["muted"])
    s += '<rect x="850" y="84" width="292" height="174" rx="16" fill="#0c1218" stroke="#263642"/>'
    s += label(878, 119, "ENGINEERING / 001", 10, "#718491")
    s += '<circle cx="1105" cy="113" r="5" fill="#55c6dc"><animate attributeName="opacity" values=".25;.9;.25" dur="4s" repeatCount="indefinite"/></circle><path d="M878 139H1114" stroke="#25333d"/>'
    s += label(878, 172, "AI SYSTEMS", 11, "#d5e0e7")
    s += label(878, 199, "PRODUCT ENGINEERING", 11, "#d5e0e7")
    s += label(878, 226, "BUSINESS SOFTWARE", 11, "#d5e0e7")
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
    if not stats["days"]:
        s += '<rect x="30" y="58" width="900" height="112" rx="12" fill="#111820" stroke="#26323c"/>'
        s += label(54, 101, "WAITING FOR VERIFIED GITHUB ACTIVITY", 12, PALETTE["white"])
        s += '<text x="54" y="130" font-size="13" fill="#9aa8b5">Live contribution metrics will appear after the data refresh succeeds. No numbers are fabricated.</text>'
        return s + svg_end()
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
    """Render a project as a compact editorial case-study panel."""
    s = svg_start(960, 198, delay)
    s += '<rect x="1" y="1" width="958" height="196" rx="18" fill="#0b1016" stroke="#26323c"/>'
    s += '<path d="M1 18Q1 1 18 1H942Q959 1 959 18" fill="none" stroke="url(#accent)" stroke-width="2" opacity=".8"/>'
    s += label(30, 38, repo.get("status", "SELECTED WORK").upper(), 10, PALETTE["signal"])
    s += f'<text class="enter" x="30" y="88" font-size="29" font-weight="650" letter-spacing="-.8" fill="{PALETTE["white"]}">{esc(repo["name"])}</text>'
    desc = repo["description"]
    words, lines, current = desc.split(), [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > 94 and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > 2:
        lines = lines[:2]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    for index, line in enumerate(lines[:2]):
        s += f'<text x="30" y="{122 + index*22}" font-size="13" fill="{PALETTE["text"]}">{esc(line)}</text>'
    s += label(30, 177, "OPEN PROJECT  ↗", 9, PALETTE["signal"])
    s += '<circle cx="891" cy="91" r="34" fill="#2bb0cf" opacity=".07"/><path d="M875 91h31m-9-9 9 9-9 9" stroke="#55c6dc" fill="none" stroke-width="1.7"/>'
    return s + svg_end()

def render_stack(groups: list[dict]) -> str:
    """Render a compact, grouped capability map without badge-wall noise."""
    s = svg_start(960, 300, 2.0)
    s += label(30, 34, "ENGINEERING TOOLKIT  /  SELECTED PRACTICE", 10, PALETTE["signal"])
    columns = 3
    col_w, top = 292, 66
    for index, group in enumerate(groups[:columns]):
        x = 30 + index * 316
        s += f'<rect x="{x}" y="{top}" width="{col_w}" height="198" rx="14" fill="#0b1016" stroke="#26323c"/>'
        s += label(x+18, top+32, f'{index+1:02d}  /  {group["title"]}', 10, PALETTE["signal"])
        s += f'<path d="M{x+18} {top+48}H{x+col_w-18}" stroke="#26323c"/>'
        for row, item in enumerate(group.get("items", [])[:6]):
            y = top + 78 + row*23
            s += f'<circle cx="{x+22}" cy="{y-4}" r="3" fill="#45bad2"/>'
            s += f'<text x="{x+34}" y="{y}" font-size="13" fill="{PALETTE["text"]}">{esc(item)}</text>'
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

def write_card(path: Path, content: str) -> None:
    """Write deterministic UTF-8/LF output without trailing whitespace."""
    normalized = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
    path.write_text(normalized, encoding="utf-8", newline="\n")


def main() -> None:
    profile = load_json(PROFILE_PATH, {})
    contributions = load_json(CONTRIB_PATH, {"days": []})
    if not profile:
        raise SystemExit(f"Missing profile configuration: {PROFILE_PATH}")
    validate_profile(profile)
    CARDS.mkdir(parents=True, exist_ok=True)
    write_card(CARDS / "hero.svg", render_hero(profile))
    write_card(CARDS / "contributions.svg", render_contributions(contributions))
    write_card(CARDS / "contribution-graph.svg", render_graph(contributions))
    write_card(CARDS / "stack.svg", render_stack(profile.get("stack_groups", [])))
    for i, tile in enumerate(profile["tiles"]):
        target = CARDS / "links" / f'{tile["id"]}.svg'
        target.parent.mkdir(parents=True, exist_ok=True)
        write_card(target, render_tile(tile["title"], tile["subtitle"], tile["href"], tile["accent"], 1.8+i*.35))
    for i, repo in enumerate(profile["featured_repos"]):
        target = CARDS / "repos" / f'{repo["id"]}.svg'
        target.parent.mkdir(parents=True, exist_ok=True)
        write_card(target, render_repo(repo, 3.2+i*.45))
    # Fail closed: every generated SVG must be parseable XML.
    for path in CARDS.rglob("*.svg"):
        ET.parse(path)
    print(f"Rendered {len(list(CARDS.rglob('*.svg')))} SVG cards ({'static' if STATIC else 'animated'}).")

if __name__ == "__main__":
    main()
