"""The ad copy as a spreadsheet the user edits: ads.xlsx, next to a library's ads.json.

Usage:
    python sheet.py export LIBRARY_OR_ADS_JSON [--fresh]
    python sheet.py show   LIBRARY_OR_ADS_JSON [--ad ID]
    python sheet.py set    LIBRARY_OR_ADS_JSON AD_ID FIELD TEXT [--card N]

In a library, the sheet is the master for the words; ads.json keeps the setup (images, brands,
placements, formats). render.py creates the sheet on a library's first render and adds rows for
new ads on later ones. Every script that loads ads.json (check.py, render.py) reads ads.xlsx beside
it and applies its copy, cell by cell.

  export  writes ads.xlsx from ads.json. If it exists, it only adds rows for ads that aren't in it
          yet. --fresh rebuilds it from the current copy (the sheet's text over ads.json's), after
          copying the old sheet to backups/; it drops columns and formatting the user added.
  show    prints the current copy as JSON (what the mockups use). Read copy this way, not from
          ads.json, whose copy fields may be out of date.
  set     changes one field in the sheet and keeps everything else (formatting, the user's own
          columns). FIELD is one of: label, group, brand, primary_text, headline, description, cta,
          display_link, destination_url, notes (headline, description, cta, display_link and
          destination_url with --card N for a carousel card). \n in TEXT is a line break. For cta,
          give a label ("Book now") or a code (BOOK_NOW); "No button" removes it. An empty TEXT
          clears the field.

Columns are found by their header text, so the user can reorder them and add columns of their
own; those are ignored. Format and Source are shown for information and never read back. Writing
fails while the sheet is open in Excel (reading works: it sees the last saved version).
Needs openpyxl: https://openpyxl.readthedocs.io/en/stable/#installation
"""
import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metaads  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SHEET_NAME = "ads.xlsx"
INSTALL = "https://openpyxl.readthedocs.io/en/stable/#installation"


class SheetError(Exception):
    """Something the user can fix (close Excel, install openpyxl); the message says what."""
NO_BUTTON = "No button"
SAME_AS_AD = ""          # a card's blank Button means "the ad's button"

# (header, ad field, column width, editable)
AD_COLS = [
    ("ID", "id", 12, False),
    ("Ad name", "label", 26, True),
    ("Group", "group", 20, True),
    ("Brand", "brand", 20, True),
    ("Format", "format", 10, False),
    ("Primary text", "primary_text", 60, True),
    ("Primary text length", None, 11, False),
    ("Headline", "headline", 32, True),
    ("Headline length", None, 11, False),
    ("Description", "description", 32, True),
    ("Description length", None, 11, False),
    ("Button", "cta", 18, True),
    ("Display link", "display_link", 22, True),
    ("Destination URL", "destination_url", 30, True),
    ("Notes", "notes", 30, True),
    ("Source", "source", 24, False),
]
CARD_COLS = [
    ("Ad ID", "ad", 12, False),
    ("Card", "card", 6, False),
    ("Headline", "headline", 32, True),
    ("Headline length", None, 11, False),
    ("Description", "description", 32, True),
    ("Description length", None, 11, False),
    ("Button", "cta", 18, True),
    ("Display link", "display_link", 22, True),
    ("Destination URL", "destination_url", 30, True),
]
TEXT_FIELDS = ("label", "group", "primary_text", "headline", "description", "display_link", "destination_url", "notes")


def need_openpyxl():
    try:
        import openpyxl  # noqa: F401
        return openpyxl
    except ImportError:
        return None


def sheet_path(spec_path):
    return Path(spec_path).resolve().parent / SHEET_NAME


def _clean(v):
    """A cell's value as ad text: None for empty, line breaks as \\n."""
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).replace("_x000D_", "").replace("\r\n", "\n").replace("\r", "\n")
    return s if s.strip() else None


def _effective(ad, defaults, field):
    return ad[field] if field in ad else defaults.get(field)


def _text(v):
    """How a value shows in the sheet (notes may be any JSON; the sheet shows it as text)."""
    return v if v is None or isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def _is_button(code):
    return bool(code) and code != "NO_BUTTON"


