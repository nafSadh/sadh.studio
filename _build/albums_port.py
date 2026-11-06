#!/usr/bin/env python3
"""Port a shoot's posts (~/photos/posts/<shoot>/) into albums/<slug>/ at web quality.

    python3 _build/albums_port.py ~/photos                 # every shoot under ~/photos/posts
    python3 _build/albums_port.py ~/photos "26.10.17 Panther"
    ... --force   rewrite album.yaml (default: keep an existing one, only refresh img/)

The album keeps the shoot's own structure: one section per post folder, frames in post order.
Posts come from <shoot>/README.json (either dialect), else each post folder's README.json,
else the jpgs in the folder. Story (9:16) folders and _held/_archive folders are skipped; a frame
shown in an earlier post is not repeated.

Images: the uncropped edit, not the Instagram crop -- the README's src, else photos/<id>.jpg in
this repo, else the newest ~/photos/**/edits/<id>*.jpg, else the post file itself. Written as
albums/<slug>/img/<id>.jpg, long edge 1400px, which is what the album page loads.
"""
import json, os, re, sys, hashlib
from datetime import datetime
from PIL import Image, ImageOps
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE, QUAL = 1400, 82
ID_RE = re.compile(r"(DSCF\d{4}|_?DSC\d{4}|P[1-9A-C]\d{6}|IMG_\d{4})")
SKIP_DIR = re.compile(r"^[_.]|stories|9x16", re.I)
ORIENT = re.compile(r"[-_ ](wide|tall|horizontals?|verticals?)$", re.I)
MONTHS = "January February March April May June July August September October November December".split()

# the card/heading text per shoot; anything not listed uses the folder name
NAMES = {
    "25.12 Hawaii - Oahu": ("Oʻahu", "in Winter 2025"),
    "25.12.13 Walk": ("San Francisco", "Mission Walk"),
    "26.01 Austin": ("Austin", "Texas"),
    "26.01.16 Yosemite": ("Yosemite", "in Winter"),
    "26.01.31 Carmel": ("Carmel", "by-the-Sea"),
    "26.05 Misc": ("Apartment Studies", "Window Light, Macros & Dusk"),
    "26.05 Shasta": ("Shasta", "Cascade"),
    "26.05 Santa Cruz": ("Santa Cruz", "West Cliff"),
    "26.05.23 Yosemite": ("Yosemite", "in Spring"),
    "26.05.25 Coastal North": ("Coastal North", "Marin to Mendocino"),
    "26.06 dtSJ": ("San José", "Downtown"),
    "26.06.20 Rose Garden": ("Rose Garden", "San José"),
    "26.06.27 Clouds & Chefs": ("Silicon Valley", "Clouds & Hills"),
    "26.06.28 Monterey Coast": ("Monterey", "Coast"),
    "26.07.04 SF": ("San Francisco", "Fourth of July"),
    "26.07.12 SF Clouds and Colors": ("San Francisco", "Clouds and Colors"),
    "26.08 LA Trip": ("LA Trip", "Santa Barbara, Malibu & Cachuma"),
    "26.08.09 Santa Cruz": ("Santa Cruz", "Redwoods & Coast"),
    "26.09 Tahoe": ("Tahoe", "& Fallen Leaf"),
    "26.09.13 dtLA": ("Los Angeles", "Downtown"),
    "26.10.17 Panther": ("Panther", "Beach"),
    "26.10 New York Trip": ("New York", "in Fall 2026"),
}
SLUGS = {
    "25.12 Hawaii - Oahu": "2512-oahu",
    "25.12 Misc": "2512-dtsj-rooftop",
    "25.12.13 Walk": "2512-walk",
    "25.12.14 Walk": "2605-apt-studies",
    "25.12.15 dtSJ Rooftop": "2512-dtsj-rooftop",
    "25.12.27 Party": "2512-party",
    "25.12.27 Portraits": "2512-portraits",
    "25.12.28 Brunch": "2512-brunch",
    "25.12.29-30 Miro": "2605-apt-studies",
    "25.12.31 to HNY": "2512-new-years-eve",
    "26.01 Macros": "2605-apt-studies",
    "26.01 Miro": "2601-miro",
    "26.01.10 Biryani by Bal": "2601-biryani",
    "26.01.11 SF Museum": "2601-sf-museum",
    "26.01.31 Carmel": "2601-carmel",
    "26.03.20 Knoxville Eid": "2603-knoxville-eid",
    "26.04.05 Napa": "2604-napa",
    "26.04.18 H Cowell": "2604-henry-cowell",
    "26.05 Miro": "2605-apt-studies",
    "26.05 Misc": "2605-apt-studies",
    "26.05.17 Campbell": "2605-campbell",
    "26.06.27 Clouds & Chefs": "2606-clouds",
    "26.07 Misc": "2607-misc",
    "26.07.12 SF Clouds and Colors": "2607-sf-clouds",
    "26.07.15 Rooftop Pizza": "2607-rooftop-pizza",
    "26.07.18 Miro Chef's Dinner": "2607-chefs-dinner",
    "26.07.31 HMB": "2607-half-moon-bay",
    "26.08 LA Trip": "2608-la-trip",
    "26.08 Misc": "2608-august-walks",
    "26.08.07 SJ Rose Garden": "2608-rose-garden",
    "26.08.07 Zoom Burst": "2605-apt-studies",
    "26.08.08 Valley Fair": "2608-valley-fair",
    "26.08.28 Lights and Darks": "2608-lights-and-darks",
    "26.10 Portraits": "2610-portraits",
}
HIDDEN = set()


