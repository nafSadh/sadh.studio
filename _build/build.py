#!/usr/bin/env python3
"""Static-site generator for sadh.studio (still movements).

Reads:  home.yaml (the wall, in order), feed.yaml (the rest of the feed), photos/<id>.jpg, CNAME
Writes: _site/**  (the wall at /photos/, the feed at /photos/all/ and /photo/, one page per
        photo at /photo/<id>/, plus /photo/<id>.jpg and /photo/<id>.thumb.jpg)

The generated tree is what the GitHub Actions workflow uploads to Pages.
Run locally with ./run.sh (build + serve). Photo files are the web exports (long edge
up to 3200px, capture date in EXIF); the build makes the 760px thumbnails.
"""
import re, os, json, base64, html as _html, urllib.parse, io
from PIL import Image, ImageOps
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))        # _build/
REPO = os.path.dirname(HERE)
OUT  = os.path.join(REPO, "_site")

# ── output: _site/ is rebuilt from scratch every run ──────────────────────────
import shutil
DEPLOY = OUT
# keep _site/photo/*.jpg between runs (copying ~400MB of photos every rebuild is slow); everything
# else is regenerated, and photos that are no longer listed are removed at the end
os.makedirs(os.path.join(OUT, "photo"), exist_ok=True)
for _n in os.listdir(OUT):
    if _n != "photo": shutil.rmtree(os.path.join(OUT, _n), ignore_errors=True) if os.path.isdir(os.path.join(OUT, _n)) else os.remove(os.path.join(OUT, _n))
for _n in os.listdir(os.path.join(OUT, "photo")):
    if os.path.isdir(os.path.join(OUT, "photo", _n)): shutil.rmtree(os.path.join(OUT, "photo", _n))
FULL_EDGE, FULL_Q = 3200, 88

# ── manifest: feed.yaml (every photo, with stacks) + home.yaml (the wall, in order) ──
__import__("sys").path.insert(0, HERE)
import entries, check
for _w in check.run(): print("  ! " + _w)          # same warnings as ./run.sh check
DOMAIN = open(os.path.join(REPO, "CNAME")).read().strip() if os.path.exists(os.path.join(REPO, "CNAME")) else "sadh.studio"
def _when(v):
    if isinstance(v, datetime): return v
    try: return datetime.strptime(str(v).strip()[:16], "%Y-%m-%d %H:%M")
    except Exception: return None
def _entry(it, shared=None):
    shared = shared or {}
    pid = str(it.get("photo") or ""); f = os.path.join("photos", pid + ".jpg")
    if not pid or not os.path.isfile(os.path.join(REPO, f)): return None
    rd = []
    for r in it.get("reddit") or []:
        if not isinstance(r, dict) or not r.get("post") or not r.get("sub"): continue
        sub = str(r["sub"]); sub = sub if sub.startswith("r/") else "r/" + sub
        rd.append({"sub": sub, "ups": None, "views": None, "display": sub, "url": f"https://www.reddit.com/{sub}/comments/{r['post']}/"})
    ig = it.get("ig")
    return {"id": pid, "file": f, "filename": os.path.basename(str(it.get("origin") or f)),
            "title": str(it.get("caption") or shared.get("caption") or ""), "place": str(it.get("location") or shared.get("location") or ""),
            "reddit": rd, "instagram": f"https://www.instagram.com/p/{ig}/" if ig else None, "fivehundredpx": None,
            "dt": _when(it.get("date") or shared.get("date")), "wall": False}
_, HOME_ = entries.load(os.path.join(REPO, "home.yaml"))
_, FEED_ = entries.load(os.path.join(REPO, "feed.yaml"))
WALL = {}                                           # the wall: home.yaml order; its details win for photos in both files
for n, it in enumerate(HOME_):
    e = _entry(it)
    if e and e["id"] not in WALL: e["wall"], e["order"] = True, n; WALL[e["id"]] = e
manifest, byid = [], {}
def _take(it, shared=None):
    pid = str(it.get("photo") or "")
    if pid in byid: return byid[pid]
    e = WALL.get(pid) or _entry(it, shared)
    if e: manifest.append(e); byid[pid] = e
    return e
for it in FEED_:
    if "photos" not in it: _take(it); continue
    cover = str(it["photos"]); shared = {k: it.get(k) for k in ("location", "date", "caption")}; ids = []
    for m in it.get("stack") or []:
        pid = str(m.get("photo") or "")
        e = _take(m, {**shared, "date": shared["date"] if pid == cover else None})
        if e and pid not in ids: ids.append(pid)
    if cover in ids and len(ids) > 1:
        for pid in ids: byid[pid]["group"] = cover