def _limits():
    """Where Facebook Feed (mobile) cuts each text: the length the sheet flags."""
    cfg = metaads.load_placements()
    t = next((p for p in cfg["placements"] if p["id"] == "fb_feed_mobile"), cfg["placements"][0]).get("text") or {}
    return {f: (t.get(f) or {}).get("chars") or 0 for f in ("primary_text", "headline", "description")}


# --------------------------------------------------------------------------- reading
def apply(spec, spec_path, rep):
    """If ads.xlsx sits beside ads.json, put its copy into the spec (in memory). Returns a summary
    dict, or None when there's no sheet."""
    sp = sheet_path(spec_path)
    if not sp.exists():
        return None
    openpyxl = need_openpyxl()
    if openpyxl is None:
        rep.error("ads.xlsx", f"{sp.name} holds this library's copy, but reading it needs openpyxl: {INSTALL}")
        return None
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # "Data Validation extension is not supported": Excel's dropdowns; harmless when reading
            wb = openpyxl.load_workbook(sp, data_only=True, read_only=True)
    except PermissionError:
        rep.error("ads.xlsx", f"{sp} can't be read (is it locked by another program?)")
        return None
    except Exception as e:  # noqa: BLE001
        rep.error("ads.xlsx", f"{sp} can't be read: {e}")
        return None
    cta_labels = metaads.load_placements()["cta"]
    by_label = {l.lower(): c for c, l in cta_labels.items()}
    defaults = spec.get("defaults") or {}
    ads = {a.get("id"): a for a in (spec.get("ads") or []) if isinstance(a, dict)}
    brands = spec.get("brands") or {}
    brand_by_name = {(b.get("page_name") or "").strip().lower(): k for k, b in brands.items() if isinstance(b, dict)}
    changed = set()

    def cta_code(v, where):
        if v is None:
            return None
        s = v.strip()
        if s.lower() in (NO_BUTTON.lower(), "no_button", "none"):
            return "NO_BUTTON"
        if s.upper().replace(" ", "_") in cta_labels:
            return s.upper().replace(" ", "_")
        if s.lower() in by_label:
            return by_label[s.lower()]
        rep.warn(where, f"button '{s}' isn't one of Meta's labels; left as it was")
        return False

    def rows(ws_name, cols):
        if ws_name not in wb.sheetnames:
            return []
        it = wb[ws_name].iter_rows(values_only=True)
        head = next(it, None) or ()
        idx = {}
        for i, h in enumerate(head):
            h = (str(h).strip() if h is not None else "")
            for name, field, _w, editable in cols:
                if h.lower() == name.lower() and field and (editable or field in ("id", "ad", "card", "format")):
                    idx[field] = i
        out = []
        for n, r in enumerate(it, start=2):
            if not any(v not in (None, "") for v in r):
                continue
            out.append((n, {f: (r[i] if i < len(r) else None) for f, i in idx.items()}, set(idx)))
        return out

    for n, r, present in rows("Ads", AD_COLS):
        aid = _clean(r.get("id"))
        where = f"ads.xlsx Ads row {n}"
        if not aid or aid not in ads:
            rep.warn(where, f"no ad with ID '{aid}' in ads.json; row ignored")
            continue
        ad = ads[aid]
        for f in TEXT_FIELDS:
            if f not in present:
                continue
            new, old = _clean(r.get(f)), _text(_effective(ad, defaults, f))
            if (new or None) != (old or None):
                if new is None and f not in defaults and f in ("label", "group", "notes", "display_link", "destination_url"):
                    ad.pop(f, None)       # an empty cell: no value
                else:
                    ad[f] = new or ""     # an emptied text, or an emptied inherited value: no text
                changed.add(aid)
        if "brand" in present:
            v = _clean(r.get("brand"))
            if v:
                bid = v if v in brands else brand_by_name.get(v.lower())
                cur = _effective(ad, defaults, "brand") or next(iter(brands), None)
                if not bid:
                    rep.warn(f"{where}.Brand", f"no brand named '{v}'; left as it was")
                elif bid != cur:
                    ad["brand"] = bid
                    changed.add(aid)
        if "cta" in present:
            old = _effective(ad, defaults, "cta")
            old = str(old).strip().upper().replace(" ", "_") if old else None
            code = cta_code(_clean(r.get("cta")), f"{where}.Button")
            if code in (None, "NO_BUTTON"):      # blank or "No button": no button
                if _is_button(old):
                    ad["cta"] = None
                    changed.add(aid)
            elif code is not False and code != old:
                ad["cta"] = code
                changed.add(aid)
        if "format" in present:
            v = _clean(r.get("format"))
            if v and ad.get("format") and v.lower() != str(ad["format"]).lower():
                rep.warn(f"{where}.Format", f"the format is set in ads.json ({ad['format']}); the sheet can't change it")

    seen = {_clean(r.get("id")) for _n, r, _p in rows("Ads", AD_COLS)}
    missing = [a for a in ads if a and a not in seen]
    if missing and "Ads" in wb.sheetnames:
        rep.warn("ads.xlsx", f"{len(missing)} ad(s) have no row in the sheet and use ads.json's copy: {', '.join(missing[:8])}"
                 f"{'…' if len(missing) > 8 else ''} (sheet.py export adds their rows)")

    for n, r, present in rows("Cards", CARD_COLS):
        aid = _clean(r.get("ad"))
        where = f"ads.xlsx Cards row {n}"
        ad = ads.get(aid)
        try:
            k = int(r.get("card")) - 1
        except (TypeError, ValueError):
            k = -1
        cards = (ad or {}).get("cards")
        if not ad or not isinstance(cards, list) or not (0 <= k < len(cards)) or not isinstance(cards[k], dict):
            rep.warn(where, f"no card {r.get('card')} on ad '{aid}' in ads.json; row ignored")
            continue
        card = cards[k]
        for f in ("headline", "description", "display_link", "destination_url"):
            if f not in present:
                continue
            new, old = _clean(r.get(f)), card.get(f)
            if (new or None) != (old or None):
                if new is None:
                    card.pop(f, None)
                else:
                    card[f] = new
                changed.add(aid)
        if "cta" in present:
            v = _clean(r.get("cta"))
            if v is None:
                if "cta" in card:
                    card.pop("cta")
                    changed.add(aid)
            else:
                code = cta_code(v, f"{where}.Button")
                if code == "NO_BUTTON":
                    if "cta" not in card or card["cta"] not in (None, "NO_BUTTON"):
                        card["cta"] = None
                        changed.add(aid)
                elif code not in (False, None) and code != card.get("cta"):
                    card["cta"] = code
                    changed.add(aid)
    wb.close()
    try:
        json_newer = Path(spec_path).stat().st_mtime > sp.stat().st_mtime + 1
    except OSError:
        json_newer = False
    if changed and json_newer:
        ids = sorted(changed)
        rep.warn("ads.xlsx", f"ads.json was saved after ads.xlsx and {len(ids)} ad(s) have different copy in each: "
                 f"{', '.join(ids[:8])}{'…' if len(ids) > 8 else ''}. The sheet's text is used. "
                 "To change copy, change it in the sheet (sheet.py set); ads.json's copy is only the starting point.")
    return {"path": str(sp), "ads_changed": len(changed)}


