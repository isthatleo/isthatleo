#!/usr/bin/env python3
"""Fetch the public GitHub contribution calendar into normalized JSON."""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USERNAME = "isthatleo"
URL = f"https://github.com/users/{USERNAME}/contributions"
TARGET = ROOT / "data" / "contributions.json"


class CalendarParser(HTMLParser):
    """Extract valid contribution cells without trusting page attributes.

    GitHub currently omits ``data-count`` and exposes the count in the
    following ``<tool-tip>`` text, so support both markup shapes.
    """

    def __init__(self) -> None:
        super().__init__()
        self.days: list[dict] = []
        self._pending: dict | None = None
        self._in_tooltip = False
        self._tooltip_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tool-tip":
            self._in_tooltip = True
            self._tooltip_text = []
            return
        if tag != "td":
            return
        self._pending = None
        values = dict(attrs)
        raw_date = values.get("data-date")
        if not raw_date:
            return
        try:
            parsed_date = date.fromisoformat(raw_date)
            level = int(values.get("data-level") or 0)
        except (TypeError, ValueError):
            return
        if not 0 <= level <= 4:
            return
        count: int | None = None
        raw_count = values.get("data-count")
        if raw_count is not None:
            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                return
            if count < 0:
                return
        self._pending = {
            "date": parsed_date.isoformat(),
            "count": count,
            "level": level,
        }
        if count is not None:
            self.days.append({
                "date": self._pending["date"],
                "count": count,
                "level": level,
            })
            self._pending = None

    def handle_data(self, data: str) -> None:
        if self._in_tooltip:
            self._tooltip_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "tool-tip" or not self._in_tooltip:
            return
        self._in_tooltip = False
        if self._pending is None or self._pending["count"] is not None:
            return
        text = " ".join("".join(self._tooltip_text).split())
        if "No contributions" in text:
            count = 0
        else:
            match = re.search(r"(\d+)\s+contributions?\b", text)
            if not match:
                return
            count = int(match.group(1))
        self.days.append({
            "date": self._pending["date"],
            "count": count,
            "level": self._pending["level"],
        })
        self._pending = None

    def close(self) -> None:
        super().close()
        self._pending = None
        self._in_tooltip = False


def parse_calendar(source: str) -> list[dict]:
    parser = CalendarParser()
    parser.feed(source)
    parser.close()
    # GitHub's calendar should have one cell per date. Reject duplicates rather
    # than silently double-counting if the source markup changes unexpectedly.
    dates = [item["date"] for item in parser.days]
    if len(dates) != len(set(dates)):
        raise ValueError("Duplicate contribution dates found in source HTML.")
    return parser.days


def fetch_calendar() -> list[dict]:
    request = Request(URL, headers={"User-Agent": "notlxnrd-profile-card/1.0"})
    with urlopen(request, timeout=30) as response:
        source = response.read().decode("utf-8", "replace")
    days = parse_calendar(source)
    if not days:
        raise ValueError("No valid contribution calendar cells were parsed.")
    return days


def write_contributions(days: list[dict], target: Path = TARGET) -> None:
    """Atomically replace the dataset only after a valid non-empty fetch."""
    if not days:
        raise ValueError("Refusing to write an empty contribution dataset.")
    output = {
        "schema_version": 1,
        "username": USERNAME,
        "source": URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "days": days,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=target.parent, delete=False,
            prefix=f".{target.name}.", suffix=".tmp",
        ) as handle:
            json.dump(output, handle, indent=2)
            handle.write("\n")
            temp_path = Path(handle.name)
        os.replace(temp_path, target)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def main() -> None:
    days = fetch_calendar()
    write_contributions(days)
    print(f"Saved {len(days)} contribution days to {TARGET}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"Contribution refresh failed: {exc}") from exc
