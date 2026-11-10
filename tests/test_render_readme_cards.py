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


def test_readme_project_destinations_match_profile_configuration():
    profile = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for project in profile["featured_repos"]:
        expected = f'<a href="{project["url"]}"><img src="./cards/repos/{project["id"]}.svg"'
        assert expected in readme, f"README destination mismatch for {project['id']}"


def test_profile_configuration_accepts_repository_source_data():
    profile = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    renderer.validate_profile(profile)


def test_profile_configuration_rejects_unsafe_project_ids():
    profile = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    profile["featured_repos"][0]["id"] = "../outside"
    import pytest
    with pytest.raises(ValueError, match="unsafe path"):
        renderer.validate_profile(profile)


def test_profile_configuration_rejects_duplicate_tile_ids():
    profile = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    profile["tiles"][1]["id"] = profile["tiles"][0]["id"]
    import pytest
    with pytest.raises(ValueError, match="Duplicate tile"):
        renderer.validate_profile(profile)


def test_profile_configuration_rejects_non_http_project_urls():
    profile = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    profile["featured_repos"][0]["url"] = "javascript:alert(1)"
    import pytest
    with pytest.raises(ValueError, match="HTTP"):
        renderer.validate_profile(profile)


def test_profile_configuration_rejects_invalid_tile_colours():
    profile = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    profile["tiles"][0]["accent"] = "url(javascript:alert(1))"
    import pytest
    with pytest.raises(ValueError, match="hex colour"):
        renderer.validate_profile(profile)


def test_project_description_truncation_is_visible_and_escaped():
    svg = renderer.render_repo({
        "id": "sample",
        "name": "A & B",
        "description": "A long description with enough words to wrap across more than two lines " * 5,
        "status": "ACTIVE",
    }, 0)
    ET.fromstring(svg)
    assert "A &amp; B" in svg
    assert "…" in svg


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


def test_calendar_parser_uses_tooltip_counts_when_data_count_is_absent():
    html = """
    <td data-date="2026-11-08" data-level="3"></td>
    <tool-tip>4 contributions on November 8th.</tool-tip>
    <td data-date="2026-11-09" data-level="1"></td>
    <tool-tip>1 contribution on November 9th.</tool-tip>
    <td data-date="2026-11-10" data-level="0"></td>
    <tool-tip>No contributions on November 10th.</tool-tip>
    <td data-date="2026-11-11" data-level="2"></td>
    <tool-tip>unexpected markup</tool-tip>
    """
    assert fetcher.parse_calendar(html) == [
        {"date": "2026-11-08", "count": 4, "level": 3},
        {"date": "2026-11-09", "count": 1, "level": 1},
        {"date": "2026-11-10", "count": 0, "level": 0},
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


def test_network_failure_does_not_touch_existing_dataset(tmp_path, monkeypatch):
    target = tmp_path / "contributions.json"
    original = '{"trusted":"existing-data"}\n'
    target.write_text(original, encoding="utf-8")
    monkeypatch.setattr(fetcher, "TARGET", target)

    def fail_fetch():
        raise OSError("network unavailable")

    monkeypatch.setattr(fetcher, "fetch_calendar", fail_fetch)
    import pytest
    with pytest.raises(OSError, match="network unavailable"):
        fetcher.main()
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


def test_editorial_hero_uses_the_new_visual_identity():
    profile = {
        "name": "NOTLXNRD",
        "role": "Software engineer. Systems thinker.",
        "tagline": "I turn complex ideas into useful, engineered products.",
        "location": "Kampala, Uganda",
    }
    svg = renderer.render_hero(profile)
    ET.fromstring(svg)
    assert "editorial-bg" in svg
    assert "editorial-acid" in svg
    assert "INDEPENDENT ENGINEERING" in svg
    assert "2bb0cf" not in svg
