import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "render_avi_profile.py"

def load_renderer():
    spec = importlib.util.spec_from_file_location("avi_profile_renderer", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module

renderer = load_renderer()

def profile_fixture():
    return {
        "name": "Leonard Lomude",
        "handle": "@notlxnrd",
        "role": "Software Engineer & Product Builder",
        "tagline": "Building useful software.",
        "location": "Kampala, Uganda",
        "website": "https://leonardlomude.vercel.app",
        "tiles": [
            {"id": "build", "title": "BUILD", "subtitle": "Products", "href": "https://example.com/build", "accent": "#3478f6"},
            {"id": "systems", "title": "SYSTEMS", "subtitle": "Code", "href": "https://example.com/systems", "accent": "#e36c62"},
            {"id": "ai-lab", "title": "AI LAB", "subtitle": "AI", "href": "https://example.com/ai", "accent": "#e8b84b"},
        ],
        "featured_repos": [
            {"id": "sample", "name": "SAMPLE", "description": "A sample project description.", "url": "https://example.com/sample"}
        ],
    }

def test_profile_requires_three_safe_tiles():
    profile = profile_fixture()
    renderer.validate(profile)
    profile["tiles"].pop()
    import pytest
    with pytest.raises(ValueError, match="exactly three"):
        renderer.validate(profile)

def test_profile_rejects_non_http_tile_destinations():
    profile = profile_fixture()
    profile["tiles"][0]["href"] = "javascript:alert(1)"
    import pytest
    with pytest.raises(ValueError, match="HTTP"):
        renderer.validate(profile)

def test_contribution_stats_use_real_counts():
    data = {"days": [
        {"date": "2026-01-01", "count": 2, "level": 1},
        {"date": "2026-01-02", "count": 0, "level": 0},
        {"date": "2026-02-01", "count": 3, "level": 2},
    ]}
    stats = renderer.stats_for(data)
    assert stats["total"] == 5
    assert stats["active"] == 2
    assert stats["months"] == [((2026, 1), 2), ((2026, 2), 3)]

def test_all_card_renderers_produce_valid_svg():
    profile = profile_fixture()
    data = {"days": [
        {"date": "2026-11-18", "count": 3, "level": 2},
        {"date": "2026-11-19", "count": 1, "level": 1},
    ]}
    outputs = [
        renderer.render_hero(profile),
        renderer.render_graph(data),
        renderer.render_activity(data),
        renderer.render_tile(profile["tiles"][0]),
        renderer.render_repo(profile["featured_repos"][0], 1),
    ]
    for svg in outputs:
        ET.fromstring(svg)

def test_static_mode_disables_animation(monkeypatch):
    monkeypatch.setattr(renderer, "STATIC", True)
    static_svg = renderer.render_hero(profile_fixture())
    assert "@keyframes" not in static_svg
    monkeypatch.setattr(renderer, "STATIC", False)
    animated_svg = renderer.render_hero(profile_fixture())
    assert "@keyframes" in animated_svg
    assert "prefers-reduced-motion:reduce" in animated_svg

def test_renderer_generates_exact_ten_assets(tmp_path, monkeypatch):
    profile = profile_fixture()
    profile["featured_repos"] = [
        {"id": "one", "name": "ONE", "description": "One.", "url": "https://example.com/one"},
        {"id": "two", "name": "TWO", "description": "Two.", "url": "https://example.com/two"},
        {"id": "three", "name": "THREE", "description": "Three.", "url": "https://example.com/three"},
        {"id": "four", "name": "FOUR", "description": "Four.", "url": "https://example.com/four"},
    ]
    data = {"days": [{"date": "2026-11-18", "count": 2, "level": 1}]}
    monkeypatch.setattr(renderer, "ROOT", tmp_path)
    monkeypatch.setattr(renderer, "PROFILE", tmp_path / "data" / "profile.json")
    monkeypatch.setattr(renderer, "CONTRIBUTIONS", tmp_path / "data" / "contributions.json")
    monkeypatch.setattr(renderer, "CARDS", tmp_path / "cards")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (tmp_path / "data" / "contributions.json").write_text(json.dumps(data), encoding="utf-8")
    renderer.main()
    assets = sorted((tmp_path / "cards").rglob("*.svg"))
    assert len(assets) == 10
    for asset in assets:
        ET.parse(asset)

def test_readme_references_every_generated_profile_asset():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    expected = [
        "cards/hero.svg",
        "cards/contribution-graph.svg",
        "cards/activity.svg",
        "cards/tiles/build.svg",
        "cards/tiles/systems.svg",
        "cards/tiles/ai-lab.svg",
        "cards/repos/nancy.svg",
        "cards/repos/notlxnrd-os.svg",
        "cards/repos/roxan.svg",
        "cards/repos/trade-titans.svg",
    ]
    for path in expected:
        assert path in readme, path
