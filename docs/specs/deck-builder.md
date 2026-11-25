# Spec: deck builder (PDF and PowerPoint)

Status: proposed. Next feature after the single-file share (v1.4.0).

## Goal

Turn chosen mockups into a designed presentation, for example to show a company's leadership the ad concepts, or to set your ads against a competitor's. The user picks ads, picks a layout for each slide and orders them. The skill produces:

- a **PDF** that looks like a designed deck, not a screenshot of the viewer;
- an editable **PowerPoint** (`.pptx`) with the same slides.

## How it's used

1. In any library's viewer, an **Add to deck** button sits next to the Ad picker. The home page gets a **Decks** section, with **New deck** and the existing decks.
2. **The deck builder** (`meta-ads/decks.html`) is a page at the library root, so one deck can use ads from several libraries.
   - **Left:** slides as thumbnails. Drag to reorder; add, duplicate and delete slides.
   - **Centre:** the selected slide at 16:9, drawn live.
   - **Right:** slide settings: layout, ads (picked from any library), placement, title, subtitle, talking points and speaker notes.
3. **Saving:** the builder saves as it goes (browser storage), and **Save deck** writes the deck file. Saving goes through the browser's save dialog where it allows that, otherwise to a download. **Copy for Claude** puts the deck on the clipboard.
4. **Building:** the user asks the agent to build it (or runs `deck.py build`), and gets `<deck>.pdf` and `<deck>.pptx`.
5. **Without the builder:** the agent can also write a deck file from a request ("a deck with our three hooks against Acme's top three"). The user then opens it in the builder to adjust.

## Files

```
meta-ads/
  decks.html                    generated: the deck builder
  decks/
    <deck>/
      deck.json                 the deck (the builder and the agent write this)
      <deck>.pdf                built
      <deck>.pptx               built
      build/                    generated mockup images and slide pages; safe to delete
```

## deck.json

```json
{
  "deck_version": 1,
  "title": "Fall concepts for review",
  "subtitle": "Northstep · prepared for the leadership team",
  "date": "2026-12-01",
  "theme": { "accent": "#1b74e4", "background": "light", "logo": "logo.png", "font": "Segoe UI" },
  "slides": [
    { "layout": "cover" },
    { "layout": "concept", "title": "Hook: discount first",
      "ads": [{ "library": "northstep-fall-drafts", "ad": "A1" }],
      "placements": ["ig_feed", "fb_feed_mobile", "ig_reels"],
      "points": ["Leads with the offer", "Strongest in Feed"], "notes": "Speaker notes" },
    { "layout": "versus", "title": "Us vs Rival: Stories",
      "placement": "ig_stories",
      "sides": [
        { "label": "Northstep", "ads": [{ "library": "northstep-fall-drafts", "ad": "A2" }] },
        { "label": "Rival", "ads": [{ "library": "rival-competitors", "ad": "R4" }] } ] }
  ]
}
```

**Days running** needs data the ad spec doesn't have yet. Add an optional `started` date per ad (`"started": "2026-10-02"`, from the Ad Library's "Started running on"), which check.py validates and the viewer can also show. Without it, the row leaves days out.

Ads are referred to by library folder and ad ID. If an ad has been removed, the slide shows a clear "missing ad" box, both in the builder and in the build.

## Slide layouts

| Layout | Content |
|---|---|
| `cover` | Title, subtitle, date, logo |
| `section` | A divider with a title and one line |
| `concept` | One ad large in its main placement, up to two more placements beside it, the copy as real text (headline, primary text, CTA) and up to four talking points |
| `versus` | Two sides, 1–3 ads each, in one placement, with a comparison row under each side: format, CTA, primary-text length against Meta's guidance, headline length, and days running when the ad has a start date (see below) |
| `lineup` | 2–6 ads in one placement, with a short caption under each |
| `everywhere` | One ad across 3–5 placements |
| `takeaways` | Title and up to six points |

All layouts are defined once, as boxes on a 1920×1080 grid. The PDF and the PowerPoint read the same definitions, so the two match.

## Look

- A clean house style: generous margins, one accent colour, mockups on a soft neutral background with a subtle shadow, small grey captions naming the placement.
- **Theme:** accent colour, light or dark background, an optional logo (shown on the cover and small in a corner), and the font. Default font is the system UI font in the PDF and a font PowerPoint will have (Segoe UI or Arial) in the `.pptx`.
- **Simulated mockups** get a small "simulated" tag in the caption. The last slide of every deck says that the mockups are approximations, and that simulated ones were adjusted to fit.
- **Video ads** show their cover frame with a small "▶ video" tag. In the `.pptx` the video can be embedded and play (option, on by default when the file is under 50 MB).
- **Carousels:** first card large, with the next cards peeking in the same way the viewer shows them.

## How it's built

1. **Mockup images:** `deck.py` renders each (ad, placement) pair in the deck with the same headless Chrome export as `export_png.py`, at 2× for sharp output. It caches the images in `build/`, keyed by the ad's data, so rebuilding is quick.
2. **PDF:** `deck.py` writes one HTML page per deck from the layout definitions and the images, sized to 13.333 × 7.5 in. Chrome prints it to PDF, so text stays real and sharp, with no headers, footers or margins.
3. **PowerPoint:** with `python-pptx` (a new optional requirement), the same boxes become native text boxes (editable), images and, optionally, embedded video. Talking points become bullet lists; `notes` become speaker notes.
4. **Builder preview:** each mockup in the builder is the library viewer itself in a frame, in a new **embed** mode (`<library>/viewer/index.html#embed&ad=..&pl=..`). That mode is like PNG export but with a transparent background instead of the chroma key, and it tells the builder its size with `postMessage`, since a page opened from a local file can't read a frame's contents. The builder scales the frame to its slide box. This reuses the renderer exactly, with no second copy of the mockup code. The slide thumbnails in the left rail use the images from the last build when there are any, and simple boxes otherwise, so the rail doesn't load dozens of viewers.
5. **Text that doesn't fit:** HTML and PowerPoint wrap text differently, and PowerPoint doesn't shrink text to fit. So `deck.py` decides how much text each box gets (lines and characters per box, by layout) and cuts it with "…" before either renderer sees it. The full text stays in the speaker notes. Ads with very long primary text are the test case.

## Commands

```
python deck.py new "Fall concepts for review" [--root DIR]     create decks/<deck>/deck.json with a cover slide
python deck.py build decks/<deck>/deck.json [--pdf] [--pptx]    build (both by default)
python deck.py check decks/<deck>/deck.json                     report missing ads, libraries or placements
```

`library.py index` and `render.py` also refresh `decks.html` and the Decks list on the home page. `library.py new` refuses the name "decks", which is reserved for this folder.

## Requirements and limits

- PDF: no new requirements (Chrome or Edge is already needed for PNG export).
- PowerPoint: the [python-pptx](https://python-pptx.readthedocs.io/en/latest/user/install.html) library. If it's missing, the build makes the PDF and points to that page.
- Nothing is uploaded. The README's "What it runs, sends and fetches" section gets `deck.py`.

## Build order

1. `deck.json`, `deck.py check` and `build --pdf` with `cover`, `concept`, `versus` and `takeaways` (the agent can write decks from requests from this point on).
2. PowerPoint output for the same layouts.
3. The builder page and **Add to deck** in the viewer.
4. The remaining layouts (`section`, `lineup`, `everywhere`), embedded video in PowerPoint, theme logo.

## Decided defaults

- Neutral house style; the accent colour and logo are set per deck.
- `versus` has two sides, 1–3 ads each. More sides can come later if needed.
