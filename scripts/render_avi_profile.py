#!/usr/bin/env python3
"""Generate the NOTLXNRD GitHub profile using the animated SVG-card approach.

CI runs this renderer after profile source or test changes.

The composition follows Avi Vashishta's public animated-card concept while
using an original NOTLXNRD identity, project data, and contribution palette.
All SVGs are self-contained and safe to embed through GitHub README image tags.
"""
from __future__ import annotations

import base64
import html
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data" / "profile.json"
CONTRIBUTIONS = ROOT / "data" / "contributions.json"
CARDS = ROOT / "cards"
STATIC = os.getenv("STATIC", "0") == "1"

PAPER = "#f4f1e9"
INK = "#20242b"
MUTED = "#66707b"
LINE = "#d9d5ca"
BLUE = "#3478f6"
RED = "#e36c62"
YELLOW = "#e8b84b"
GREEN_LEVELS = ["#e8e8e8", "#9be9a8", "#40c463", "#30a14e", "#216e39"]

def esc(value: object) -> str:
    return html.escape(str(value), quote=True)

def read_json(path: Path, default: object) -> object:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def validate_url(value: object, field: str) -> None:
    parsed = urlparse(value) if isinstance(value, str) else None
    if not parsed or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute HTTP(S) URL")

def validate(profile: dict) -> None:
    for key in ("name", "handle", "role", "tagline", "location", "website"):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            raise ValueError(f"profile.{key} must be a non-empty string")
    validate_url(profile["website"], "profile.website")
    repos = profile.get("featured_repos")
    if not isinstance(repos, list) or not repos:
        raise ValueError("profile.featured_repos must be a non-empty list")
    ids: set[str] = set()
    for i, repo in enumerate(repos):
        if not isinstance(repo, dict):
            raise ValueError(f"featured_repos[{i}] must be an object")
        for key in ("id", "name", "description", "url"):
            if not isinstance(repo.get(key), str) or not repo[key].strip():
                raise ValueError(f"featured_repos[{i}].{key} must be non-empty")
        if repo["id"] in ids or not repo["id"].replace("-", "").isalnum():
            raise ValueError(f"featured_repos[{i}].id must be unique and filesystem-safe")
        ids.add(repo["id"])
        validate_url(repo["url"], f"featured_repos[{i}].url")
    tiles = profile.get("tiles")
    if not isinstance(tiles, list) or len(tiles) != 3:
        raise ValueError("profile.tiles must contain exactly three linked tiles")
    tile_ids: set[str] = set()
    for i, tile in enumerate(tiles):
        for key in ("id", "title", "subtitle", "href", "accent"):
            if not isinstance(tile.get(key), str) or not tile[key].strip():
                raise ValueError(f"tiles[{i}].{key} must be non-empty")
        if tile["id"] in tile_ids or not tile["id"].replace("-", "").isalnum():
            raise ValueError(f"tiles[{i}].id must be unique and filesystem-safe")
        tile_ids.add(tile["id"])
        validate_url(tile["href"], f"tiles[{i}].href")
        if tile["accent"] not in {BLUE, RED, YELLOW}:
            raise ValueError(f"tiles[{i}].accent must use one of the three brand accents")

def font_css() -> str:
    """Embed optional local fonts; no remote font requests are made."""
    rules: list[str] = []
    candidates = [
        ("Instrument Serif", "InstrumentSerif-Regular.woff"),
        ("Geist", "Geist-Regular.woff"),
        ("Geist Mono", "GeistMono-Regular.woff"),
    ]
    for family, filename in candidates:
        source = ROOT / "fonts" / filename
        if not source.exists():
            continue
        subset = source.with_name(source.stem + "-subset.woff")
        try:
            if not subset.exists() or subset.stat().st_mtime < source.stat().st_mtime:
                subprocess.run(
                    ["pyftsubset", str(source), f"--output-file={subset}", "--flavor=woff",
                     "--unicodes=U+0020-007E,U+00A0-00FF"],
                    check=True, capture_output=True,
                )
            encoded = base64.b64encode(subset.read_bytes()).decode("ascii")
            rules.append(
                f"@font-face{{font-family:'{family}';src:url(data:font/woff;base64,{encoded}) format('woff')}}"
            )
        except (OSError, subprocess.CalledProcessError):
            continue
    return "".join(rules)