def human(name):
    n = re.sub(r"^\d+[a-z]?[-_ ]+|^[a-z]\d+[-_ ]+", "", name, flags=re.I)
    n = re.sub(r"[-_ ]?POSTED$", "", n)
    if not re.search(r"[-_ ]in[-_ ](horizontals?|verticals?)$", n, re.I): n = ORIENT.sub("", n)
    words = [WORDS.get(w.lower(), w) for w in n.replace("_", " ").replace("-", " ").split()]
    n = " ".join(words)
    return (n[:1].upper() + n[1:]) if n else name


WORDS = {"sf": "SF", "ptreyes": "Point Reyes", "citys": "city's", "hmb": "HMB", "la": "LA", "nyc": "NYC", "wc": "WC"}


def id_date(fid, year):
    """Olympus names carry the month and day: P5170717 = May 17 (A/B/C = Oct/Nov/Dec)."""
    m = re.match(r"P([1-9A-C])(\d\d)\d{4}$", fid)
    if not m: return None
    try: return datetime(year, int(m.group(1), 16), int(m.group(2)))
    except ValueError: return None


def short_title(t):
    t = re.split(r"\s+[—–]\s+|\s+--\s+", str(t))[0]      # "Verticals -- two days, ..." -> "Verticals"
    return t.replace("&amp;", "&").strip()


def slug_of(shoot):
    if shoot in SLUGS: return SLUGS[shoot]
    m = re.match(r"(\d\d)\.(\d\d)(?:\.\d\d)?\s+(.*)", shoot)
    name = NAMES.get(shoot, (m.group(3) if m else shoot, ""))[0]
    s = re.sub(r"[^a-z0-9]+", "-", name.lower().replace("é", "e").replace("ʻ", "")).strip("-")
    return f"{m.group(1)}{m.group(2)}-{s}" if m else s


def ids_in(folder):
    out = []
    for sub in ("", "for-insta"):
        d = os.path.join(folder, sub)
        if not os.path.isdir(d): continue
        for f in sorted(os.listdir(d)):
            m = ID_RE.search(f)
            if m and f.lower().endswith((".jpg", ".jpeg")) and m.group(1) not in [i for i, _ in out]:
                out.append((m.group(1), os.path.join(d, f)))
        if out: break                                   # prefer the folder's own files over for-insta
    return out