# --------------------------------------------------------------------------- writing
def _ad_row(ad, defaults, brands, cta_labels):
    row = {}
    for _h, f, _w, _e in AD_COLS:
        if not f:
            continue
        v = _effective(ad, defaults, f) if f != "id" else ad.get("id")
        if f == "brand":
            bid = v or next(iter(brands), None)
            v = (brands.get(bid) or {}).get("page_name") or bid
        elif f == "cta":
            v = NO_BUTTON if v in (None, "NO_BUTTON") and ("cta" in ad or "cta" in defaults) else (cta_labels.get(str(v).upper(), v) if v else None)
        elif f in ("source", "notes"):
            v = _text(v)
        row[f] = v
    return row


def _card_rows(ad, cta_labels):
    out = []
    for i, c in enumerate(ad.get("cards") or []):
        if not isinstance(c, dict):
            continue
        cta = c.get("cta")
        if "cta" not in c:
            label = SAME_AS_AD                 # blank: the ad's button
        elif cta in (None, "NO_BUTTON"):
            label = NO_BUTTON                  # this card has none
        else:
            label = cta_labels.get(str(cta).upper(), cta)
        out.append({"ad": ad.get("id"), "card": i + 1, "headline": c.get("headline"), "description": c.get("description"),
                    "cta": label,
                    "display_link": c.get("display_link"), "destination_url": c.get("destination_url")})
    return out


