# Vendored files

The viewer's emoji picker (in Edit copy) is [emoji-mart](https://github.com/missive/emoji-mart), MIT licensed
(`LICENSE-emoji-mart.txt`). Bundled so the picker works offline from a local file; render.py copies this
folder into each viewer as `vendor/`, and the viewer loads it only when the emoji button is first used.

| File | Source |
|---|---|
| `emoji-mart.js` | `emoji-mart@5.6.0/dist/browser.js` |
| `emoji-mart-data.js` | `@emoji-mart/data@1.2.1/sets/15/native.json`, wrapped as `window.EMOJI_MART_DATA = …;` |

To update: download the new versions from jsDelivr (`https://cdn.jsdelivr.net/npm/<package>@<version>/<path>`),
check the license, and wrap the data file the same way.