def read_posts(sdir):
    """-> [{"id", "title", "frames": [(id, hint path or None)]}] in post order"""
    posts = []
    rd = os.path.join(sdir, "README.json")
    top = json.load(open(rd)) if os.path.exists(rd) else {}
    if top.get("posts"):
        for i, p in enumerate(top["posts"]):
            fr = []
            for f in p.get("frames") or p.get("order") or []:
                fid = f.get("id") if isinstance(f, dict) else str(f)
                hint = f.get("src") if isinstance(f, dict) else None
                file = f.get("file") if isinstance(f, dict) else None
                fr.append((fid, hint, file))
            pid = str(p.get("id") or p.get("post_id") or i + 1)
            if SKIP_DIR.search(pid) or "stor" in str(p.get("name") or p.get("title") or "").lower(): continue
            posts.append({"id": pid, "title": short_title(p.get("name") or p.get("title") or human(pid)), "frames": fr})
    allfiles = {}
    for sub in sorted(os.listdir(sdir)):
        d = os.path.join(sdir, sub)
        if os.path.isdir(d) and not SKIP_DIR.search(sub):
            for fid, f in ids_in(d): allfiles.setdefault(fid, f)
    for p in posts:                                       # README frames without a file: find it in the post folders
        p["frames"] = [(fid, hint, file or allfiles.get(fid)) for fid, hint, file in p["frames"]]
    in_readme = {fid for p in posts for fid, _, _ in p["frames"]}
    for sub in sorted(os.listdir(sdir)):
        d = os.path.join(sdir, sub)
        if not os.path.isdir(d) or SKIP_DIR.search(sub): continue
        fids = [fid for fid, _ in ids_in(d)]
        if posts and fids and all(f in in_readme for f in fids): continue      # this folder is a README post
        if re.sub(r"^\d+[-_]", "", sub).lower() in {str(p["id"]).lower() for p in posts}: continue
        prd = os.path.join(d, "README.json")
        files = dict(ids_in(d))
        if os.path.exists(prd):
            p = json.load(open(prd))
            fr = [(o["id"], None, files.get(o["id"])) for o in p.get("order") or []]
            title = short_title(p.get("title") or human(sub))
        else:
            fr = [(fid, None, f) for fid, f in files.items()]
            title = human(sub)
        if "reddit" in sub.lower(): title = "Singles"
        posts.append({"id": re.sub(r"^\d+[-_]", "", sub).lower().replace("_", "-"), "title": title, "frames": fr})
    loose = [(fid, None, f) for fid, f in ids_in(sdir)]
    if loose: posts.append({"id": "frames", "title": human(re.sub(r"^[\d.]+\s+", "", os.path.basename(sdir))), "frames": loose})
    # merge neighbours that are one subject split by orientation (park-wide + park-tall)
    merged = []
    for p in posts:
        base = ORIENT.sub("", p["id"])
        if merged and ORIENT.sub("", merged[-1]["id"]) == base and base != p["id"] + "x":
            if ORIENT.search(p["id"]) or ORIENT.search(merged[-1]["id"]):
                merged[-1]["frames"] += p["frames"]; merged[-1]["id"] = base; continue
        merged.append(dict(p))
    return merged


EDITS = None
EDIT_DIRS = ("edits", "edited", "exports", "badger-jpeg", "cabin-jpeg", "Selected")
def edits_index(photos_root):
    global EDITS
    if EDITS is None:
        EDITS = {}
        for root, dirs, files in os.walk(photos_root):
            dirs[:] = [d for d in dirs if not d.startswith((".", "_")) and d != "posts"]
            if os.path.basename(root) not in EDIT_DIRS: continue
            for f in files:
                m = ID_RE.match(f)
                if m and f.lower().endswith((".jpg", ".jpeg")):
                    EDITS.setdefault(m.group(1), []).append(os.path.join(root, f))
    return EDITS


def source_for(fid, hint, file, shoot, photos_root, sdir):
    if hint:
        for base in (os.path.join(photos_root, shoot), sdir):
            p = os.path.join(base, hint)
            if os.path.isfile(p): return p
    p = os.path.join(REPO, "photos", fid + ".jpg")
    if os.path.isfile(p): return p
    cands = edits_index(photos_root).get(fid) or []
    pre = shoot[:5]                                      # "26.10": edits from the same month first
    cands = sorted(cands, key=lambda c: (pre not in c, -os.path.getmtime(c)))
    if cands: return cands[0]
    if file:
        for base in (sdir, os.path.join(sdir, "posts")):
            p = file if os.path.isabs(file) else os.path.join(base, file)
            if os.path.isfile(p): return p
        p = os.path.join(os.path.dirname(sdir), file)
        if os.path.isfile(p): return p
    return None


