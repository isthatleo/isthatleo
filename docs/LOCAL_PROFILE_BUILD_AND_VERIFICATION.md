# Local Profile Build & Verification Runbook

This document is the handoff for cloning this repository, regenerating the GitHub profile artwork, running the quality gates, and reviewing the result locally before pushing changes.

Repository: https://github.com/isthatleo/isthatleo  
Public profile: https://github.com/isthatleo

## 1. What this repository produces

The root `README.md` is the public GitHub profile page. The SVG files under `cards/` are generated presentation assets. The source of truth is:

- `data/profile.json` — identity, project descriptions, destinations, toolkit groups and link tiles.
- `data/contributions.json` — normalized GitHub contribution-calendar data.
- `scripts/fetch_contributions.py` — fetches the public contribution calendar for `isthatleo`.
- `scripts/render_readme_cards.py` — renders SVG assets from the source data.
- `README.md` — controls the page narrative, section order, image references and clickable links.
- `tests/` — automated tests for data calculations, SVG output and repository asset references.

Do not edit generated SVGs as the primary source of a design change. Edit the data or renderer, regenerate, then review the generated output. A deliberate hand-authored SVG (if one is introduced later) must be clearly documented as such.

## 2. Clone and prepare the machine

### macOS / Linux

```bash
git clone https://github.com/isthatleo/isthatleo.git
cd isthatleo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r scripts/requirements.txt
```

### Windows PowerShell

```powershell
git clone https://github.com/isthatleo/isthatleo.git
Set-Location isthatleo
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r scripts/requirements.txt
```

Python 3.12 is the CI target. Use Python 3.12 locally for parity. If PowerShell blocks activation, use the Python executable directly at `.venv\Scripts\python.exe` rather than changing machine-wide execution policy.

Optional font embedding:
- Put properly licensed `Geist-Regular.woff` and `GeistMono-Regular.woff` files in `fonts/`.
- The renderer uses `pyftsubset` from fonttools when available.
- Font files are optional. Without them, generated SVGs use system font fallbacks.
- Do not commit fonts unless their license permits redistribution; retain the license file when required.

## 3. Build sequence

Run these commands from the repository root, in this order.

### Step A — fetch contribution data

```bash
python scripts/fetch_contributions.py
```

Expected result:
- Fetches `https://github.com/users/isthatleo/contributions`.
- Parses contribution calendar cells.
- Writes `data/contributions.json` with `schema_version`, `username`, `source`, `fetched_at` and `days`.
- Parses and validates ISO dates, non-negative counts and contribution levels (0–4); malformed cells are skipped.
- Rejects duplicate dates rather than silently double-counting them.
- Exits non-zero if no valid calendar cells are parsed.
- Writes through a temporary file in the target directory, then atomically replaces the dataset only after a valid non-empty fetch. Network, parse and empty-result failures leave the previous file untouched.

Network access is required. No GitHub token is currently required by this public HTML fetcher. If GitHub changes its page markup or rate-limits the request, stop and investigate; do not fabricate data or manually fill counts.

### Step B — generate animated profile assets

```bash
python scripts/render_readme_cards.py
```

Expected result: renderer prints the number of SVG cards generated. The output is written beneath `cards/`.

### Step C — generate static assets and restore animated output

```bash
STATIC=1 python scripts/render_readme_cards.py
python scripts/render_readme_cards.py
```

The first command verifies the static/reduced-motion rendering path. The second restores the default animated SVGs so the working tree is left in its normal release state.

Windows PowerShell equivalent:

```powershell
$env:STATIC = "1"
python scripts/render_readme_cards.py
Remove-Item Env:STATIC
python scripts/render_readme_cards.py
```

### Step D — run automated tests

```bash
python -m pytest -q
```

### Step E — inspect the generated changes

```bash
git status --short
git diff --check
git diff -- data/contributions.json cards/
```

Review every changed SVG in a browser or image-capable editor. Open the root `README.md` on GitHub after pushing; local SVG rendering is not a substitute for checking GitHub's actual Markdown rendering.

## 4. Generated asset manifest

The renderer currently generates **10 SVG files**:

