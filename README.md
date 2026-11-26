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
  - **Feed preview:** one ad between ordinary posts, the way someone scrolling would see it.
  - **Compare ads:** every ad side by side in one placement.
  - **All placements:** one ad in every placement, grouped by Facebook phone, Instagram and Facebook desktop.
  - **Overview:** a grid of every ad × every placement, coloured by status. Click a cell to open it.
  - Step through ads with ‹ › or the arrow keys; Filter narrows by group, brand or status.
- **Remembers your settings** (view, placement, overlays, dark mode, zoom) across visits and libraries, in your browser.
- **Overlays:** Stories/Reels safe areas, where the text gets cut off ("…See more") and how long it is against Meta's recommendation, and notes saying why a mockup is simulated. Plus a phone frame, dark mode and zoom.
- **Gap report.** `check.py` says which mockups are native fits and which are simulated (wrong ratio, placeholder creative, missing logo), and ranks what to add next. For example: *"Add a 9:16 version of m_hero → 12 mockups become native"*.
- **Copy-first.** Ads can use placeholder creative, so you can judge copy before any image exists.
- **Shared media.** Each unique image is listed once and referenced by any number of ads. 100 ads using one image means one file.

## Libraries

Keep separate sets of ads apart: your drafts, each competitor, each campaign. Every **library** has its own folder with its spec, its media and its viewer, under `meta-ads/` in your project. A **Library** menu in the viewer switches between them, keeping your view, and `meta-ads/index.html` lists them all with their ad counts and last update.

Ask for it in plain words: *"Start a mockup library called Acme competitors with their current ads"*, *"Add these two drafts to my Spring launch library"*. The agent creates and fills the folders, following the layout in [`SKILL.md`](skills/meta-ads/SKILL.md#libraries).

## Share mockups

To show the mockups to someone, ask for a **single-file share**: *"Make a shareable file of the Spring launch library"*. You get one `.html` file with everything inside it. Send it by email, Slack or Teams, or drop it in a shared drive. The recipient downloads it and double-clicks it: no install, no account, and nothing is uploaded anywhere.

- Videos appear as their cover frame. The share is for judging how each ad looks on the device (text against image, margins, safe areas), and it keeps the file small.
- You can share only some ads. Images are scaled to phone-mockup size unless you ask for full resolution.
- Open the file in the browser, not in a web preview such as Google Drive's, which won't run it.
- Opened where it was made (the library's `share/` folder), it links back to the full library and to all libraries. A copy you send shows no links.

Team access through a shared folder, with videos playing, is planned: see [`docs/specs/shared-folder-libraries.md`](docs/specs/shared-folder-libraries.md).

## See what your competitors are running

The [Meta Ad Library](https://www.facebook.com/ads/library/) is Meta's public archive of the ads that brands are running right now. Give your agent a brand's Ad Library page and it can bring those ads into the viewer, so you see them the way customers do: in the feed, as Stories and Reels, on desktop. That's a far quicker read than the Library's own small previews. Then put them next to yours.

Things you can ask for:

- *"Here's [competitor]'s Ad Library page: [link]. Pull their active ads and show me how they look in the feed."*
- *"Which hooks and offers are [competitor] testing right now? Show their ads side by side as Instagram Stories."*
- *"Put my three draft ads next to [competitor]'s current ads in Compare ads, Facebook Feed."*
- *"I have headlines in this spreadsheet and no images yet. Mock them up with placeholders."*

Each brand gets its own name and logo in the mockups, and the Filter menu narrows the viewer to one brand. Keep each competitor in its own library, or put their ads in the same library as yours to compare them side by side. The skill itself doesn't fetch anything from the Ad Library. Your agent collects the ads with whatever tools it has (a browser, or an export you saved) and writes them into the skill's format. Meta's image links expire within days, so the agent saves the media locally.

## How it works

The skill defines a format (`ads.json`, documented in [`skills/meta-ads/SPEC.md`](skills/meta-ads/SPEC.md)). The agent using the skill converts whatever it has (a spreadsheet, notes, an Ad Library export) into that format itself. The skill then checks it and renders:

```
ads.json  →  check.py (errors, gaps, unlock list)  →  render.py (viewer)  →  export_png.py (PNGs)
```

A library's viewer goes to `meta-ads/<library>/viewer/` in the current project folder. A spec outside a library renders to `meta-ads-output/<campaign>-<date>/`.

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

Download this repository (on GitHub: **Code → Download ZIP**, or [clone it](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository)), then copy the `skills/meta-ads` folder into your personal skills folder: `~/.claude/skills/` on macOS and Linux, `%USERPROFILE%\.claude\skills\` on Windows. It's then invoked as `/meta-ads`.

Use one option, not both, or you'll have two copies of the skill.

### Requirements

- **[Python](https://www.python.org/downloads/) 3.9+** with **[Pillow](https://pillow.readthedocs.io/en/stable/installation/basic-installation.html)**
- **[ffmpeg / ffprobe](https://ffmpeg.org/download.html)** on your PATH, for video ads (measuring and cover frames)
- **Chrome or Edge**, for PNG export. If it isn't found automatically, give its path with `--browser`.

## What it runs, sends and fetches

Everything runs locally on your machine. The plugin has no hooks, no MCP servers and no telemetry, and needs no accounts or API keys.

- **Python scripts** in `skills/meta-ads/scripts/`, which Claude runs when you ask for mockups:
  - `check.py` validates your `ads.json` and writes `inventory.json` and `inventory.md` next to it.
  - `render.py` copies your media into the output folder (a library's `viewer/`, or `meta-ads-output/<campaign>-<date>/` in the current folder) and writes the viewer (`index.html`, `data.js`) there. For a library it also rewrites `index.html` and `libraries.js` in the library root (`meta-ads/`).
  - `share.py` writes a single-file copy of a viewer (images embedded, videos as cover frames) into a `share/` folder. It sends nothing; you decide where the file goes.
  - `library.py` creates library folders under `meta-ads/` and rewrites that folder's `index.html` and `libraries.js`. It deletes nothing.
  - `export_png.py` saves PNGs into that folder's `png/` subfolder.
  - `sync_spec.py` is a maintenance script that regenerates tables in the docs.
- **ffprobe / ffmpeg**, if installed, read video dimensions and save one cover frame per video.
- **Chrome or Edge, headless**, opens the local `index.html` to take the PNG screenshots, using a temporary profile folder that is deleted afterwards.
- **Network:** the only network access is downloading media you list in `ads.json` as `http(s)://` URLs. Each file is fetched once with a plain GET into the output folder. Nothing is uploaded or sent anywhere, and the viewer page loads nothing from the web. The viewer keeps your settings in the browser's local storage on your machine.

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
