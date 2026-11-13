#!/usr/bin/env python3
"""Fold the site's feed into the albums: every feed.yaml frame from an album's dates and places that
the album lacks goes into the chapter nearest in time; the three card photos are the best performers
(on the wall, then Reddit posts, then Instagram). Images for added frames come from photos/<id>.jpg.

    python3 _build/albums_feed.py            # all albums
    python3 _build/albums_feed.py 2605-yosemite
"""
import os, sys, glob, yaml
from datetime import datetime
from PIL import Image, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import albums_port as ap

REPO = ap.REPO
PLACES = {                       # feed `location` values that belong to each album
    "2512-oahu": ["Oahu", "Oʻahu", "Honolulu", "Waikiki", "Hawaii", "Makapu"],
    "2512-walk": ["San Francisco"],
    "2601-austin": ["Austin"],
    "2601-sf-museum": ["San Francisco"],
    "2601-yosemite": ["Yosemite"],
    "2603-coastal-drive": ["Highway 1", "Half Moon Bay", "Carmel", "Capitola", "Pigeon Point"],
    "2605-coastal-north": ["Mendocino", "Point Reyes", "Sonoma Coast", "Muir Beach", "Bolinas Lagoon"],
    "2605-santa-cruz": ["Santa Cruz"], "2605-shasta": ["Shasta–Cascade", "Shasta"], "2605-yosemite": ["Yosemite"],
    "2606-clouds": ["San José", "Silicon Valley"],
    "2606-monterey": ["Monterey Coast", "Monterey"], "2606-rose-garden": ["Rose Garden", "Municipal Rose Garden"],
    "2606-san-jose": ["San José"], "2607-half-moon-bay": ["Half Moon Bay"], "2607-rooftop-pizza": [],
    "2607-san-francisco": ["San Francisco"], "2607-sf-clouds": ["San Francisco", "Baker Beach", "Fort Funston", "Lands End"],
    "2608-santa-cruz": ["Santa Cruz", "Henry Cowell"], "2609-los-angeles": ["Los Angeles"],
    "2609-tahoe": ["Lake Tahoe", "Fallen Leaf"], "2610-panther": ["Panther Beach"],
    "2610-new-york": ["New York", "Hudson Valley", "Sleepy Hollow", "Cold Spring"],
    "2611-knoxville": ["Knoxville", "Cades Cove", "Smokies", "Great Smoky Mountains"],
}

def feed_frames():
    feed = yaml.safe_load(open(os.path.join(REPO, "feed.yaml")))["contents"]
    wall = {str(i.get("photo")) for i in yaml.safe_load(open(os.path.join(REPO, "home.yaml")))["contents"]}
    out = []
    for it in feed:
        members = it.get("stack") or [it]
        for m in members:
            e = {**{k: it.get(k) for k in ("location", "date", "caption")}, **m}
            pid = str(e.get("photo") or "")
            if not pid: continue
            try: d = datetime.strptime(str(e.get("date"))[:16], "%Y-%m-%d %H:%M")
            except Exception:
                try: d = datetime.strptime(str(e.get("date"))[:10], "%Y-%m-%d")
                except Exception: d = None
            out.append({"id": pid, "dt": d, "place": str(e.get("location") or ""), "wall": pid in wall,
                        "score": (10 if pid in wall else 0) + 2 * len(e.get("reddit") or []) + (1 if e.get("ig") else 0)})
    return out

def taken(pid, slug):
    for f in (os.path.join(REPO, "photos", pid + ".jpg"), os.path.join(REPO, "albums", slug, "img", pid + ".jpg")):
        if os.path.exists(f):
            d = ap.taken(Image.open(f))
            if d: return d
    return None

def ensure_img(pid, slug):
    dst = os.path.join(REPO, "albums", slug, "img", pid + ".jpg")
    if os.path.exists(dst): return True
    src = os.path.join(REPO, "photos", pid + ".jpg")
    if not os.path.exists(src): return False
    im = Image.open(src); icc = im.info.get("icc_profile")
    im = ImageOps.exif_transpose(im).convert("RGB"); im.thumbnail((ap.EDGE, ap.EDGE), Image.LANCZOS)
    im.save(dst, "JPEG", quality=ap.QUAL, optimize=True, progressive=True, **({"icc_profile": icc} if icc else {}))
    return True

def fold(slug, frames):
    y = os.path.join(REPO, "albums", slug, "album.yaml")
    if not os.path.exists(y) or os.path.exists(os.path.join(REPO, "albums", slug, "index.html")): return
    txt = open(y, encoding="utf-8").read(); head = txt[:txt.find("name:")]; a = yaml.safe_load(txt)
    d0 = datetime.strptime(str(a["date"]), "%Y-%m-%d"); d1 = datetime.strptime(str(a["until"]), "%Y-%m-%d").replace(hour=23, minute=59)
    places = PLACES.get(slug, [])
    mine = [f for f in frames if f["dt"] and d0 <= f["dt"] <= d1 and any(p.lower() in f["place"].lower() for p in places)]
    have = {fid for p in a["posts"] for fid in p["frames"]}
    T = {}
    def t(pid):
        if pid not in T: T[pid] = taken(pid, slug) or next((f["dt"] for f in mine if f["id"] == pid), None)
        return T[pid]
    added = []
    for f in mine:
        if f["id"] in have or not ensure_img(f["id"], slug): continue
        ft = t(f["id"]); best, gap = None, None
        for p in a["posts"]:                         # chapter whose frames sit nearest in time
            ts = [t(x) for x in p["frames"] if t(x)]
            if not ts: continue
            g = min(abs((ft - x).total_seconds()) for x in ts) if ft else 1e18
            if gap is None or g < gap: best, gap = p, g
        best = best or a["posts"][0]
        fr = best["frames"]
        pos = next((i for i, x in enumerate(fr) if t(x) and ft and t(x) > ft), len(fr))
        fr.insert(pos, f["id"]); have.add(f["id"]); added.append(f["id"])
    score = {f["id"]: f["score"] for f in mine}
    ranked = sorted((fid for p in a["posts"] for fid in p["frames"]), key=lambda i: -score.get(i, 0))
    if not a.get("cover") and any(score.get(i, 0) for i in ranked[:3]): a["cover"] = ranked[:3]
    open(y, "w", encoding="utf-8").write(head + yaml.safe_dump(a, sort_keys=False, allow_unicode=True, width=200))
    print(f"  {slug}: +{len(added)} {added}  cover={a.get('cover')}")

if __name__ == "__main__":
    fr = feed_frames()
    slugs = sys.argv[1:] or sorted(os.path.basename(os.path.dirname(y)) for y in glob.glob(os.path.join(REPO, "albums", "*", "album.yaml")))
    for s in slugs: fold(s, fr)