for pid, e in WALL.items():                          # on the wall but missing from feed.yaml: still in the feed
    if pid not in byid: manifest.append(e); byid[pid] = e
print(f"loaded {len(manifest)} photos, {len(WALL)} on the wall")

def _dt(e):
    """date: from the yaml; the file's EXIF time breaks ties inside the same minute."""
    ex = capture_dt(e["file"]); d = e.get("dt")
    return ex if (d is None or ex.strftime("%Y-%m-%d %H:%M") == d.strftime("%Y-%m-%d %H:%M")) else d
# thumbnails are generated from each frame's EDITED file (base64-embedded, disk-cached)
PHOTOSROOT = REPO
TCACHE = os.path.join(REPO, ".cache", "thumbs"); os.makedirs(TCACHE, exist_ok=True)
def make_thumb(file):
    srcp = os.path.join(PHOTOSROOT, file)
    cb = os.path.join(TCACHE, re.sub(r"[^A-Za-z0-9._-]", "_", file) + ".jpg")
    if not (os.path.exists(cb) and os.path.getmtime(cb) >= os.path.getmtime(srcp)):
        im = ImageOps.exif_transpose(Image.open(srcp)).convert("RGB")   # honor EXIF rotation
        im.thumbnail((760, 760), Image.LANCZOS)
        im.save(cb, "JPEG", quality=66, optimize=True)
    w, h = Image.open(cb).size
    if DEPLOY:
        pid = os.path.splitext(os.path.basename(file))[0]
        tp = os.path.join(DEPLOY, "photo", pid + ".thumb.jpg")
        fp = os.path.join(DEPLOY, "photo", pid + ".jpg")
        if not (os.path.exists(tp) and os.path.getmtime(tp) >= os.path.getmtime(cb)):
            open(tp, "wb").write(open(cb, "rb").read())
        if not (os.path.exists(fp) and os.path.getmtime(fp) >= os.path.getmtime(srcp)):
            im = Image.open(srcp)
            if max(im.size) <= FULL_EDGE and im.getexif().get(0x0112, 1) == 1: shutil.copyfile(srcp, fp)
            else:
                im = ImageOps.exif_transpose(im).convert("RGB"); im.thumbnail((FULL_EDGE, FULL_EDGE), Image.LANCZOS)
                im.save(fp, "JPEG", quality=FULL_Q, optimize=True, progressive=True)
        return "/photo/" + pid + ".thumb.jpg", w, h
    return "data:image/jpeg;base64," + base64.b64encode(open(cb, "rb").read()).decode(), w, h

def capture_dt(file, hint=""):
    """Capture instant for chrono ordering: EXIF DateTimeOriginal, else the album-folder date."""
    srcp = os.path.join(PHOTOSROOT, file)
    try:
        ex = Image.open(srcp).getexif(); v = None
        try:
            sub = ex.get_ifd(0x8769); v = sub.get(36867) or sub.get(36868)   # DateTimeOriginal / Digitized
        except Exception: pass
        v = v or ex.get(306)                                                  # DateTime
        if v:
            try: return datetime.strptime(str(v)[:19], "%Y:%m:%d %H:%M:%S")
            except Exception: pass
    except Exception: pass
    m = re.match(r"^(\d{2})\.(\d{2})(?:[.\-](\d{2}))?", hint or file.split("/")[0])    # e.g. "26.05.09 Shasta"
    if m:
        yy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
        try: return datetime(2000 + yy, mm, dd)
        except Exception: pass
    return datetime.fromtimestamp(os.path.getmtime(srcp))

photos = []
for e in manifest:
    try:
        src, w, h = make_thumb(e["file"])
    except Exception as ex:
        print("  ! thumb fail", e["file"], ex); continue
    photos.append({**e, "src": src, "ar": round(w / h, 4), "dt": _dt(e)})
print(f"rendering {len(photos)} published photos")

def esc(s): return _html.escape(s or "", quote=True)
def q(f):
    if DEPLOY: return "/photo/" + os.path.splitext(os.path.basename(f))[0] + ".jpg"
    return "../" + urllib.parse.quote(f)

# variation groups (feed only): the stacks in feed.yaml; the cover leads, the rest sit behind it.
# The member whose id == group is shown in the feed; the rest sit behind it in the lightbox.
GROUPS = {}
for _i, _p in enumerate(photos):
    if _p.get("group"): GROUPS.setdefault(_p["group"], []).append(_i)
for _g, _mem in list(GROUPS.items()):
    _lead = next((i for i in _mem if photos[i]["id"] == _g), _mem[0])
    _mem.sort(key=lambda i: (i != _lead, photos[i]["dt"]))
    if len(_mem) < 2: del GROUPS[_g]
