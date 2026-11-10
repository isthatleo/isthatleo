#!/usr/bin/env python3
"""Fetch the public GitHub contribution calendar into normalized JSON."""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USERNAME = "isthatleo"
URL = f"https://github.com/users/{USERNAME}/contributions"

class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = []
    def handle_starttag(self, tag, attrs):
        if tag != "td":
            return
        values = dict(attrs)
        if "data-date" not in values:
            return
        try:
            count = int(values.get("data-count", "0"))
        except ValueError:
            count = 0
        self.days.append({
            "date": values["data-date"],
            "count": count,
            "level": int(values.get("data-level", "0") or 0),
        })

def main():
    request = Request(URL, headers={"User-Agent": "notlxnrd-profile-card/1.0"})
    with urlopen(request, timeout=30) as response:
        source = response.read().decode("utf-8", "replace")
    parser = CalendarParser()
    parser.feed(source)
    if not parser.days:
        raise SystemExit("No contribution calendar cells were parsed; refusing to overwrite existing data.")
    output = {
        "schema_version": 1,
        "username": USERNAME,
        "source": URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "days": parser.days,
    }
    target = ROOT / "data" / "contributions.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(parser.days)} contribution days to {target}")

if __name__ == "__main__":
    main()
