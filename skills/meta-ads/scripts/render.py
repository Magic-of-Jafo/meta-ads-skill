"""Render an ads.json into the mockup viewer.

Usage:
    python render.py path/to/ads.json [--out DIR] [--open]

Default output: ./meta-ads-output/<campaign-slug>-<YYYY-MM-DD>/ under the
current working directory (the invoking agent's workspace). Each unique media
file is stored once in media/, named by content hash, however many ads use it.
Re-running into the same folder reuses media already there.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metaads  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VIEWER = metaads.SKILL_DIR / "assets" / "viewer.html"


def slug(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s or "campaign").strip("-").lower()
    return s[:60] or "campaign"


def download_remote(spec, out_media):
    """Fetch http(s) media once into the output's media folder (in-memory spec only is updated)."""
    dl = out_media / "_downloads"
    for mid, m in (spec.get("media") or {}).items():
        if not isinstance(m, dict):
            continue
        for key in ("src", "poster"):
            url = m.get(key)
            if not (isinstance(url, str) and re.match(r"^https?://", url)):
                continue
            dl.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20]
            ext = os.path.splitext(url.split("?")[0])[1].lower()[:5] or (".mp4" if m.get("kind") == "video" and key == "src" else ".jpg")
            target = dl / (name + ext)
            if not target.exists():
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "meta-ads-mockup/1.0"})
                    with urllib.request.urlopen(req, timeout=60) as r, open(target, "wb") as f:
                        shutil.copyfileobj(r, f)
                except Exception as e:  # noqa: BLE001
                    print(f"  could not download {mid}.{key}: {e}")
                    continue
            m[key] = str(target)


def store(path, media_dir, suffix=""):
    """Copy a file into media/ under its content hash; return the relative path."""
    p = Path(path)
    sha = metaads.file_sha256(p)
    if p.resolve().parent == media_dir.resolve():  # already stored (re-render from snapshot)
        return f"media/{p.name}", sha
    name = f"{sha[:20]}{suffix}{p.suffix.lower()}"
    dest = media_dir / name
    if not dest.exists():
        shutil.copy2(p, dest)
    return f"media/{name}", sha


def make_poster(video_path, media_dir, sha):
    dest = media_dir / f"{sha[:20]}.poster.jpg"
    if dest.exists():
        return f"media/{dest.name}"
    for t in ("1", "0"):
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", t, "-i", str(video_path), "-frames:v", "1", "-q:v", "3", str(dest)],
                           capture_output=True, text=True)
        if dest.exists():
            return f"media/{dest.name}"
    print(f"  could not extract a poster frame from {video_path}: {r.stderr.strip()[:200]}")
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--out", help="output folder (default ./meta-ads-output/<campaign>-<date>)")
    ap.add_argument("--open", action="store_true", help="open the viewer in the default browser")
    a = ap.parse_args()

    spec, spec_path, rep = metaads.load_spec(a.spec)
    if spec is None:
        for e in rep.errors:
            print(f"ERROR {e['where']}: {e['message']}")
        sys.exit(1)
    name = (spec.get("campaign") or {}).get("name") if isinstance(spec.get("campaign"), dict) else None
    out = Path(a.out) if a.out else Path.cwd() / "meta-ads-output" / f"{slug(name)}-{dt.date.today().isoformat()}"
    out = out.resolve()
    media_dir = out / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    download_remote(spec, media_dir)
    res = metaads.resolve(spec, spec_path, rep)
    inv = metaads.inventory(res, rep)
    (out / "inventory.json").write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "inventory.md").write_text(metaads.inventory_md(res, inv), encoding="utf-8")
    if rep.errors:
        print(f"{len(rep.errors)} error(s); fix ads.json and re-run (details in {out / 'inventory.md'}):")
        for e in rep.errors[:30]:
            print(f"  {e['where']}: {e['message']}")
        sys.exit(1)

    # media: copy each unique file once
    out_media = {}
    stored = 0
    for mid, m in res["media"].items():
        o = {k: m.get(k) for k in ("kind", "label", "ratio", "aspect", "w", "h", "duration", "color", "placeholder")}
        if not m.get("placeholder"):
            rel, sha = store(m["path"], media_dir)
            o["src"] = rel
            stored += 1
            if m["kind"] == "video":
                if m.get("poster_path"):
                    o["poster"], _ = store(m["poster_path"], media_dir, ".poster")
                else:
                    o["poster"] = make_poster(m["path"], media_dir, sha)
        out_media[mid] = o
    unique_files = len({p.name for p in media_dir.iterdir() if p.is_file()})

    ads = []
    for ad in res["ads"]:
        ads.append({k: v for k, v in ad.items() if not k.startswith("_")})
    data = {
        "campaign": res["campaign"],
        "brands": res["brands"],
        "media": out_media,
        "ads": ads,
        "matrix": res["matrix"],
        "placements": res["placements"],
        "cta": res["cta"],
        "placements_version": res["placements_version"],
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
    }
    (out / "data.js").write_text("window.META_ADS = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    shutil.copy2(VIEWER, out / "index.html")
    # Self-contained snapshot: same spec, media paths pointing at the stored copies, so the
    # output folder can be re-rendered or moved. The agent's working ads.json is never touched.
    snap = json.loads(json.dumps(spec))
    for mid, m in (snap.get("media") or {}).items():
        if isinstance(m, dict) and mid in out_media and out_media[mid].get("src"):
            m["src"] = out_media[mid]["src"]
            if out_media[mid].get("poster"):
                m["poster"] = out_media[mid]["poster"]
    snap_path = out / "ads.snapshot.json"
    if snap_path.resolve() != spec_path.resolve():
        snap_path.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")

    c = inv["counts"]
    print(f"Rendered {len(ads)} ads into {out}")
    print(f"  {c.get('ready',0)} ready, {c.get('simulated',0)} simulated, {c.get('not_eligible',0)} not eligible mockups")
    print(f"  media: {stored} referenced files -> {unique_files} unique files in media/")
    if rep.warnings:
        print(f"  {len(rep.warnings)} warning(s), see inventory.md")
    print(f"  open: {out / 'index.html'}")
    if a.open:
        import webbrowser
        webbrowser.open((out / "index.html").as_uri())


if __name__ == "__main__":
    main()
