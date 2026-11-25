# meta-ads: Facebook & Instagram ad mockups for Claude Code

A Claude Code skill that turns ad information (copy, headlines, CTAs, images, video, carousels) into realistic mockups of how the ads look **in situ** across 15 Meta placements. You get an interactive local HTML viewer plus PNG exports, with no online tools and no Meta account.

![Example mockups: Facebook Feed, Instagram Feed carousel, Instagram Reels, Facebook Stories](docs/preview.jpg)

*Example output for a fictional brand: Facebook Feed, Instagram Feed (carousel), Instagram Reels, Facebook Stories.*

## What it does

- **15 placements.**
  - Facebook: Feed (mobile and desktop), Stories, Reels, Marketplace, Video Feeds, In-stream, Right Column, Search.
  - Instagram: Feed, Stories, Reels, Explore, Explore Home, Profile Feed.
- **Image, video and carousel** ads. Videos play and carousels swipe in the viewer.
- **Viewer modes:**
  - **Gallery:** one ad in every placement.
  - **Compare:** variants side by side in one placement.
  - **In feed:** the ad between organic posts.
  - **Matrix:** every ad × every placement.
- **Review overlays:** Stories/Reels safe zones, where the text cuts off ("…See more") and how long it is against Meta's recommendation, and badges explaining any fallback. Plus a phone frame, dark mode and zoom.
- **Gap report.** `check.py` says which mockups are native fits and which are simulated (wrong ratio, placeholder creative, missing logo), and ranks what to add next. For example: *"Add a 9:16 version of m_hero → 12 mockups become native"*.
- **Copy-first.** Ads can use placeholder creative, so you can judge copy before any image exists.
- **Shared media.** Each unique image is listed once and referenced by any number of ads. 100 ads using one image means one file.

## How it works

The skill defines a format (`ads.json`, documented in [`skills/meta-ads/SPEC.md`](skills/meta-ads/SPEC.md)). The agent using the skill converts whatever it has (a spreadsheet, notes, an Ad Library export) into that format itself. The skill then checks it and renders:

```
ads.json  →  check.py (errors, gaps, unlock list)  →  render.py (viewer)  →  export_png.py (PNGs)
```

Output goes to `meta-ads-output/<campaign>-<date>/` in the current project folder.

## Install

### Option A: as a plugin (recommended)

In Claude Code:

```
/plugin marketplace add Magic-of-Jafo/meta-ads-skill
/plugin install meta-ads@meta-ads-skill
```

Then use it by asking naturally ("mock up these ads as Instagram Reels and Facebook Feed"), or run `/meta-ads:meta-ads`.

From a terminal instead:

```
claude plugin marketplace add Magic-of-Jafo/meta-ads-skill
claude plugin install meta-ads@meta-ads-skill
```

### Option B: as a personal skill

Copy the skill folder into your personal skills directory. It's then invoked as `/meta-ads`.

macOS / Linux:

```bash
git clone https://github.com/Magic-of-Jafo/meta-ads-skill.git
mkdir -p ~/.claude/skills && cp -r meta-ads-skill/skills/meta-ads ~/.claude/skills/
```

Windows (PowerShell):

```powershell
git clone https://github.com/Magic-of-Jafo/meta-ads-skill.git
New-Item -ItemType Directory -Force "$HOME\.claude\skills" | Out-Null
Copy-Item -Recurse meta-ads-skill\skills\meta-ads "$HOME\.claude\skills\"
```

Use one option, not both, or you'll have two copies of the skill.

### Requirements

- **Python 3.9+** with **Pillow**: `pip install pillow`
- **ffmpeg / ffprobe** on your PATH, for video ads (measuring and cover frames)
- **Chrome or Edge**, for PNG export. Set `CHROME` to the browser's path if it isn't found automatically.

## Try it

Ask Claude Code something like:

> Mock up the ads in `ads.json` across all placements and show me the Instagram ones.

or render the bundled example directly:

```bash
python skills/meta-ads/scripts/check.py skills/meta-ads/assets/examples/showcase.json
python skills/meta-ads/scripts/render.py skills/meta-ads/assets/examples/showcase.json
python skills/meta-ads/scripts/export_png.py meta-ads-output/<folder> --ads A1,C1
```

Then open `meta-ads-output/<folder>/index.html`.

## Accuracy

The mockups are hand-built HTML/CSS approximations of the Facebook and Instagram apps as of late 2026, based on Meta's Ads Guide and public coverage of app changes. They are not pixel-for-pixel copies:
- fonts fall back to your system font;
- logos and icons are drawn approximations, not Meta's own assets;
- a few behaviours Meta doesn't document are assumptions, such as how off-ratio media is padded and where text cuts off.

Every assumption, plus the sources, is listed in [`skills/meta-ads/references/placements.md`](skills/meta-ads/references/placements.md). Placement rules live in one dated file (`assets/placements.json`); `scripts/sync_spec.py` keeps the documentation tables in step after edits.

## Notes

- Not affiliated with or endorsed by Meta. Facebook and Instagram are trademarks of Meta Platforms, Inc.
- Mockups are for private review. They imitate the apps' interface and can contain other brands' ads, so don't publish them as if they were real ads.

## License

[MIT](LICENSE)