def _style_sheet(ws, cols, limits):
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    head = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="E9EBEE")
    info_font = Font(color="7A7F87")
    for j, (h, f, w, editable) in enumerate(cols, start=1):
        c = ws.cell(row=1, column=j)
        c.font, c.fill = head, head_fill
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[get_column_letter(j)].width = w
        if not editable:
            for row in ws.iter_rows(min_row=2, min_col=j, max_col=j):
                for cell in row:
                    cell.font = info_font
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "C2"
    ws.row_dimensions[1].height = 32
    red = PatternFill("solid", start_color="F8D7DA", end_color="F8D7DA")   # a highlight is drawn from bgColor; set both
    red_text = Font(color="9C0006", bold=True)
    for j, (h, f, w, e) in enumerate(cols, start=1):
        if f is None and h.endswith(" length"):
            field = h[:-len(" length")].strip().lower().replace(" ", "_")
            lim = limits.get(field)
            if lim:
                col = get_column_letter(j)
                ws.conditional_formatting.add(f"{col}2:{col}5000", FormulaRule(formula=[f"AND(ISNUMBER({col}2),{col}2>{lim})"], fill=red, font=red_text))   # "" > n is TRUE in Excel


def _put(cell, v):
    """Set a value as plain text: copy that starts with = would otherwise become a formula."""
    cell.value = v
    if isinstance(v, str) and v.startswith("="):
        cell.data_type = "s"
    return cell


def _fill_rows(ws, cols, rows, start):
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter
    wrap = Alignment(wrap_text=True, vertical="top")
    letter = {f: get_column_letter(j) for j, (h, f, w, e) in enumerate(cols, start=1) if f}
    for i, r in enumerate(rows):
        n = start + i
        for j, (h, f, w, e) in enumerate(cols, start=1):
            if f:
                v = r.get(f)
                _put(ws.cell(row=n, column=j), v if v not in ("",) else None).alignment = wrap
            elif h.endswith(" length"):
                src = h[:-len(" length")].strip().lower().replace(" ", "_")
                ws.cell(row=n, column=j, value=f'=IF({letter[src]}{n}="","",LEN({letter[src]}{n}))').alignment = wrap


def _dropdowns(wb, brands, cta_labels):
    """(Re)build the Button and Brand dropdowns, finding the columns by header. openpyxl can't
    keep dropdowns Excel saved (they point at another tab, an Excel extension), so they're
    rebuilt every time this script saves the workbook. The lists live on a hidden tab, since a
    typed-in list is limited to 255 characters."""
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    ls = wb["Lists"] if "Lists" in wb.sheetnames else wb.create_sheet("Lists")
    ls.delete_cols(1, 2)
    labels = [NO_BUTTON] + [l for c, l in cta_labels.items() if c != "NO_BUTTON"]
    names = [(b.get("page_name") or k) for k, b in brands.items()] or [""]
    for i, l in enumerate(labels, start=1):
        ls.cell(row=i, column=1, value=l)
    for i, nm in enumerate(names, start=1):
        ls.cell(row=i, column=2, value=nm)
    ls.sheet_state = "hidden"
    lists = {"button": f"Lists!$A$1:$A${len(labels)}", "brand": f"Lists!$B$1:$B${len(names)}"}
    for tab, want in (("Ads", ("button", "brand")), ("Cards", ("button",))):
        if tab not in wb.sheetnames:
            continue
        ws = wb[tab]
        ws.data_validations.dataValidation = []
        for j, c in enumerate(ws[1], start=1):
            h = str(c.value or "").strip().lower()
            if h in want:
                col = get_column_letter(j)
                dv = DataValidation(type="list", formula1=lists[h], allow_blank=True, showErrorMessage=True,
                                    errorTitle=h.capitalize(), error=f"Pick a {h} from the list.")
                dv.add(f"{col}2:{col}5000")
                ws.add_data_validation(dv)