GROUP_LEAD = {mem[0]: mem for mem in GROUPS.values()}             # lead index -> member indices (lead first)
GROUP_OF   = {i: mem[0] for mem in GROUPS.values() for i in mem}  # any member -> lead index
DR_STACK = False                                                   # set while rendering the feed

# JS metadata (no base64 here)
meta_js = [{
    "id": p["id"], "t": p["title"], "pl": p["place"], "fn": p["filename"], "full": q(p["file"]), "ar": p["ar"],
    "r": [{"s": s["sub"], "d": s["display"], "url": s["url"]} for s in p["reddit"]],
    "ig": p["instagram"], "px": p["fivehundredpx"], "th": p["src"], "v": GROUP_LEAD.get(i),
} for i, p in enumerate(photos)]
PHOTOS_JSON = json.dumps(meta_js, ensure_ascii=False)

# Layout: equal pixel AREA per photo, native aspect ratio (NO crop). Photos are packed
# into ORIENTATION-PURE rows (all landscape OR all portrait) that ALTERNATE landscape/
# portrait, so a short landscape never sits beside a tall portrait. A trailing single is
# folded into the previous same-orientation row (→ a row of 2, which may then be mixed).
ORDER = sorted(range(len(photos)), key=lambda i: photos[i]["dt"], reverse=True)  # newest first
LAND = [i for i in ORDER if photos[i]["ar"] >= 1.0]   # landscape + square, reverse-chrono
PORT = [i for i in ORDER if photos[i]["ar"] < 1.0]    # portrait, reverse-chrono (independent stream)

def _pack(items, area, target_w, gap, extra=0):
    """Greedily pack indices into rows whose summed display widths (+gaps) fit target_w."""
    rows, cur, cw = [], [], 0.0
    for i in items:
        w = (area * photos[i]["ar"]) ** 0.5 + extra
        add = w + (gap if cur else 0)
        if cur and cw + add > target_w:
            rows.append(cur); cur, cw = [i], w
        else:
            cur.append(i); cw += add
    if cur: rows.append(cur)
    # no lonely singletons: borrow one from the previous row to make a pair
    if len(rows) > 1 and len(rows[-1]) == 1 and len(rows[-2]) > 1:
        rows[-1].insert(0, rows[-2].pop())
    return rows

CHRONO_ROWS = False

def alt_rows(area, target_w, gap, extra=0):
    """Interleave landscape-rows and portrait-rows (start with whichever has more rows)."""
    lr = _pack(LAND, area, target_w, gap, extra)
    pr = _pack(PORT, area, target_w, gap, extra)
    out, a, b, take_land = [], 0, 0, len(lr) >= len(pr)
    if CHRONO_ROWS:   # feed: newest row first, whichever orientation it is
        while a < len(lr) or b < len(pr):
            if b >= len(pr) or (a < len(lr) and photos[lr[a][0]]["dt"] >= photos[pr[b][0]]["dt"]): out.append(lr[a]); a += 1
            else: out.append(pr[b]); b += 1
        return out
    while a < len(lr) or b < len(pr):
        if take_land and a < len(lr): out.append(lr[a]); a += 1
        elif not take_land and b < len(pr): out.append(pr[b]); b += 1
        elif a < len(lr): out.append(lr[a]); a += 1
        else: out.append(pr[b]); b += 1
        take_land = not take_land
    return out

def render_rows(rows, tile, numbered=False):
    """Wrap each packed row in a .grow flex row; number tiles in display order if asked."""
    html, n = [], 0
    for row in rows:
        html.append('<div class="grow">')
        for i in row:
            n += 1
            html.append(tile(i, photos[i], n) if numbered else tile(i, photos[i]))
        html.append('</div>')
    return "".join(html)

# ── DARKROOM markup: exhibition wall (scroll-revealed) ───────────────────────
DR_AREA = 230 * 230
def dr_tile(i, p):
    w = round((DR_AREA * p["ar"]) ** 0.5)
    stack = DR_STACK and i in GROUP_LEAD
    return (f'<figure class="frame dr-reveal{" stack" if stack else ""}" data-i="{i}" style="width:{w}px">'
            f'<img loading="lazy" src="{p["src"]}" alt="{esc(p["title"])}">'
            + (f'<span class="vers">+{len(GROUP_LEAD[i]) - 1}</span>' if stack else '') +
            f'<span class="cap"><b>{esc(p["title"])}</b><i>{esc(p["place"])}</i></span></figure>')
TEMPLATES = os.path.join(HERE, "templates")
def _load_tmpl(name):
    return open(os.path.join(TEMPLATES, name), encoding="utf-8").read()