| Asset | Source | Purpose |
|---|---|---|
| `cards/hero.svg` | `profile.json` + `render_hero` | Main identity / hero banner |
| `cards/contributions.svg` | `contributions.json` + `render_contributions` | Contribution summary and monthly activity |
| `cards/contribution-graph.svg` | `contributions.json` + `render_graph` | Contribution calendar grid |
| `cards/stack.svg` | `profile.json:stack_groups` + `render_stack` | Grouped engineering toolkit |
| `cards/links/build.svg` | `profile.json:tiles[build]` | Build / portfolio destination tile |
| `cards/links/systems.svg` | `profile.json:tiles[systems]` | Systems / GitHub destination tile |
| `cards/repos/nancy.svg` | `profile.json:featured_repos[nancy]` | NÅNCY / BILLION project panel |
| `cards/repos/notlxnrd-os.svg` | `profile.json:featured_repos[notlxnrd-os]` | NOTLXNRD.OS project panel |
| `cards/repos/roxan.svg` | `profile.json:featured_repos[roxan]` | ROXAN project panel |
| `cards/repos/trade-titans.svg` | `profile.json:featured_repos[trade-titans]` | TRADE TITANS project panel |

The README currently references the hero, toolkit, contribution summary, contribution graph and four project panels. The two link tiles are generated assets but are not currently embedded in the README. Keep that distinction intentional; either embed them in a future layout change or remove them from the generator only after confirming no other consumer uses them.

### Generated versus source-controlled

Commit generated SVGs alongside the source changes that produce them. This keeps the GitHub profile readable without requiring GitHub Actions to run before every README update. Commit refreshed `data/contributions.json` only when it was successfully fetched from the stated source.

## 5. Automated test inventory

Run the complete suite with:

```bash
python -m pytest -q
```

Current test file: `tests/test_render_readme_cards.py`.

| Test | What it protects | Expected assertion |
|---|---|---|
| `test_stats_are_derived_from_fixture` | Contribution aggregation | Total, active days, busiest day and month buckets match fixture data |
| `test_xml_escaping` | Untrusted text in SVG | Ampersands and angle brackets are escaped |
| `test_svg_is_well_formed` | Hero rendering | Hero output parses as XML with special-character input |
| `test_stack_card_is_well_formed` | Toolkit rendering | Toolkit output parses and contains the supplied group items |
| `test_empty_contributions_are_not_rendered_as_zero_metrics` | Empty-data honesty | Empty contribution data displays the waiting state, not invented metrics |
| `test_readme_image_references_exist` | README asset integrity | Every local `cards/` image source referenced by README exists |
| `test_calendar_parser_extracts_valid_cells_and_skips_malformed_values` | Fetcher parsing | Valid dates/counts/levels are normalized; malformed, negative and out-of-range cells are ignored |
| `test_calendar_parser_rejects_duplicate_dates` | Fetcher integrity | Duplicate dates fail closed |
| `test_empty_fetch_cannot_overwrite_existing_contributions` | Data safety | Empty results cannot replace an existing dataset |
| `test_network_failure_does_not_touch_existing_dataset` | Network failure safety | A failed fetch leaves existing data unchanged |
| `test_fetch_write_is_valid_json_and_atomic_output_shape` | Output contract | Successful writes contain schema metadata and normalized days with no leftover temp files |
| `test_every_generated_asset_is_well_formed_and_matches_manifest` | Full renderer integration | All 10 expected SVGs are generated and parse as XML |
| `test_static_and_animated_svg_modes` | Motion modes | Static output omits keyframes; animated output includes reduced-motion handling |

### Additional manual / release gates

These are required even when pytest passes:

1. Fetcher succeeds against the live public contribution page and produces non-empty, dated calendar data.
2. Fetcher failure does not replace valid existing contribution data.
3. Animated renderer completes successfully.
4. Static renderer completes successfully; regenerate animated output afterward.
5. Every generated SVG parses as XML.
6. All expected generated assets exist (manifest above).
7. README local image references all resolve.
8. All project links open the intended repository or verified public destination.
9. SVGs are legible at GitHub's rendered size on desktop and mobile.
10. Motion is subtle and does not obscure text; reduced-motion/static output remains readable.
11. `git diff --check` passes and no unrelated files are modified.

### Known coverage gaps to address during local verification

The automated suite now covers parser fixtures, duplicate dates, empty/network failure safety, atomic output, all generated SVGs, the asset manifest and motion modes. Remaining hardening opportunities include:
- Contribution fetcher parsing using saved HTML fixtures (no network in unit tests).
- Fetcher behavior for malformed/empty HTML and network failures, proving existing data remains untouched.
- Invalid or missing profile keys and malformed contribution records.
- XML parsing for every generated SVG, not just selected renderer outputs.
- An exact expected asset manifest, including both link tiles and all four project cards.
- README link destinations and image references, not only image-file existence.
- Static-mode output and the presence of reduced-motion handling in animated output.
- Escaping for all user-controlled text fields, including project descriptions and toolkit labels.

