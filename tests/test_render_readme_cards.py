import importlib.util
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "render_readme_cards.py"
FETCH_SCRIPT = ROOT / "scripts" / "fetch_contributions.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


renderer = load_module("renderer", SCRIPT)
fetcher = load_module("fetcher", FETCH_SCRIPT)


def test_stats_are_derived_from_fixture():
    data = {"days": [
        {"date": "2026-01-01", "count": 2},
        {"date": "2026-01-02", "count": 0},
        {"date": "2026-02-01", "count": 3},
    ]}
    stats = renderer.derive_stats(data)
    assert stats["total"] == 5
    assert stats["active_days"] == 2
    assert stats["busiest_count"] == 3
    assert stats["months"] == [("Jan 2026", 2), ("Feb 2026", 3)]


def test_xml_escaping():
    assert renderer.esc("A & B <C>") == "A &amp; B &lt;C&gt;"


def test_svg_is_well_formed():
    svg = renderer.render_hero({
        "name": "Leonard & Co", "role": "Engineer",
        "tagline": "Build <ship>", "location": "Kampala",
    })
    ET.fromstring(svg)
    assert "Leonard &amp; Co" in svg
    assert "Build &lt;ship&gt;" in svg


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
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    references = re.findall(r'src="./(cards/[^"]+)"', readme)
    assert references
    for reference in references:
        assert (ROOT / reference).is_file(), reference


def test_calendar_parser_extracts_valid_cells_and_skips_malformed_values():
    html = """
    <table>
      <td data-date="2026-11-08" data-count="4" data-level="3"></td>
      <td data-date="not-a-date" data-count="9" data-level="4"></td>
      <td data-date="2026-11-09" data-count="-2" data-level="1"></td>
      <td data-date="2026-11-10" data-count="2" data-level="9"></td>
      <td data-date="2026-11-11" data-count="0" data-level="0"></td>
    </table>
    """
    assert fetcher.parse_calendar(html) == [
        {"date": "2026-11-08", "count": 4, "level": 3},
        {"date": "2026-11-11", "count": 0, "level": 0},
    ]


def test_calendar_parser_rejects_duplicate_dates():
    html = """
    <td data-date="2026-11-08" data-count="1" data-level="1"></td>
    <td data-date="2026-11-08" data-count="2" data-level="2"></td>
    """
    import pytest
    with pytest.raises(ValueError, match="Duplicate"):
        fetcher.parse_calendar(html)


def test_empty_fetch_cannot_overwrite_existing_contributions(tmp_path):
    target = tmp_path / "contributions.json"
    original = '{"days":[{"date":"2026-11-01","count":1}]}\n'
    target.write_text(original, encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="empty"):
        fetcher.write_contributions([], target)
    assert target.read_text(encoding="utf-8") == original


def test_fetch_write_is_valid_json_and_atomic_output_shape(tmp_path):
    target = tmp_path / "data" / "contributions.json"
    days = [{"date": "2026-11-10", "count": 3, "level": 2}]
    fetcher.write_contributions(days, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["username"] == "isthatleo"
    assert payload["fetched_at"]
    assert payload["days"] == days
    assert list(target.parent.iterdir()) == [target]


def test_every_generated_asset_is_well_formed_and_matches_manifest(tmp_path, monkeypatch):
    profile = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    contributions = {"days": []}
    monkeypatch.setattr(renderer, "ROOT", tmp_path)
    monkeypatch.setattr(renderer, "DATA", tmp_path / "data")
    monkeypatch.setattr(renderer, "CARDS", tmp_path / "cards")
    monkeypatch.setattr(renderer, "PROFILE_PATH", tmp_path / "data" / "profile.json")
    monkeypatch.setattr(renderer, "CONTRIB_PATH", tmp_path / "data" / "contributions.json")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (tmp_path / "data" / "contributions.json").write_text(json.dumps(contributions), encoding="utf-8")
    renderer.main()
    actual = {path.relative_to(tmp_path).as_posix() for path in (tmp_path / "cards").rglob("*.svg")}
    expected = {
        "cards/hero.svg", "cards/contributions.svg", "cards/contribution-graph.svg",
        "cards/stack.svg", "cards/links/build.svg", "cards/links/systems.svg",
        "cards/repos/nancy.svg", "cards/repos/notlxnrd-os.svg",
        "cards/repos/roxan.svg", "cards/repos/trade-titans.svg",
    }
    assert actual == expected
    for path in (tmp_path / "cards").rglob("*.svg"):
        ET.parse(path)


def test_static_and_animated_svg_modes(monkeypatch):
    monkeypatch.setattr(renderer, "STATIC", True)
    static_svg = renderer.svg_start(100, 100)
    assert "@keyframes" not in static_svg
    monkeypatch.setattr(renderer, "STATIC", False)
    animated_svg = renderer.svg_start(100, 100)
    assert "@keyframes" in animated_svg
    assert "prefers-reduced-motion:reduce" in animated_svg