def export(target, fresh=False, quiet=False):
    """Returns {'path', 'created', 'added': [ad IDs]}."""
    openpyxl = need_openpyxl()
    if openpyxl is None:
        raise SheetError(f"Writing {SHEET_NAME} needs openpyxl: {INSTALL}")
    t = Path(target).resolve()
    spec_path = t / "ads.json" if t.is_dir() else t
    with open(spec_path, encoding="utf-8-sig") as f:
        spec = json.load(f)
    sp = sheet_path(spec_path)
    cfg = metaads.load_placements()
    cta_labels = cfg["cta"]
    defaults = spec.get("defaults") or {}
    brands = {k: v for k, v in (spec.get("brands") or {}).items() if isinstance(v, dict)}
    ads = [a for a in (spec.get("ads") or []) if isinstance(a, dict) and a.get("id")]
    limits = _limits()

    if sp.exists() and not fresh:
        import warnings
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")   # Excel's dropdowns: rebuilt below
                wb = openpyxl.load_workbook(sp)
        except PermissionError:
            raise SheetError(f"{sp} is open in another program (Excel?). Close it and run this again.")
        ws = wb["Ads"] if "Ads" in wb.sheetnames else None
        if ws is None:
            raise SheetError(f"{sp} has no Ads tab; rename it back to Ads, or rebuild with --fresh")
        from openpyxl.styles import Alignment
        from openpyxl.utils import get_column_letter
        wrap = Alignment(wrap_text=True, vertical="top")
        heads = [str(c.value or "").strip().lower() for c in ws[1]]
        if "id" not in heads:
            raise SheetError(f"{sp}: the Ads tab has no ID column")
        id_col = heads.index("id") + 1
        have = {str(row[0]).strip() for row in ws.iter_rows(min_row=2, min_col=id_col, max_col=id_col, values_only=True) if row[0] is not None}
        new_ads = [a for a in ads if a["id"] not in have]
        if not new_ads:
            if not quiet:
                print(f"{sp} already has every ad; nothing to add.")
            return {"path": sp, "created": False, "added": []}
        # append in the sheet's own column order; columns the user added stay empty
        order = [next((f for h, f, w, e in AD_COLS if h.lower() == hd), None) for hd in heads]
        start = ws.max_row + 1
        for i, a in enumerate(new_ads):
            r, n = _ad_row(a, defaults, brands, cta_labels), start + i
            for j, f in enumerate(order, start=1):
                if f:
                    _put(ws.cell(row=n, column=j), r.get(f)).alignment = wrap
                elif heads[j - 1].endswith(" length"):
                    src = heads[j - 1][:-len(" length")].strip().replace(" ", "_")
                    if src in order:
                        col = get_column_letter(order.index(src) + 1)
                        ws.cell(row=n, column=j, value=f'=IF({col}{n}="","",LEN({col}{n}))')
        card_rows = [r for a in new_ads for r in _card_rows(a, cta_labels)]
        if card_rows:
            if "Cards" not in wb.sheetnames:
                cw = wb.create_sheet("Cards", 1)
                cw.append([h for h, *_ in CARD_COLS])
                _style_sheet(cw, CARD_COLS, limits)
            cw = wb["Cards"]
            _fill_rows(cw, CARD_COLS, card_rows, cw.max_row + 1)
        _dropdowns(wb, brands, cta_labels)
        try:
            wb.save(sp)
        except PermissionError:
            raise SheetError(f"{sp} is open in another program (Excel?). Close it and run this again.")
        if not quiet:
            print(f"Added {len(new_ads)} ad(s) to {sp}: {', '.join(a['id'] for a in new_ads)}")
        return {"path": sp, "created": False, "added": [a["id"] for a in new_ads]}

    if sp.exists():
        # rebuild from the copy as it is now: the sheet's text over ads.json's
        rep = metaads.Report()
        apply(spec, spec_path, rep)
        for e in rep.errors:
            raise SheetError(f"Can't read the current sheet to keep its edits: {e['message']}")
        ads = [a for a in (spec.get("ads") or []) if isinstance(a, dict) and a.get("id")]
        bdir = sp.parent / "backups"
        bdir.mkdir(exist_ok=True)
        b = bdir / f"ads-{dt.datetime.now():%Y-%m-%d-%H%M%S}.xlsx"
        shutil.copy2(sp, b)
        if not quiet:
            print(f"Backed up the old sheet to {b}")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ads"
    ws.append([h for h, *_ in AD_COLS])
    _fill_rows(ws, AD_COLS, [_ad_row(a, defaults, brands, cta_labels) for a in ads], 2)
    _style_sheet(ws, AD_COLS, limits)
    card_rows = [r for a in ads for r in _card_rows(a, cta_labels)]
    if card_rows:
        cw = wb.create_sheet("Cards")
        cw.append([h for h, *_ in CARD_COLS])
        _fill_rows(cw, CARD_COLS, card_rows, 2)
        _style_sheet(cw, CARD_COLS, limits)
    _dropdowns(wb, brands, cta_labels)
    ab = wb.create_sheet("About")
    name = (spec.get("campaign") or {}).get("name") or spec_path.parent.name
    lines = [
        f"{name}: ad copy",
        "",
        "This sheet is where the ad copy lives. Edit the text here; the mockups use it.",
        "• Ads: one row per ad. Cards: the cards of carousel ads (a blank Button means the ad's button).",
        "• Grey columns are for information: ID, Format and Source. Don't change an ID; it links the row to its ad.",
        f"• The length columns turn red past what Facebook Feed shows before cutting the text "
        f"(primary text {limits['primary_text']}, headline {limits['headline']}, description {limits['description']} characters).",
        "• Line breaks (Alt+Enter) and emoji are kept.",
        "• You can add columns of your own and reorder them; columns are found by their header.",
        "• Images, brands and placements are set up in ads.json, beside this file. Ask Claude to change those.",
        "• After editing, ask Claude to re-render the library to see the changes in the viewer.",
    ]
    for i, l in enumerate(lines, start=1):
        ab.cell(row=i, column=1, value=l)
    from openpyxl.styles import Font
    ab["A1"].font = Font(bold=True, size=14)
    ab.column_dimensions["A"].width = 120
    try:
        wb.save(sp)
    except PermissionError:
        raise SheetError(f"{sp} is open in another program (Excel?). Close it and run this again.")
    if not quiet:
        print(f"Wrote {sp}: {len(ads)} ads{f', {len(card_rows)} carousel cards' if card_rows else ''}")
    return {"path": sp, "created": True, "added": [a["id"] for a in ads]}


