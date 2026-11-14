#!/usr/bin/env python3
"""Render self-contained animated SVG cards for the @isthatleo GitHub profile.

Visual direction: luxury editorial x cyber-industrial. Graphite foundation,
restrained acid-lime signal, oversized display type, architectural geometry.
Every card is drawn at the width it is displayed at on GitHub so type never
shrinks below its intended size.
"""
from __future__ import annotations

import base64
import html
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta
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
    "bg": "#0b0d0b", "surface": "#101310", "raised": "#161a15",
    "line": "#242922", "line2": "#343a2c", "white": "#eef1e8",
    "text": "#b7bfae", "muted": "#8a9282", "faint": "#5f6759",
    "signal": "#d5ff70", "signal2": "#9dbd4a", "success": "#7fa86a",
}

# Card canvases are authored at the width GitHub renders them, so text keeps
# its designed size instead of being scaled down inside a narrow column.
HERO_SIZE = (1200, 430)
REPO_SIZE = (960, 240)
STACK_SIZE = (960, 300)
ACTIVITY_SIZE = (960, 200)
CTA_SIZE = (960, 170)


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
      .enter{{animation:rise .75s cubic-bezier(.2,.8,.2,1) {delay:.2f}s backwards}}
      .fade{{animation:reveal .7s ease {delay+.08:.2f}s backwards}}
      .shine{{animation:sweep 5s ease-in-out {delay+1.5:.2f}s infinite}}
    """
    reduce = "" if STATIC else "@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;opacity:1!important;transform:none!important}animate,animateTransform,set{display:none!important}}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
    <title>NOTLXNRD profile card</title><defs>
      <linearGradient id="editorial-bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#151713"/><stop offset=".55" stop-color="#0f110e"/><stop offset="1" stop-color="#080907"/></linearGradient>
      <linearGradient id="editorial-acid" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{PALETTE['signal']}"/><stop offset="1" stop-color="{PALETTE['signal2']}"/></linearGradient>
      <pattern id="editorial-grid" width="38" height="38" patternUnits="userSpaceOnUse"><path d="M38 0H0V38" fill="none" stroke="#d8e2c9" stroke-opacity=".05"/></pattern>
      <clipPath id="clip"><rect x="1" y="1" width="{width-2}" height="{height-2}" rx="18"/></clipPath>
    </defs><style>
      {font_css()}
      text{{font-family:Geist,'Arial',sans-serif}} .mono{{font-family:'Geist Mono',monospace}}
      {animation}
      {reduce}
    </style>
    <rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="18" fill="url(#editorial-bg)" stroke="{PALETTE['line']}"/>
    <g clip-path="url(#clip)">'''


def svg_end() -> str:
    return "</g></svg>"


def grid(width: int, height: int, opacity: float = 1) -> str:
    return f'<rect width="{width}" height="{height}" fill="url(#editorial-grid)" opacity="{opacity}"/>'


def label(x: int, y: int, text: str, size: int = 11, color: str | None = None, mono: bool = True,
          anchor: str | None = None, spacing: float | None = None) -> str:
    cls = "mono" if mono else ""
    attrs = f' letter-spacing="{spacing}"' if spacing is not None else ""
    anchor_attr = f' text-anchor="{anchor}"' if anchor else ""
    return (f'<text class="{cls}" x="{x}" y="{y}" font-size="{size}" fill="{color or PALETTE["muted"]}"'
            f'{attrs}{anchor_attr}>{esc(text)}</text>')


def rect(x: int, y: int, w: int, h: int, fill: str, rx: int = 8, opacity: float = 1) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" opacity="{opacity}"/>'


def rule(x1: int, y1: int, x2: int, y2: int, color: str = PALETTE["line"], width: int = 1, opacity: float = 1) -> str:
    return (f'<path d="M{x1} {y1}H{x2}" stroke="{color}" stroke-width="{width}"'
            f' stroke-opacity="{opacity}" fill="none"/>')


def wrap_text(text: str, limit: int, max_lines: int) -> list[str]:
    """Wrap text to a character budget, trimming overflow with a visible ellipsis."""
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > limit and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return lines


def render_hero(profile: dict) -> str:
    """Render the NOTLXNRD editorial identity banner."""
    width, height = HERO_SIZE
    name, role = profile["name"], profile["role"]
    tagline, loc = profile["tagline"], profile["location"]
    wordmark = str(profile.get("handle", "@notlxnrd")).lstrip("@").upper()
    # Keep the wordmark inside the left column whatever the handle length.
    wordmark_size = max(54, min(124, int(690 / max(len(wordmark), 1) / 0.72)))

    s = svg_start(width, height, 0)
    s += grid(width, height)
    s += '<ellipse cx="990" cy="180" rx="220" ry="150" fill="#b4d66b" opacity=".10"/>'
    s += '<path d="M790 0V430M830 0V430M870 0V430M910 0V430M950 0V430M990 0V430M1030 0V430M1070 0V430M1110 0V430" stroke="#d6e6b7" stroke-opacity=".08"/>'
    s += '<path d="M770 315L930 55H1150L990 315Z" fill="none" stroke="url(#editorial-acid)" stroke-width="2" opacity=".85"/>'
    s += '<path d="M855 315L1015 55M940 315L1100 55" stroke="#d7f19b" stroke-opacity=".26"/>'
    s += '<path d="M930 55H1150V275" fill="none" stroke="#d9f5a4" stroke-width="5"/>'
    s += '<circle cx="1040" cy="180" r="74" fill="none" stroke="#d9f5a4" stroke-opacity=".4"/><circle cx="1040" cy="180" r="44" fill="none" stroke="#d9f5a4" stroke-opacity=".65"/><circle cx="1040" cy="180" r="5" fill="#d9f5a4"/>'

    s += label(58, 62, "INDEPENDENT ENGINEERING  /  " + loc.upper(), 12, "#c5e88b", spacing=1.6)
    s += (f'<text class="enter" x="48" y="196" fill="#f0f1e9" font-size="{wordmark_size}" '
           f'font-weight="800" letter-spacing="-7">{esc(wordmark)}</text>')
    s += '<path d="M60 232H640" stroke="url(#editorial-acid)" stroke-width="3"/>'
    s += f'<text class="fade" x="62" y="278" fill="#e6e8df" font-size="25" font-weight="600">{esc(name)}</text>'
    s += f'<text class="fade" x="62" y="312" fill="#aeb3a5" font-size="19">{esc(role)}</text>'
    s += f'<text class="fade" x="62" y="344" fill="#8a9282" font-size="16">{esc(tagline)}</text>'
    s += label(62, 392, "AI SYSTEMS  /  PRODUCT ENGINEERING  /  DIGITAL INFRASTRUCTURE", 12, "#92998a", spacing=1.4)
    s += label(1140, 392, "BUILDING WITH INTENT", 12, "#c5e88b", anchor="end", spacing=1.4)
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


def render_activity(data: dict) -> str:
    """Render one compact, honest activity card for the public calendar."""
    width, height = ACTIVITY_SIZE
    stats = derive_stats(data)
    s = svg_start(width, height, 0.05)
    s += grid(width, height)
    s += label(44, 50, "GITHUB ACTIVITY  /  LAST 12 MONTHS", 11, PALETTE["signal"], spacing=1.6)

    # An empty calendar and a calendar with no public activity are both shown
    # as a waiting state. Zero-valued metrics are never presented as results.
    if not stats["days"] or stats["total"] == 0:
        s += '<path d="M44 78H360" stroke="url(#editorial-acid)" stroke-width="2"/>'
        s += (f'<text x="44" y="122" font-size="24" font-weight="650" fill="{PALETTE["white"]}">'
              'WAITING FOR VERIFIED GITHUB ACTIVITY</text>')
        s += (f'<text x="44" y="156" font-size="15" fill="{PALETTE["text"]}">'
              'GitHub reports no public contributions in this window. Private activity is not exposed, '
              'and no metrics are fabricated.</text>')
        return s + svg_end()

    metrics = [("CURRENT STREAK", f'{stats["current_streak"]} days'),
               ("ACTIVE DAYS", str(stats["active_days"])),
               ("BUSIEST DAY", f'{stats["busiest_date"]} · {stats["busiest_count"]}')]
    for i, (key, val) in enumerate(metrics):
        x = 44 + i * 300
        s += label(x, 88, key, 10, PALETTE["muted"], spacing=1.4)
        s += f'<text x="{x}" y="126" font-size="30" font-weight="650" fill="{PALETTE["white"]}">{esc(val)}</text>'
    months = stats["months"]
    maxv = max((v for _, v in months), default=1) or 1
    chart_x, base_y, bar_w, gap = 46, 178, 56, 20
    for i, (month, value) in enumerate(months):
        h = max(4, int(44 * value / maxv))
        x = chart_x + i * (bar_w + gap)
        s += rect(x, base_y - h, bar_w, h, PALETTE["signal"] if value == maxv else PALETTE["raised"], 3)
        s += label(x, 194, month.split()[0].upper(), 9, PALETTE["faint"], spacing=1.2)
    return s + svg_end()


def render_stack(groups: list[dict]) -> str:
    """Render a grouped capability map with legible, full-size type."""
    width, height = STACK_SIZE
    s = svg_start(width, height, 0.10)
    s += grid(width, height)
    s += label(44, 50, "ENGINEERING TOOLKIT  /  SELECTED PRACTICE", 11, PALETTE["signal"], spacing=1.6)
    columns = 3
    col_w, gap, top = 288, 12, 84
    for index, group in enumerate(groups[:columns]):
        x = 44 + index * (col_w + gap)
        s += label(x, top, f'{index+1:02d}', 12, PALETTE["signal"], spacing=1.6)
        s += f'<text x="{x + 34}" y="{top}" font-size="17" font-weight="650" fill="{PALETTE["white"]}">{esc(group["title"])}</text>'
        s += rule(x, top + 18, x + col_w, top + 18, PALETTE["line2"])
        for row, item in enumerate(group.get("items", [])[:6]):
            y = top + 52 + row * 30
            s += f'<path d="M{x} {y - 5}h12" stroke="{PALETTE["signal"]}" stroke-width="2" stroke-opacity=".8"/>'
            s += f'<text x="{x + 26}" y="{y}" font-size="16" fill="{PALETTE["text"]}">{esc(item)}</text>'
    return s + svg_end()


def render_repo(repo: dict, delay: float, index: int = 1) -> str:
    """Render a project as an editorial case-study row."""
    width, height = REPO_SIZE
    s = svg_start(width, height, delay)
    s += grid(width, height)
    s += label(44, 52, repo.get("status", "SELECTED WORK").upper(), 11, PALETTE["signal"], spacing=1.6)
    s += (f'<text class="enter" x="44" y="110" font-size="38" font-weight="700" letter-spacing="-.8" '
           f'fill="{PALETTE["white"]}">{esc(repo["name"])}</text>')
    for row, line in enumerate(wrap_text(repo["description"], 92, 2)):
        s += f'<text x="44" y="{148 + row * 26}" font-size="17" fill="{PALETTE["text"]}">{esc(line)}</text>'
    s += (f'<text x="{width - 44}" y="156" font-size="86" font-weight="800" letter-spacing="-5" '
           f'fill="{PALETTE["signal"]}" opacity=".09" text-anchor="end">{index:02d}</text>')
    s += rule(44, 208, width - 44, 208, PALETTE["line"])
    s += label(44, 230, f'{index:02d}  /  SELECTED WORK', 10, PALETTE["faint"], spacing=1.4)
    s += label(width - 44, 230, "OPEN PROJECT  ↗", 10, PALETTE["signal"], anchor="end", spacing=1.4)
    return s + svg_end()


def render_cta(tiles: list[dict]) -> str:
    """Render the closing call-to-action band with the configured destinations."""
    width, height = CTA_SIZE
    s = svg_start(width, height, 0.15)
    s += grid(width, height)
    s += label(44, 52, "HAVE A GOOD PROBLEM?", 11, PALETTE["signal"], spacing=1.6)
    s += (f'<text x="44" y="106" font-size="30" font-weight="650" fill="{PALETTE["white"]}">'
          'Let’s build something useful.</text>')
    for i, tile in enumerate(tiles[:2]):
        x = 520 + i * 200
        host = urlparse(tile["href"]).netloc.replace("www.", "")
        s += rule(x, 74, x + 172, 74, PALETTE["line2"])
        s += f'<text x="{x}" y="104" font-size="18" font-weight="650" fill="{PALETTE["white"]}">{esc(tile["title"])}</text>'
        s += f'<text x="{x}" y="128" font-size="12" fill="{PALETTE["muted"]}">{esc(host)}</text>'
        s += label(x, 150, "OPEN  ↗", 10, PALETTE["signal"], spacing=1.4)
    return s + svg_end()


def write_card(path: Path, content: str) -> None:
    """Write deterministic UTF-8/LF output without trailing whitespace."""
    normalized = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
    path.write_text(normalized, encoding="utf-8", newline="\n")


def prune_cards(expected: set[Path]) -> list[Path]:
    """Remove SVGs the renderer no longer produces so the manifest stays exact."""
    pruned = []
    for path in sorted(CARDS.rglob("*.svg")):
        if path not in expected:
            path.unlink()
            pruned.append(path)
    return pruned


def main() -> None:
    profile = load_json(PROFILE_PATH, {})
    contributions = load_json(CONTRIB_PATH, {"days": []})
    if not profile:
        raise SystemExit(f"Missing profile configuration: {PROFILE_PATH}")
    validate_profile(profile)
    CARDS.mkdir(parents=True, exist_ok=True)
    write_card(CARDS / "hero.svg", render_hero(profile))
    write_card(CARDS / "activity.svg", render_activity(contributions))
    write_card(CARDS / "stack.svg", render_stack(profile.get("stack_groups", [])))
    write_card(CARDS / "cta.svg", render_cta(profile.get("tiles", [])))
    for i, repo in enumerate(profile["featured_repos"]):
        target = CARDS / "repos" / f'{repo["id"]}.svg'
        target.parent.mkdir(parents=True, exist_ok=True)
        write_card(target, render_repo(repo, 0.20 + i * 0.06, i + 1))
    # Fail closed: every generated SVG must be parseable XML.
    for path in CARDS.rglob("*.svg"):
        ET.parse(path)
    pruned = prune_cards({
        CARDS / "hero.svg", CARDS / "activity.svg", CARDS / "stack.svg", CARDS / "cta.svg",
        *(CARDS / "repos" / f'{repo["id"]}.svg' for repo in profile["featured_repos"]),
    })
    for path in pruned:
        print(f"Pruned stale asset: {path.relative_to(ROOT).as_posix()}")
    print(f"Rendered {len(list(CARDS.rglob('*.svg')))} SVG cards ({'static' if STATIC else 'animated'}).")


if __name__ == "__main__":
    main()
