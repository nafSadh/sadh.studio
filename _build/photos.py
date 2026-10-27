#!/usr/bin/env python3
"""Add or remove photos.

  ./run.sh add <file.jpg>... [--home | --stack <cover ID>] [--location "..."] [--caption "..."]
      Copies each edited export to photos/<ID>.jpg (ID = the camera ID, edit suffixes like -2
      dropped; long edge 3200px, capture date kept) and writes its entry into feed.yaml, by
      date, or into the stack fronted by <cover ID> with --stack; --home also adds it to the
      end of the wall (home.yaml). The location comes from --location, else from another
      photo exported from the same ~/photos album.
  ./run.sh rm <ID>...
      Deletes photos/<ID>.jpg and its entries in both files. If it fronted a stack, the next
      photo does.

Everything here can be done by editing the yaml by hand; ./run.sh check catches slips.
"""
import os, re, sys
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageOps
sys.path.insert(0, str(Path(__file__).resolve().parent))
import entries as E

REPO = Path(__file__).resolve().parent.parent
PDIR = REPO / "photos"
HOME, FEED = REPO / "home.yaml", REPO / "feed.yaml"
FULL_EDGE, FULL_Q = 3200, 88


def norm(name):
    m = re.match(r"^[A-Za-z]+\d+", name); return m.group(0) if m else name


def taken(path):
    im = Image.open(path); ex = im.getexif(); v = None
    try: v = ex.get_ifd(0x8769).get(36867)
    except Exception: pass
    v = v or ex.get(306)
    try: return datetime.strptime(str(v)[:19], "%Y:%m:%d %H:%M:%S")
    except Exception: return datetime.fromtimestamp(os.path.getmtime(path))


def every_photo(home, feed):
    """(photo dict, location) for every photo with details, wherever it is listed"""
    for p in home: yield p, p.get("location")
    for it in feed:
        if "photos" in it:
            for m in it.get("stack") or []: yield m, m.get("location") or it.get("location")
        else: yield it, it.get("location")


def add(files, home_=False, stack=None, location=None, caption=None):
    for f in files:
        hh, home = E.load(HOME); fh, feed = E.load(FEED)
        src = Path(f).expanduser().resolve(); pid = norm(src.stem)
        if any(str(p.get("photo")) == pid for p, _ in every_photo(home, feed)): print(f"  ! {pid} is already listed"); continue
        when = taken(src); im = Image.open(src)
        origin = "~/" + str(src.relative_to(Path.home())) if str(src).startswith(str(Path.home())) else str(src)
        origin = re.sub(r"^~/mnt/", "~/", origin)   # folders mounted under ~/mnt in a sandbox are ~/... on the Mac
        loc = location
        if not loc and origin.startswith("~/photos/"):
            album = origin.split("/")[2]
            loc = next((l for p, l in every_photo(home, feed) if str(p.get("origin") or "").startswith(f"~/photos/{album}/") and l), None)
        if not im.getexif().get(0x0131): print(f"  ! {pid}: no editing software in EXIF, looks like a camera JPEG (only edited exports belong here)")
        if max(im.size) < 2400: print(f"  ! {pid}: only {max(im.size)}px on the long edge, the lightbox will look soft")
        out = ImageOps.exif_transpose(im).convert("RGB"); out.thumbnail((FULL_EDGE, FULL_EDGE), Image.LANCZOS)
        ex = Image.Exif(); s = when.strftime("%Y:%m:%d %H:%M:%S"); ex[306] = s; ex.get_ifd(0x8769)[36867] = s
        out.save(PDIR / f"{pid}.jpg", "JPEG", quality=FULL_Q, optimize=True, progressive=True, exif=ex.tobytes())
        p = {"photo": pid, "origin": origin, "location": loc or "", "date": when.strftime("%Y-%m-%d %H:%M")}
        if caption: p["caption"] = caption
        where = "feed.yaml"
        if home_:
            home.append(p); E.dump(HOME, hh, home)
        if stack:
            cover = norm(stack); where = f"the stack fronted by {cover}"
            st = next((it for it in feed if str(it.get("photos")) == cover or ("photos" in it and any(str(m.get("photo")) == cover for m in it["stack"]))), None)
            if st is None:                    # start a stack from a single feed photo or a wall photo
                single = next((i for i, it in enumerate(feed) if str(it.get("photo")) == cover), None)
                if single is not None:
                    c = feed[single]
                    st = {"photos": cover, "location": c.get("location"), "date": c.get("date"),
                          "stack": [{k: v for k, v in c.items() if k not in ("location", "date", "caption")}]}
                    if c.get("caption"): st["caption"] = c["caption"]
                    feed[single] = st
                else: print(f"  ! {cover} isn't in feed.yaml; {pid} went into the feed on its own"); stack = None
            if st is not None:
                m = {k: v for k, v in p.items() if k not in ("date", "caption") and not (k == "location" and v == st.get("location"))}
                st["stack"].append(m); E.dump(FEED, fh, feed)
        if not stack:
            feed.insert(next((i for i, it in enumerate(feed) if str(it.get("date")) < p["date"]), len(feed)), p)
            E.dump(FEED, fh, feed)
        if home_: where += " and the end of the wall (home.yaml)"
        print(f"  + {pid} -> {where}  ({out.size[0]}x{out.size[1]}, taken {p['date']})" + ("" if loc else "  (fill in its location:)"))


def rm(ids):
    for pid in map(norm, ids):
        hh, home = E.load(HOME); fh, feed = E.load(FEED); found = False
        if any(str(h.get("photo")) == pid for h in home):
            home = [h for h in home if str(h.get("photo")) != pid]; found = True
        out = []
        for it in feed:
            if "photos" not in it:
                if str(it.get("photo")) == pid: found = True; continue
                out.append(it); continue
            st = [m for m in it.get("stack") or [] if str(m.get("photo")) != pid]
            if len(st) != len(it.get("stack") or []): found = True
            if str(it["photos"]) == pid and st:
                it["photos"] = str(st[0]["photo"]); it["date"] = taken(PDIR / f"{st[0]['photo']}.jpg").strftime("%Y-%m-%d %H:%M")
                print(f"    {it['photos']} now fronts that stack")
            if len(st) > 1: it["stack"] = st; out.append(it)
            elif st and len(st[0]) > 1:      # one photo left: back to a single photo
                one = dict(st[0]); one.setdefault("location", it.get("location")); one.setdefault("date", it.get("date"))
                if it.get("caption"): one.setdefault("caption", it["caption"])
                out.append({k: one[k] for k in E.PHOTO_KEYS if k in one})
        if not found: print(f"  ! {pid} isn't listed"); continue
        (PDIR / f"{pid}.jpg").unlink(missing_ok=True)       # file first: if that fails, nothing else changes
        E.dump(HOME, hh, home); E.dump(FEED, fh, out)
        print(f"  - {pid}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("add", "rm"): sys.exit(__doc__)
    opt = {"home": "--home" in a}
    if opt["home"]: a.remove("--home")
    for k in ("--location", "--caption", "--stack"):
        if k in a: i = a.index(k); opt[k[2:]] = a[i + 1]; del a[i:i + 2]
    if a[0] == "add": add(a[1:], opt["home"], opt.get("stack"), opt.get("location"), opt.get("caption"))
    else: rm(a[1:])