def _spec_path(target):
    t = Path(target).resolve()
    return t / "ads.json" if t.is_dir() else t


def show(target, ad_id=None):
    """The copy as the mockups use it: the sheet's text over ads.json's."""
    spec, p, rep = metaads.load_spec(_spec_path(target))
    if spec is None or rep.errors:
        raise SheetError("; ".join(e["message"] for e in rep.errors) or "can't load the spec")
    defaults = spec.get("defaults") or {}
    out = []
    for a in spec.get("ads") or []:
        if not isinstance(a, dict) or (ad_id and a.get("id") != ad_id):
            continue
        row = {"id": a.get("id")}
        for f in ("label", "group", "brand", "primary_text", "headline", "description", "cta", "display_link", "destination_url", "notes"):
            v = _effective(a, defaults, f)
            if v not in (None, ""):
                row[f] = v
        if a.get("cards"):
            row["cards"] = [{k: c.get(k) for k in CARD_SET_FIELDS if c.get(k) not in (None, "")} for c in a["cards"] if isinstance(c, dict)]
        out.append(row)
    if ad_id and not out:
        raise SheetError(f"no ad with ID '{ad_id}'")
    sp = sheet_path(p)
    return {"sheet": str(sp) if sp.exists() else None, "ads": out}


SET_FIELDS = {"label": "Ad name", "group": "Group", "brand": "Brand", "primary_text": "Primary text", "headline": "Headline",
              "description": "Description", "cta": "Button", "display_link": "Display link", "destination_url": "Destination URL", "notes": "Notes"}
CARD_SET_FIELDS = ("headline", "description", "cta", "display_link", "destination_url")


