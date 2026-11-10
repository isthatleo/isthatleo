import importlib.util
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "render_readme_cards.py"
spec = importlib.util.spec_from_file_location("renderer", SCRIPT)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

def test_stats_are_derived_from_fixture():
    data = {"days": [
        {"date":"2026-01-01","count":2},
        {"date":"2026-01-02","count":0},
        {"date":"2026-02-01","count":3},
    ]}
    stats = renderer.derive_stats(data)
    assert stats["total"] == 5
    assert stats["active_days"] == 2
    assert stats["busiest_count"] == 3
    assert stats["months"] == [("Jan 2026", 2), ("Feb 2026", 3)]

def test_xml_escaping():
    assert renderer.esc("A & B <C>") == "A &amp; B &lt;C&gt;"

def test_svg_is_well_formed():
    ET.fromstring(renderer.render_hero({"name":"Leonard & Co","role":"Engineer","tagline":"Build <ship>","location":"Kampala"}))