Do not make unit tests depend on live GitHub. Keep live network checks as a separate manual/integration gate.

## 6. Profile content and asset editing rules

### Identity and narrative
- Edit identity fields in `data/profile.json`.
- Edit prose, section order and clickable image wrappers in `README.md`.
- Keep the hero's role and tagline concise enough to render cleanly.

### Featured projects
- Edit `featured_repos` in `data/profile.json`.
- Verify every URL before adding it.
- Keep descriptions grounded in the actual source repository and current product scope.
- Current ROXAN and TRADE TITANS card destinations are portfolio-level links; replace them with direct project destinations only after confirming the correct public URLs.
- Do not claim a project is deployed, production-ready or fully implemented unless verified.

### Toolkit
- Edit `stack_groups` in `data/profile.json`.
- Keep no more than three groups and six items per group unless the renderer layout is deliberately expanded.
- Include only technologies and practices that accurately represent the owner's skills and work.

### Contributions
- Never hand-edit contribution counts to improve appearance.
- A missing or empty dataset must remain visibly empty / awaiting refresh.
- Check `fetched_at` and `source` when reviewing the contribution data.

## 7. Git workflow for local work

Start by checking the branch and working tree:

```bash
git branch --show-current
git status --short
git pull --ff-only origin main
```

After editing and passing tests:

```bash
python -m pytest -q
python scripts/render_readme_cards.py
python -m pytest -q
git diff --check
git status --short
git diff
```

Review the diff before committing. Suggested commit scopes:
- `design(profile): ...` for README/SVG presentation changes.
- `feat(profile): ...` for renderer or generator behavior.
- `test(profile): ...` for automated coverage.
- `docs(profile): ...` for this runbook and maintenance documentation.
- `chore(profile): ...` for refreshed contribution data and generated output.

Push to a feature branch and review the GitHub-rendered profile before merging to `main`, unless the owner deliberately chooses a direct-main workflow.

## 8. GitHub Actions troubleshooting

Workflow: `.github/workflows/update-profile-art.yml`.

The workflow is intended to:
1. Check out the repository.
2. Set up Python 3.12.
3. Install `scripts/requirements.txt`.
4. Fetch contribution data.
5. Render animated SVG assets.
6. Run pytest.
7. Commit refreshed contribution data and generated SVGs.

Recent workflow attempts were failing almost immediately, with no exposed step list or useful job logs through the available GitHub API inspection. **The cause is not yet established.** Do not assume it is a Python/test failure or a runner-provisioning issue without checking the actual Actions run page.

On the PC:
- Open the failed run from the repository's Actions tab.
- Expand the `render` job and identify the exact failing step.
- If no step starts, inspect repository/org Actions permissions, runner availability and workflow policy.
- If dependency installation fails, compare Python version and requirements.
- If fetch fails, inspect the HTTP response / page markup and confirm no data was overwritten.
- If rendering or tests fail, reproduce the exact command locally and fix the underlying source.
- Re-run the workflow after the fix and retain the successful run URL in the project notes.

The workflow currently uses major-version action tags (`actions/checkout@v4`, `actions/setup-python@v5`, `stefanzweifel/git-auto-commit-action@v5`). Consider pinning third-party actions to verified full commit SHAs as a separate supply-chain hardening task.

## 9. Definition of done

The profile refresh is complete only when all are true:

- [ ] Clean clone setup works on Python 3.12.
- [ ] Contribution fetch succeeds, or a documented source failure is handled without corrupting existing data.
- [ ] Animated and static rendering both succeed.
- [ ] All 10 generated SVG assets are present and parseable.
- [ ] Full pytest suite passes locally and in GitHub Actions.
- [ ] README image references and project destinations are verified.
- [ ] Desktop and mobile GitHub rendering reviewed.
- [ ] Git diff contains only intentional source/data/generated-art/documentation changes.
- [ ] GitHub Actions completes successfully and its run is inspected.
- [ ] Final commit / PR includes the generated assets and the verification evidence.

Until the last release gates pass, describe the profile as refined but not fully verified.
