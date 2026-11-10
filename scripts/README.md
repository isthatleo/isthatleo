# Profile README renderer

Run from this directory:

```bash
python -m pip install -r scripts/requirements.txt
python scripts/fetch_contributions.py
python scripts/render_readme_cards.py
STATIC=1 python scripts/render_readme_cards.py
python -m pytest -q
```

To embed custom fonts, place licensed Geist WOFF files in `fonts/Geist-Regular.woff` and `fonts/GeistMono-Regular.woff`. The renderer uses `pyftsubset` (installed with fonttools) and embeds the subset as base64 WOFF data. Without local font files, SVGs use safe system fallbacks.
