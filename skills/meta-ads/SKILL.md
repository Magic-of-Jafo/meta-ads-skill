---
name: meta-ads
description: Render realistic mockups of Meta ads (Facebook and Instagram) as they'd appear in situ, across 15 placements (FB Feed mobile/desktop, Stories, Reels, Marketplace, Video Feeds, In-stream, Right Column, Search; IG Feed, Stories, Reels, Explore, Explore Home, Profile Feed) for image, video and carousel ads, as an interactive local HTML viewer plus PNGs. Use this whenever someone wants to see, preview, mock up, visualize or compare Facebook/Instagram/Meta ads or ad variants: headlines and copy from a spreadsheet, ads scraped from the Meta Ad Library, competitor ads, draft copy with no creative yet, or "how would this look as a Reel/Story". The skill defines a standard ads.json format (SPEC.md) that the calling agent fills in from whatever it has, then checks what's missing per placement and renders. Not for writing ad copy (ad-creative) or planning campaigns/targeting (ads).
---

# meta-ads

Turns ad information into in-situ mockups of Facebook and Instagram ads. You (the invoking agent) translate whatever you have into one `ads.json` file; the skill validates it, tells you what's missing for each placement, and renders.

The skill never reads spreadsheets, Excel files, briefs or web pages itself. Getting data out of those sources is your job, because only you know their shape (and sources like the Ad Library change over time). `SPEC.md` tells you exactly what to produce.

## Steps

1. **Read `${CLAUDE_SKILL_DIR}/SPEC.md`** before writing anything. It defines every field, the shared-media rule, placeholders for missing creative, placement IDs, CTA codes, and a glossary mapping common source column names to spec fields. Complete examples are in `${CLAUDE_SKILL_DIR}/assets/examples/`.

2. **Write `ads.json`** from the information you have. Keep it somewhere durable in your workspace (not inside `meta-ads-output/`), because the user will likely edit it later, for example swapping placeholders for real creatives, and re-render.
   - List each unique image/video once under `media` and reference it by ID from every ad that uses it. Ads with no creative yet get a `placeholder` media entry describing the intended image.
   - Give every brand an `avatar`: the page's real profile picture (see SPEC.md §4 for where to find it), or, only if you can't get it, an explicit 1:1 `placeholder`. A missing avatar is an error.
   - Copy text verbatim. Leave out what you don't know instead of inventing it; the check reports gaps.
   - Save remote media (especially Meta CDN links, which expire within days) to local files and point `src` at them.

3. **Check**: `python "${CLAUDE_SKILL_DIR}/scripts/check.py" ads.json`
   Fix all errors. Then look at the summary, `unlock` list and `shopping_list` (in `inventory.json` / `inventory.md`). If something important is missing (copy, a 9:16 version, an avatar), ask the user whether to supply it or render with placeholders now. Placeholders are a valid choice: the user may want to judge copy before creatives exist.

4. **Render**: `python "${CLAUDE_SKILL_DIR}/scripts/render.py" ads.json`
   Output goes to `./meta-ads-output/<campaign>-<date>/` inside **your current working directory** (your own project workspace). Use `--out DIR` only if the user asks for another location. To update a previous render instead of creating a new dated folder, pass its folder as `--out`; stored media is reused. The folder also gets `ads.snapshot.json`, a copy of the spec whose paths point at the stored media, so the folder can be moved and re-rendered on its own.

5. **PNGs (when useful)**: `python "${CLAUDE_SKILL_DIR}/scripts/export_png.py" <output folder> [--ads A1,A2] [--placements ig_reels,fb_feed_mobile] [--dark] [--safe] [--limits] [--badges] [--all-cards]`
   Default is the clean in-situ view. `--safe`, `--limits` and `--badges` add review overlays and name files `__review`. Scope the export when there are many ads: 100 ads × 15 placements is 1,500 images.

6. **Present**: give the user the path to `index.html` (it opens offline by double-click) and summarize the inventory: how many mockups are ready or simulated, and the top unlocks.

## What the user gets in the viewer

- **Modes**: Gallery (one ad, every placement) · Compare (one placement, all variants side by side, filter by group/brand/status) · In feed (the ad between organic posts, scrollable phone or story sequence) · Matrix (all ads × placements, optional thumbnails).
- **Toggles**: safe zones (Stories/Reels UI cover areas), text limits (where copy truncates, chars vs recommendation), badges (why a mockup is simulated), phone frame, dark mode, zoom.
- Videos play, carousels swipe, "See more" expands. Every view is a URL hash, so a link to a specific view can be shared alongside the folder.

## Rules for using the output

- Mockups imitate Facebook and Instagram UI and may contain other brands' ads. Keep them local: don't publish the viewer or PNGs as an Artifact, upload them to a hosting service, or post them anywhere unless the user explicitly asks and understands that.
- The mockups are close approximations of the current apps, drawn by hand in HTML/CSS. They have not been compared pixel-for-pixel against real ads, fonts fall back to the OS's system font, and some fallback behaviours are assumed (see `references/placements.md`). Present them as realistic previews, not as Meta's own rendering.
- "Simulated" means the renderer applied a fallback (crop, padded fill, placeholder creative or placeholder identity). Say so when presenting; don't present a simulated mockup as exactly what Meta will show.
- Placement rules are dated (`assets/placements.json`, `version_date`). `references/placements.md` lists sources and which behaviours are assumptions. If the user asks why something looks the way it does, read that file.

## Files

| Path | Purpose |
|---|---|
| `SPEC.md` | The ads.json contract. Read first. |
| `assets/examples/*.json` | Valid example specs (`showcase.json`: every format; `copy-first.json`: placeholders only) |
| `assets/ad-spec.schema.json` | JSON Schema for structural validation |
| `assets/placements.json` | Placement rules, ratios, text limits, safe zones, CTA labels |
| `assets/viewer.html` | The viewer (copied into each output) |
| `scripts/check.py` | Validate + inventory |
| `scripts/render.py` | Build the output folder |
| `scripts/export_png.py` | Headless Chrome/Edge PNG export |
| `scripts/sync_spec.py` | Regenerate SPEC tables after editing placements.json |
| `references/placements.md` | Sources, assumptions, fidelity notes, maintenance |

Requirements: Python 3.9+ with Pillow; ffmpeg/ffprobe for video measuring and posters; Chrome or Edge for PNG export (set `CHROME` to the executable if it isn't found).
