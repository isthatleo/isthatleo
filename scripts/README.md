# Profile README renderer

This repository is the source for the public GitHub profile at [github.com/isthatleo](https://github.com/isthatleo).

## Design system

- **Direction:** editorial engineering portfolio, not a badge wall or generic stats template.
- **Identity:** NOTLXNRD, with restrained electric-cyan accents on a near-black surface.
- **Typography:** system sans for display copy and monospace for metadata.
- **Motion:** subtle SVG entrance/reveal effects; all generated motion must respect `prefers-reduced-motion`.
- **Content:** keep claims factual, projects clearly described, and activity metrics sourced from GitHub contribution data.

## Local workflow

Run from the repository root:

```bash
python -m pip install -r scripts/requirements.txt
python scripts/fetch_contributions.py
python scripts/render_readme_cards.py
STATIC=1 python scripts/render_readme_cards.py
python -m pytest -q
```

To embed custom fonts, place licensed Geist WOFF files in `fonts/Geist-Regular.woff` and `fonts/GeistMono-Regular.woff`. The renderer uses `pyftsubset` (installed with fonttools) and embeds the subset as base64 WOFF data. Without local font files, SVGs use safe system fallbacks.

## Editing content

- Edit identity, links, project descriptions and status in `data/profile.json`.
- Edit layout and SVG presentation in `scripts/render_readme_cards.py`.
- Edit the profile narrative and section order in `README.md`.
- Never invent contribution counts. `data/contributions.json` is populated by the fetch script.
- Generated SVGs live in `cards/`; rerun the renderer after changing profile data or rendering code.
- The toolkit graphic is generated from `stack_groups` in `data/profile.json`; keep the groups curated and factual.
- Project descriptions and destinations must match the actual product or repository. Do not invent social URLs, metrics or deployment claims.

## Quality gates

1. Contribution fetch succeeds or fails explicitly; empty data must not be presented as real activity.
2. Renderer succeeds in animated and `STATIC=1` modes.
3. `python -m pytest -q` passes.
4. Every generated SVG parses as XML.
5. The grouped toolkit card renders from profile data and contains no unverified skill claims.
6. Every image path referenced by README resolves in the repository.
7. Reduced-motion users receive a static presentation.
8. Review the rendered profile on GitHub desktop and mobile before calling the design complete.