def set_field(target, ad_id, field, text, card=None):
    """Change one cell of the sheet, keeping everything else. Returns {'path', 'row', 'column'}."""
    openpyxl = need_openpyxl()
    if openpyxl is None:
        raise SheetError(f"Writing {SHEET_NAME} needs openpyxl: {INSTALL}")
    field = field.strip().lower().replace(" ", "_")
    field = {"ad_name": "label", "name": "label", "button": "cta"}.get(field, field)
    if field not in SET_FIELDS or (card and field not in CARD_SET_FIELDS):
        allowed = CARD_SET_FIELDS if card else SET_FIELDS
        raise SheetError(f"can't set '{field}'{' on a card' if card else ''}; use one of: {', '.join(allowed)}")
    spec_path = _spec_path(target)
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    if not any(isinstance(a, dict) and a.get("id") == ad_id for a in spec.get("ads") or []):
        raise SheetError(f"no ad with ID '{ad_id}' in {spec_path}")
    sp = sheet_path(spec_path)
    export(spec_path, quiet=True)    # creates the sheet, or adds the ad's row if it's new
    cta_labels = metaads.load_placements()["cta"]
    brands = {k: b for k, b in (spec.get("brands") or {}).items() if isinstance(b, dict)}
    value = text.replace("\\n", "\n") if text else None
    if field == "cta" and value:
        v = value.strip()
        code = v.upper().replace(" ", "_")
        if v.lower() in (NO_BUTTON.lower(), "no_button", "none"):
            value = NO_BUTTON
        elif code in cta_labels:
            value = cta_labels[code]
        elif v.lower() in {l.lower() for l in cta_labels.values()}:
            value = next(l for l in cta_labels.values() if l.lower() == v.lower())
        else:
            raise SheetError(f"'{v}' isn't one of Meta's buttons (see the CTA table in SPEC.md)")
    if field == "brand" and value:
        if value in brands:
            value = brands[value].get("page_name") or value
        elif value.lower() not in {(b.get("page_name") or "").lower() for b in brands.values()}:
            raise SheetError(f"no brand '{value}'; brands: {', '.join((b.get('page_name') or k) for k, b in brands.items())}")
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = openpyxl.load_workbook(sp)
    except PermissionError:
        raise SheetError(f"{sp} is open in another program (Excel?). Close it and try again.")
    tab = "Cards" if card else "Ads"
    if tab not in wb.sheetnames:
        raise SheetError(f"{sp} has no {tab} tab")
    ws = wb[tab]
    heads = [str(c.value or "").strip().lower() for c in ws[1]]
    want = SET_FIELDS[field].lower()
    keys = ("ad id", "card") if card else ("id",)
    missing = [k for k in (want,) + keys if k not in heads]
    if missing:
        raise SheetError(f"the {tab} tab has no '{missing[0]}' column")
    row = next((r for r in range(2, ws.max_row + 1)
                if str(ws.cell(r, heads.index(keys[0]) + 1).value or "").strip() == ad_id
                and (not card or str(ws.cell(r, heads.index("card") + 1).value or "").strip() == str(card))), None)
    if row is None:
        raise SheetError(f"no row for ad '{ad_id}'{f' card {card}' if card else ''} in the {tab} tab")
    _put(ws.cell(row, heads.index(want) + 1), value)
    _dropdowns(wb, brands, cta_labels)
    try:
        wb.save(sp)
    except PermissionError:
        raise SheetError(f"{sp} is open in another program (Excel?). Close it and try again.")
    return {"path": sp, "row": row, "column": SET_FIELDS[field]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="write ads.xlsx from ads.json (adds new ads only if it exists)")
    e.add_argument("target", help="a library folder or an ads.json")
    e.add_argument("--fresh", action="store_true", help="rebuild the sheet from the current copy (backs up the old one; drops added columns)")
    sh = sub.add_parser("show", help="print the current copy (the sheet's text over ads.json's) as JSON")
    sh.add_argument("target")
    sh.add_argument("--ad", help="only this ad")
    st = sub.add_parser("set", help="change one field in the sheet")
    st.add_argument("target")
    st.add_argument("ad")
    st.add_argument("field")
    st.add_argument("text", help="the new text; \\n for a line break; empty to clear")
    st.add_argument("--card", type=int, help="a carousel card number (1-based)")
    a = ap.parse_args()
    try:
        if a.cmd == "export":
            export(a.target, a.fresh)
        elif a.cmd == "show":
            print(json.dumps(show(a.target, a.ad), indent=2, ensure_ascii=False))
        else:
            r = set_field(a.target, a.ad, a.field, a.text, a.card)
            print(f"Set {r['column']} of {a.ad}{f' card {a.card}' if a.card else ''} in {r['path']} (row {r['row']}). Re-render to see it.")
    except SheetError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()