def _subst(tmpl, mapping):
    for k, v in mapping.items():
        tmpl = tmpl.replace("{{" + k + "}}", v)
    return tmpl

STYLES_CSS    = _load_tmpl("styles.css")
APP_JS_TMPL   = _load_tmpl("app.js")
DARKROOM_TMPL = _load_tmpl("darkroom.html")
PHOTO_TMPL    = _load_tmpl("photo.html")
NOT_FOUND_HTML = _load_tmpl("404.html")
REDIRECT_TMPL = _load_tmpl("redirect.html")

# /photos/ = the wall (home.yaml)
# /photos/all/ = every listed photo, newest first; /photo/#<id> resolves against the full set
def _darkroom_for(idx, kicker, order=None, feed=False):
    global LAND, PORT, DR_STACK, CHRONO_ROWS
    DR_STACK = CHRONO_ROWS = feed
    order = order or ORDER
    LAND = [i for i in order if i in idx and photos[i]["ar"] >= 1.0]
    PORT = [i for i in order if i in idx and photos[i]["ar"] < 1.0]
    wall_html = render_rows(alt_rows(DR_AREA, 1276, 22), dr_tile)
    app_js = _subst(APP_JS_TMPL, {"PHOTOS_JSON": PHOTOS_JSON})
    return _subst(DARKROOM_TMPL, {
        "HTML_ATTRS": 'data-groups="1" ' if feed else "",
        "STYLES_CSS": STYLES_CSS,
        "KICKER": kicker,
        "DR_WALL": wall_html,
        "APP_JS": app_js,
    })

# wall order = the order in home.yaml
ORDER_WALL = sorted((i for i in range(len(photos)) if photos[i]["wall"]), key=lambda i: photos[i]["order"])
wall_idx = set(ORDER_WALL)
all_idx  = {i for i in range(len(photos)) if GROUP_OF.get(i, i) == i}   # group members fold into their lead tile
html_wall = _darkroom_for(wall_idx, f'studio.sadh &middot; {len(wall_idx)} frames &middot; <a href="/photos/all/">all {len(photos)} &rarr;</a>', ORDER_WALL)
html_all  = _darkroom_for(all_idx,  f'studio.sadh &middot; all {len(photos)} frames &middot; <a href="/photos/">&larr; the wall</a>', feed=True)
for sub, html in (("photos", html_wall), (os.path.join("photos", "all"), html_all), ("photo", html_all)):
    os.makedirs(os.path.join(DEPLOY, sub), exist_ok=True)
    open(os.path.join(DEPLOY, sub, "index.html"), "w", encoding="utf-8").write(html)

# /photo/<id>/ — one tiny real page per frame: 200 + og:image for link previews, then on to /photo#<id>
for p in photos:
    d = os.path.join(DEPLOY, "photo", p["id"]); os.makedirs(d, exist_ok=True)
    t = esc(p["title"] or p["id"]); pl = esc(p["place"])
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(_subst(PHOTO_TMPL, {
        "TITLE": t,
        "PLACE": pl,
        "DOMAIN": DOMAIN,
        "ID": p["id"],
    }))

# 404.html: an unknown /photo/<something> still lands on the wall with the hash set
open(os.path.join(DEPLOY, "404.html"), "w", encoding="utf-8").write(NOT_FOUND_HTML)
open(os.path.join(DEPLOY, "index.html"), "w", encoding="utf-8").write(_subst(REDIRECT_TMPL, {"DOMAIN": DOMAIN}))

_keep = {p["id"] + ".jpg" for p in photos} | {p["id"] + ".thumb.jpg" for p in photos}
for _n in os.listdir(os.path.join(DEPLOY, "photo")):
    if _n.endswith(".jpg") and _n not in _keep: os.remove(os.path.join(DEPLOY, "photo", _n))
# Copy static /albums/** if present in repo root into _site/albums/
if os.path.isdir(os.path.join(REPO, "albums")):
    shutil.copytree(os.path.join(REPO, "albums"), os.path.join(DEPLOY, "albums"), dirs_exist_ok=True)
open(os.path.join(DEPLOY, "CNAME"), "w").write(DOMAIN + "\n")
open(os.path.join(DEPLOY, ".nojekyll"), "w").close()
n = len([f for f in os.listdir(os.path.join(DEPLOY, "photo")) if f.endswith(".jpg") and not f.endswith(".thumb.jpg")])
print(f"built _site/ -> /photos/ ({len(wall_idx)} on the wall), /photos/all/ + /photo/ ({len(photos)}), {n} fulls; / redirects to /photos/")

