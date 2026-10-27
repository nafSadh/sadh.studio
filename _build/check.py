#!/usr/bin/env python3
"""Sanity check for home.yaml / feed.yaml / photos/.  ./run.sh check

Warns about: wall photos whose home.yaml entry differs from feed.yaml, photos listed twice,
missing or unlisted files, IDs that aren't plain camera IDs, stacks without their cover,
missing or odd dates and locations, a date that disagrees with the file, reddit posts
missing a post id or sub, and exports too small for a sharp lightbox. The build prints
the same warnings.
"""
import os, re, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import entries as E

REPO = Path(__file__).resolve().parent.parent
PDIR = REPO / "photos"
ID = re.compile(r"^[A-Za-z]+\d+$")
FIELDS = ("origin", "location", "date", "caption", "ig", "reddit")


def _date(v):
    if isinstance(v, datetime): return v
    try: return datetime.strptime(str(v).strip(), "%Y-%m-%d %H:%M")
    except Exception: return None


def _exif_date(path):
    try:
        from PIL import Image
        ex = Image.open(path).getexif(); v = ex.get_ifd(0x8769).get(36867) or ex.get(306)
        return datetime.strptime(str(v)[:19], "%Y:%m:%d %H:%M:%S")
    except Exception: return None


def _norm(field, v):
    if v in (None, "", []): return None
    if field == "date": d = _date(v); return d.strftime("%Y-%m-%d %H:%M") if d else str(v)
    if field == "reddit": return sorted((str(r.get("sub", "")).removeprefix("r/").lower(), str(r.get("post", ""))) for r in v if isinstance(r, dict))
    return str(v).strip()


def run():
    W = []
    try: _, home = E.load(REPO / "home.yaml"); _, feed = E.load(REPO / "feed.yaml")
    except Exception as ex: return [f"can't read the yaml: {ex}"]
    # flatten feed.yaml: each photo with the location / date / caption it ends up with
    F, order = {}, []
    for it in feed:
        if "photos" in it:
            cover, st = str(it.get("photos") or ""), it.get("stack") or []
            ids = [str(m.get("photo") or "") for m in st]
            if cover not in ids: W.append(f"feed.yaml: stack {cover}: its cover isn't in its stack")
            elif ids[0] != cover: W.append(f"feed.yaml: stack {cover}: list the cover first")
            if len(st) < 2: W.append(f"feed.yaml: stack {cover} has {len(st)} photo(s); a single photo is just - photo:")
            for m in st:
                p = dict(m)
                for k in ("location", "caption"): p.setdefault(k, it.get(k))
                if str(m.get("photo")) == cover: p.setdefault("date", it.get("date"))
                p["_stack"] = cover; order.append(p)
        else: order.append(dict(it))
    for p in order:
        pid = str(p.get("photo") or "")
        if not pid: W.append("feed.yaml: an entry has no photo:"); continue
        if pid in F: W.append(f"feed.yaml: {pid} is listed twice")
        F[pid] = p
    H = {}
    for p in home:
        pid = str(p.get("photo") or "")
        if not pid: W.append("home.yaml: an entry has no photo:"); continue
        if pid in H: W.append(f"home.yaml: {pid} is listed twice")
        H[pid] = p
    for pid, h in H.items():                     # the wall vs the feed
        if pid not in F: W.append(f"{pid} is on the wall (home.yaml) but not in feed.yaml"); continue
        f = F[pid]
        for k in FIELDS:
            if k == "date" and "_stack" in f and pid != f["_stack"]: continue   # stacked photos carry no date
            a, b = _norm(k, h.get(k)), _norm(k, f.get(k))
            if a != b: W.append(f"{pid}: {k} differs -- home.yaml {h.get(k)!r}, feed.yaml {f.get(k)!r}")
    allp = {**F, **H}
    soft = []
    for pid, p in allp.items():
        where = "home.yaml" if pid in H and pid not in F else "feed.yaml"
        if not ID.match(pid): W.append(f"{pid}: not a plain camera ID (drop the edit suffix, e.g. -2)")
        f = PDIR / f"{pid}.jpg"
        if not f.exists(): W.append(f"{pid}: no file photos/{pid}.jpg"); continue
        if not p.get("location"): W.append(f"{pid}: no location ({where})")
        if not p.get("origin"): W.append(f"{pid}: no origin ({where})")
        elif str(p["origin"]).startswith("~/photos/") and (Path.home() / "photos").is_dir() and not (Path.home() / str(p["origin"])[2:]).exists():
            W.append(f"{pid}: origin {p['origin']} isn't there anymore")
        for r in p.get("reddit") or []:
            if not isinstance(r, dict) or not r.get("post") or not r.get("sub"): W.append(f"{pid}: a reddit entry needs post: and sub: ({where})")
        if p.get("date") is not None or "_stack" not in p or pid == p.get("_stack"):
            d = _date(p.get("date"))
            if d is None: W.append(f"{pid}: date {p.get('date')!r} isn't YYYY-MM-DD HH:MM ({where})")
            else:
                x = _exif_date(f)
                if x and abs((x.replace(second=0) - d).total_seconds()) > 60: W.append(f"{pid}: date {d:%Y-%m-%d %H:%M} but the file says {x:%Y-%m-%d %H:%M}")
        try:
            from PIL import Image
            if max(Image.open(f).size) < 2400: soft.append(f"{pid} {max(Image.open(f).size)}px")
        except Exception: pass
    for fn in sorted(os.listdir(PDIR)):
        if fn.lower().endswith(".jpg") and fn[:-4] not in allp: W.append(f"photos/{fn} isn't listed anywhere")
    if soft: W.append(f"small exports, the lightbox will look soft ({len(soft)}): " + ", ".join(soft))
    return W


if __name__ == "__main__":
    w = run()
    for x in w: print("  ! " + x)
    print("all good" if not w else f"{len(w)} warning(s)")
    sys.exit(1 if w and "--strict" in sys.argv else 0)