def taken(im):
    try:
        ex = im.getexif(); v = ex.get_ifd(0x8769).get(36867) or ex.get(306)
        return datetime.strptime(str(v)[:19], "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def port(photos_root, shoot, force=False):
    sdir = os.path.join(photos_root, "posts", shoot)
    slug = slug_of(shoot); out = os.path.join(REPO, "albums", slug)
    if os.path.exists(os.path.join(out, "index.html")):
        print(f"  {slug}: hand-built page, left alone"); return
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    y = os.path.join(out, "album.yaml")
    if os.path.exists(y) and not force:
        doc = yaml.safe_load(open(y, encoding="utf-8")) or {}
        posts = [{"id": p.get("id"), "title": p.get("title"),
                  "frames": [(str(fid), None, None) for fid in (p.get("frames") or [])]}
                 for p in (doc.get("posts") or [])]
    else:
        posts = read_posts(sdir) if os.path.isdir(sdir) else []
    seen, missing, dts = set(), [], []
    for p in posts:
        keep = []
        for fid, hint, file in p["frames"]:
            if not fid or fid in seen: continue
            dst = os.path.join(out, "img", fid + ".jpg")
            src = source_for(fid, hint, file, shoot, photos_root, sdir) if os.path.isdir(sdir) else source_for(fid, hint, file, shoot, photos_root, os.path.join(photos_root, shoot))
            if not src and os.path.exists(dst):
                seen.add(fid); keep.append(fid); continue
            if not src: missing.append(fid); continue
            im = Image.open(src); d = taken(im) or id_date(fid, 2000 + int(shoot[:2]))
            if d: dts.append(d)
            if not (os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src)):
                icc = im.info.get("icc_profile")
                im = ImageOps.exif_transpose(im).convert("RGB"); im.thumbnail((EDGE, EDGE), Image.LANCZOS)
                im.save(dst, "JPEG", quality=QUAL, optimize=True, progressive=True, **({"icc_profile": icc} if icc else {}))
            seen.add(fid); keep.append(fid)
        p["frames"] = keep
    posts = [p for p in posts if p["frames"]]
    for f in os.listdir(os.path.join(out, "img")):           # drop images no longer in the album
        if f.endswith(".jpg") and f[:-4] not in seen: os.remove(os.path.join(out, "img", f))
    if force or not os.path.exists(y):
        m = re.match(r"(\d\d)\.(\d\d)(?:\.(\d\d))?\s+(.*)", shoot)
        first = min(dts) if dts else datetime(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))
        last = max(dts) if dts else first
        name, sub = NAMES.get(shoot, (m.group(4), ""))
        doc = {"name": name, "sub": sub, "when": f"20{m.group(1)} {MONTHS[int(m.group(2)) - 1]}",
               "date": first.strftime("%Y-%m-%d"), "until": last.strftime("%Y-%m-%d"), "source": shoot,
               "hidden": shoot in HIDDEN,
               "posts": [{"id": p["id"], "title": p["title"], "frames": p["frames"]} for p in posts]}
        open(y, "w", encoding="utf-8").write(
            "# album: one section per post, frames in order. Edit freely; albums_port.py keeps this file\n"
            "# unless run with --force. hidden: true builds the page but keeps it off /albums/ and the feed.\n"
            + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=200))
    print(f"  {slug}: {len(posts)} posts, {len(seen)} frames" + (f", missing {missing}" if missing else ""))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = os.path.expanduser(args[0] if args else "~/photos")
    shoots = args[1:] or sorted(d for d in os.listdir(os.path.join(root, "posts")) if re.match(r"\d\d\.\d\d", d))
    for s in shoots: port(root, s, "--force" in sys.argv)