FONTS = ""

def svg_open(width: int, height: int, title: str, delay: float = 0) -> str:
    motion = "" if STATIC else """
      @keyframes enter{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
      @keyframes print{from{opacity:0}to{opacity:1}}
      @keyframes sweep{0%{transform:translateX(-130%)}100%{transform:translateX(230%)}}
      .enter{animation:enter .7s cubic-bezier(.2,.75,.25,1) both}
      .print{animation:print .5s ease both}
      .shine{animation:sweep 6s ease-in-out 2s infinite}
    """
    reduced = "" if STATIC else "@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;opacity:1!important;transform:none!important}}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
<title>{esc(title)}</title>
<defs>
  <pattern id="paper-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="{INK}" stroke-opacity=".035"/></pattern>
  <linearGradient id="blue-wash" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{BLUE}" stop-opacity=".15"/><stop offset="1" stop-color="{BLUE}" stop-opacity="0"/></linearGradient>
  <clipPath id="frame"><rect x="1" y="1" width="{width-2}" height="{height-2}" rx="16"/></clipPath>
</defs>
<style>
{FONTS}
text{{font-family:Geist,Arial,sans-serif;fill:{INK}}}
.serif{{font-family:'Instrument Serif',Georgia,serif}}
.mono{{font-family:'Geist Mono',monospace}}
{motion}
{reduced}
</style>
<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="16" fill="{PAPER}" stroke="{LINE}"/>
<g clip-path="url(#frame)">'''

def svg_close() -> str:
    return "</g></svg>"

def text(x: int, y: int, value: str, size: int = 14, fill: str = INK,
         weight: int = 400, cls: str = "", anchor: str = "start") -> str:
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'class="{cls}" text-anchor="{anchor}">{esc(value)}</text>')

def stats_for(data: dict) -> dict:
    parsed: list[tuple[date, int, int]] = []
    for item in data.get("days", []):
        try:
            day = date.fromisoformat(item["date"])
            count = int(item["count"])
            level = int(item.get("level", 0))
            if count >= 0 and 0 <= level <= 4:
                parsed.append((day, count, level))
        except (KeyError, TypeError, ValueError):
            continue
    parsed.sort(key=lambda row: row[0])
    counts = {day: count for day, count, _ in parsed}
    today = date.today()
    cursor = today if counts.get(today, 0) else today - timedelta(days=1)
    streak = 0
    while counts.get(cursor, 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)
    monthly: dict[tuple[int, int], int] = defaultdict(int)
    for day, count, _ in parsed:
        monthly[(day.year, day.month)] += count
    busiest = max(parsed, key=lambda row: row[1], default=(None, 0, 0))
    return {
        "days": parsed,
        "total": sum(row[1] for row in parsed),
        "active": sum(1 for row in parsed if row[1] > 0),
        "streak": streak,
        "busiest_date": busiest[0].isoformat() if busiest[0] else "—",
        "busiest_count": busiest[1],
        "months": list(monthly.items())[-12:],
    }

def render_hero(profile: dict) -> str:
    width, height = 960, 330
    s = svg_open(width, height, "NOTLXNRD — Leonard Lomude, software engineer and product builder")
    s += '<rect x="0" y="0" width="960" height="330" fill="url(#paper-grid)"/>'
    s += f'<circle cx="806" cy="132" r="108" fill="url(#blue-wash)"/>'
    s += f'<path d="M700 35H910V245H700Z" fill="none" stroke="{LINE}" stroke-width="1"/>'
    s += f'<path d="M725 60H885M725 82H850M725 104H870M725 126H830" stroke="{BLUE}" stroke-width="2" stroke-opacity=".5"/>'
    # An original monogram graphic stands in for a portrait; no likeness is fabricated.
    s += f'<text x="806" y="198" font-size="92" font-weight="700" letter-spacing="-9" text-anchor="middle" fill="{BLUE}" opacity=".9">NL</text>'
    s += text(54, 58, "INDEPENDENT SOFTWARE ENGINEER  /  " + profile["location"].upper(), 11, MUTED, 600, "mono")
    s += f'<text class="enter serif" x="48" y="154" font-size="76" font-weight="400" letter-spacing="-2">{esc(profile["handle"].upper())}</text>'
    s += f'<path d="M55 180H630" stroke="{BLUE}" stroke-width="3"/>'
    s += text(58, 220, profile["name"], 24, INK, 650)
    s += text(58, 252, profile["role"], 16, MUTED, 500)
    s += text(58, 282, profile["tagline"], 14, MUTED, 400)
    s += text(58, 310, "AI SYSTEMS  ·  PRODUCT ENGINEERING  ·  SOFTWARE", 10, BLUE, 600, "mono")
    s += svg_close()
    return s

def render_graph(data: dict) -> str:
    width, height = 960, 180
    stats = stats_for(data)
    s = svg_open(width, height, "GitHub contribution graph")
    s += text(38, 36, "CONTRIBUTIONS", 11, BLUE, 700, "mono")
    s += text(922, 36, f'{stats["total"]:,} PUBLIC CONTRIBUTIONS', 11, MUTED, 600, "mono", "end")
    if not stats["days"]:
        s += text(38, 94, "Contribution data is not available yet.", 18, MUTED, 400)
        return s + svg_close()
    by_day = {day: (count, level) for day, count, level in stats["days"]}
    first = stats["days"][0][0]
    start = first - timedelta(days=first.weekday())
    last = stats["days"][-1][0]
    weeks = min(53, ((last - start).days // 7) + 1)
    cell, gap, x0, y0 = 12, 4, 38, 58
    for week in range(weeks):
        for weekday in range(7):
            day = start + timedelta(days=week * 7 + weekday)
            if day > last:
                continue
            count, level = by_day.get(day, (0, 0))
            x, y = x0 + week * (cell + gap), y0 + weekday * (cell + gap)
            color = GREEN_LEVELS[level]
            delay = (week * 7 + weekday) * 0.006
            style = "" if STATIC else f' style="animation-delay:{delay:.3f}s"'
            s += (f'<rect class="{"print" if not STATIC else ""}" x="{x}" y="{y}" width="{cell}" height="{cell}" '
                  f'rx="3" fill="{color}"{style}><title>{day.isoformat()}: {count} contributions</title></rect>')
    s += text(38, 166, "LESS", 9, MUTED, 500, "mono")
    for i, color in enumerate(GREEN_LEVELS):
        s += f'<rect x="{82+i*17}" y="155" width="11" height="11" rx="2" fill="{color}"/>'
    s += text(184, 166, "MORE", 9, MUTED, 500, "mono")
    return s + svg_close()

def render_activity(data: dict) -> str:
    width, height = 960, 260
    stats = stats_for(data)
    s = svg_open(width, height, "Monthly GitHub activity and contribution statistics")
    s += text(38, 38, "THE YEAR IN CODE", 11, BLUE, 700, "mono")
    metrics = [
        ("CURRENT STREAK", f'{stats["streak"]} days'),
        ("ACTIVE DAYS", str(stats["active"])),
        ("BUSIEST DAY", f'{stats["busiest_date"]} · {stats["busiest_count"]}'),
    ]
    for i, (label, value) in enumerate(metrics):
        x = 38 + i * 300
        s += text(x, 78, label, 9, MUTED, 700, "mono")
        s += text(x, 112, value, 24, INK, 650)
    months = stats["months"]
    if not months or stats["total"] == 0:
        s += text(38, 176, "Waiting for verified public contribution activity.", 15, MUTED)
        return s + svg_close()
    max_value = max(value for _, value in months) or 1
    x0, base, bar_w, gap = 40, 218, 48, 27
    for i, ((year, month), value) in enumerate(months):
        x = x0 + i * (bar_w + gap)
        bar_h = max(3, int(64 * value / max_value))
        color = BLUE if value == max_value else "#b9c8e8"
        delay = i * .07
        style = "" if STATIC else f' style="animation-delay:{delay:.2f}s"'
        s += f'<rect class="{"enter" if not STATIC else ""}" x="{x}" y="{base-bar_h}" width="{bar_w}" height="{bar_h}" rx="4" fill="{color}"{style}><title>{year}-{month:02d}: {value} contributions</title></rect>'
        s += text(x + bar_w//2, 242, date(year, month, 1).strftime("%b").upper(), 9, MUTED, 600, "mono", "middle")
    return s + svg_close()

def render_tile(tile: dict) -> str:
    width, height = 300, 190
    accent = tile["accent"]
    s = svg_open(width, height, tile["title"] + " — " + tile["subtitle"])
    s += f'<rect x="0" y="0" width="300" height="190" fill="{PAPER}"/>'
    s += f'<path d="M22 22H278" stroke="{LINE}"/>'
    s += text(24, 54, tile["title"], 23, INK, 700)
    s += text(24, 82, tile["subtitle"], 11, MUTED, 400)
    s += f'<circle cx="260" cy="148" r="18" fill="{accent}" opacity=".16"/>'
    s += f'<path d="M250 148H270M263 141L270 148L263 155" stroke="{accent}" stroke-width="2" fill="none"/>'
    s += f'<path d="M24 148H190" stroke="{accent}" stroke-width="3"/>'
    s += text(24, 172, "EXPLORE  ↗", 9, accent, 700, "mono")
    return s + svg_close()

def render_repo(repo: dict, index: int) -> str:
    width, height = 960, 184
    s = svg_open(width, height, repo["name"] + " featured project")
    s += f'<rect x="0" y="0" width="{width}" height="{height}" fill="url(#paper-grid)"/>'
    s += text(36, 36, f'{index:02d}  /  {repo.get("status", "FEATURED PROJECT")}', 10, BLUE, 700, "mono")
    s += f'<text class="serif" x="34" y="91" font-size="38" fill="{INK}">{esc(repo["name"])}</text>'
    s += text(38, 123, repo["description"][:112], 13, MUTED, 400)
    s += text(38, 158, "OPEN PROJECT  ↗", 10, BLUE, 700, "mono")
    s += f'<path d="M790 24V160M810 24V160M830 24V160M850 24V160M870 24V160M890 24V160" stroke="{LINE}" stroke-width="1"/>'
    s += f'<circle cx="840" cy="92" r="32" fill="none" stroke="{repo.get("accent", BLUE)}" stroke-width="2"/>'
    s += f'<circle cx="840" cy="92" r="6" fill="{repo.get("accent", BLUE)}"/>'
    return s + svg_close()

def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
    path.write_text(normalized, encoding="utf-8", newline="\n")

def main() -> None:
    global FONTS
    profile = read_json(PROFILE, {})
    contributions = read_json(CONTRIBUTIONS, {"days": []})
    if not profile:
        raise SystemExit(f"Missing profile configuration: {PROFILE}")
    validate(profile)
    FONTS = font_css()
    CARDS.mkdir(parents=True, exist_ok=True)
    expected: set[Path] = set()
    outputs: list[tuple[Path, str]] = [
        (CARDS / "hero.svg", render_hero(profile)),
        (CARDS / "contribution-graph.svg", render_graph(contributions)),
        (CARDS / "activity.svg", render_activity(contributions)),
    ]
    for tile in profile["tiles"]:
        outputs.append((CARDS / "tiles" / f'{tile["id"]}.svg', render_tile(tile)))
    for index, repo in enumerate(profile["featured_repos"], 1):
        outputs.append((CARDS / "repos" / f'{repo["id"]}.svg', render_repo(repo, index)))
    for path, content in outputs:
        write(path, content)
        expected.add(path)
    for svg in CARDS.rglob("*.svg"):
        if svg not in expected:
            svg.unlink()
    for svg in sorted(expected):
        ET.parse(svg)
    print(f"Rendered and XML-validated {len(expected)} SVG assets ({'static' if STATIC else 'animated'}).")

if __name__ == "__main__":
    main()
