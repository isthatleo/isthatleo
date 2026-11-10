import importlib.util
import json
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

def test_stack_card_is_well_formed():
    svg = renderer.render_stack([
        {"title": "PRODUCT", "items": ["TypeScript", "React"]},
        {"title": "SYSTEMS", "items": ["Rust", "Python"]},
        {"title": "PRACTICE", "items": ["Testing", "Architecture"]},
    ])
    ET.fromstring(svg)
    assert "TypeScript" in svg
    assert "Architecture" in svg

def test_empty_contributions_are_not_rendered_as_zero_metrics():
    svg = renderer.render_contributions({"days": []})
    ET.fromstring(svg)
    assert "WAITING FOR VERIFIED GITHUB ACTIVITY" in svg
    assert "CURRENT STREAK" not in svg

def test_readme_image_references_exist():
    readme = (SCRIPT.parents[1] / "README.md").read_text(encoding="utf-8")
    import re
    references = re.findall(r'src="./(cards/[^"]+)"', readme)
    assert references
    for reference in references:
        assert (SCRIPT.parents[1] / reference).is_file(), reference
