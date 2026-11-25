# Spec: team libraries in a shared folder (future update)

Status: proposed, not built. Target: a minor release after the deck builder.

## Goal

Let a team work from one set of mockup libraries. The library root (`meta-ads/`) lives in a folder everyone approved can already reach: a synced cloud folder (OneDrive, SharePoint, Dropbox, Google Drive for desktop, Synology Drive) or a network share. Anyone with access double-clicks `meta-ads/index.html` and gets every library, with videos playing. Access control is whatever the folder already has; the skill adds no accounts, servers or uploads.

This complements the single-file share (`share.py`), which is for sending one snapshot to someone outside the folder and shows videos as still frames.

## What already works

- A library is self-contained: `ads.json` refers to media by relative path (`assets/...`), and the viewer uses relative paths only. A library folder opened from any machine shows the same thing.
- The home page and Library menu read `libraries.js` with a `<script>` tag, which works from `file://`, including UNC paths (`\\nas\share\meta-ads\index.html`) and synced folders.
- `libraries.js` is rebuilt by scanning folders, so whoever renders last writes the complete list.

## What the update adds

### 1. A configured library root

Agents in different projects must find the same shared root without being told each time.

- `library.py` and `render.py` look for the root in this order:
  1. `--root DIR`
  2. a `meta-ads.config.json` in the current folder or a parent folder, with `{"root": "<path>"}`
  3. `./meta-ads/`
- `library.py where` prints the root in use and how it was found.
- SKILL.md tells the agent to check `library.py where` before creating a library, so a team member doesn't create a private library by accident.

### 2. Paths that work for everyone

- `check.py` gains a warning when a library inside a root points at media outside its own folder (absolute paths, `../`). Such a file exists only on the author's machine. The fix is to copy the file into `assets/`.
- `render.py` can avoid copying media twice: an option (and the default inside a shared root) makes `viewer/` refer to the library's `assets/` instead of duplicating them into `viewer/media/`. That halves the synced size, which matters with video.

### 3. Safe concurrent use

Sync services don't lock files. Two people rendering at once, or an agent editing `ads.json` while another renders, can produce conflict copies ("libraries (Jane's conflicted copy).js").

- Each render writes to temporary files and renames them into place, so a half-written viewer is never synced.
- `render.py` takes a lock file (`<library>/.render.lock` with user, machine and time). A second render of the same library waits or stops with a clear message. Stale locks older than 10 minutes are ignored.
- `library.py doctor` finds sync-conflict copies (`*conflict*`, `* (1).js`, `*-DESKTOP-*`), stale locks and libraries whose `viewer/` is older than their `ads.json`. It reports them and, if asked, removes conflict copies of generated files only (never `ads.json` or `assets/`).
- Guidance in SKILL.md: one person (or agent) edits a given library's `ads.json` at a time. A library can record its owner in `campaign.notes` or a new optional `library.owner` field.

### 4. Opening the files

- Web previews of synced folders (OneDrive, Google Drive and Dropbox in the browser) don't run HTML pages. People must open the synced copy on their computer or the mapped network drive. The README says this plainly.
- "Files on demand" (OneDrive, Dropbox online-only files) download media when the viewer asks for it. The first open may be slow, and offline use needs "Always keep on this device" for the root.

## Documentation to write

- README: "Sharing with your team through a shared folder", covering setup per service, the open-the-local-copy rule, and who can see what (folder permissions).
- SKILL.md: root discovery, `library.py where` and `doctor`, the one-editor rule.

## Test plan

| Setup | Check |
|---|---|
| OneDrive (Windows), files on demand on | Home page, switcher, video playback, render while synced |
| Dropbox (macOS) | Same, plus two renders of different libraries at once give one correct `libraries.js` |
| Google Drive for desktop | Same |
| Synology Drive client | Same |
| SMB share opened as `\\server\share` (Windows) and `/Volumes/share` (macOS) | `file://` from UNC paths, relative media |
| Second machine without the author's other files | No missing media; check warns about any outside paths |

## Out of scope

- Hosting or web access (no server, no public links).
- Merging edits to one `ads.json` from several people at once.
- Per-library permissions beyond what the folder system provides.
