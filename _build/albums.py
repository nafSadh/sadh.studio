"""Albums: albums/<slug>/album.yaml (+ img/<id>.jpg) -> /albums/<slug>/, /albums/, and the cards in the feed.

An album folder with its own index.html (hand-built, like 2610-new-york) is served as is; its
album.yaml only feeds the index and the feed card.

Images load from albums/<slug>/img/ unless albums/IMG_BASE holds a URL (e.g.
https://img.sadh.studio/albums/): then pages load <URL><slug>/<id>.jpg and img/ is not deployed.
"""
import os, re, json, hashlib, shutil, html as _html
from datetime import datetime, timedelta
from PIL import Image
import yaml

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
ADIR = os.path.join(REPO, "albums")
esc = lambda s: _html.escape(str(s or ""), quote=True)


def img_base():
    f = os.path.join(ADIR, "IMG_BASE")
    v = open(f).read().strip() if os.path.exists(f) else ""
    return (v.rstrip("/") + "/") if v else ""


def _hash(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()[:8]


COVER_EDGE, COVER_Q = 640, 76


def _covers(a):
    d = os.path.join(ADIR, a["slug"]); posts = a.get("posts") or []
    ids = [str(x) for x in (a.get("cover") or [])]
    if not ids:
        ids = [p["frames"][0] for p in posts if p.get("frames")][:3]
        for p in posts:
            for f in p.get("frames") or []:
                if len(ids) < 3 and f not in ids: ids.append(f)
    limit = 7 if len(ids) >= 5 else 3
    ids = ids[:limit]
    out, cdir, idir = [], os.path.join(d, "covers"), os.path.join(d, "img")
    keep = {f"{fid}.jpg" for fid in ids}
    ifiles = sorted(os.listdir(idir)) if os.path.isdir(idir) else []
    for fid in ids:
        dst = os.path.join(cdir, f"{fid}.jpg")
        fl = fid.lower()
        src = next((os.path.join(idir, f) for f in ifiles if f.lower() == f"{fl}.jpg" or (f.lower().startswith(fl) and f.lower().endswith(".jpg"))), None)
        if src and not (os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src)):
            os.makedirs(cdir, exist_ok=True)
            im = Image.open(src).convert("RGB"); im.thumbnail((COVER_EDGE, COVER_EDGE), Image.LANCZOS)
            im.save(dst, "JPEG", quality=COVER_Q, optimize=True, progressive=True)
        if os.path.exists(dst): out.append(f"/albums/{a['slug']}/covers/{fid}.jpg")
    if os.path.isdir(cdir):
        for f in os.listdir(cdir):
            if f.endswith(".jpg") and f not in keep:
                try: os.remove(os.path.join(cdir, f))
                except FileNotFoundError: pass
    return out


# cover mosaics: single cards are a 4:3 box split into up to 3 tiles; double-wide (.al.wide, 5-7 covers)
# cards span 2 columns at the exact height of neighboring 4:3 cards (~2.75:1 box). Pick the split and
# cover order that crops the cover photos least, keeping cover 1 in the lead tile unless moving it saves
# a clear amount of crop. Each entry: class -> [(tile aspect w/h, share of the box), ...].
MOSAICS = {
    7: {"m-7a": [(0.655, .238)] + [(1.40, .127)] * 6,                                              # 1 portrait hero + 3x2 landscapes
        "m-7b": [(0.54, .195), (1.14, .104), (1.14, .104), (0.54, .195), (1.14, .104), (1.14, .104), (0.54, .195)],  # 3 portraits + 2x2
        "m-7c": [(0.90, .328)] + [(1.23, .112)] * 6,                                               # 1 landscape/sq hero + 3x2
        "m-7d": [(0.66, .239), (1.91, .174), (0.96, .087), (0.96, .087), (0.96, .087), (0.96, .087), (0.66, .239)]}, # 2 portrait bookends + 1 wide + 4 cells
    6: {"m-6a": [(0.65, .236), (1.45, .132), (1.45, .132), (1.45, .132), (1.45, .132), (0.65, .236)],  # 2 portrait bookends + 2x2 4:3s
        "m-6b": [(0.66, .239), (2.79, .254), (1.39, .127), (1.39, .127), (1.39, .127), (1.39, .127)],  # 1 portrait + 1 wide pano + 4 4:3s
        "m-6c": [(1.83, 1/6)] * 6,                                                                     # 3x2 landscapes
        "m-6d": [(0.523, .19), (0.495, .18), (1.43, .13), (1.43, .13), (0.495, .18), (0.523, .19)]},   # 4 full-height portraits + center 2-stack
    5: {"m-5a": [(0.84, .304), (1.91, .174), (1.91, .174), (1.91, .174), (1.91, .174)],            # 1 hero left + 2x2 landscapes
        "m-5b": [(0.635, .231), (0.635, .231), (1.69, .154), (1.69, .154), (0.635, .231)]},        # 3 portraits + stacked pair
    3: {"": [(8/9, .5), (8/9, .25), (8/9, .25)],          # big tile left, two stacked right
        "m-half": [(2/3, .5), (4/3, .25), (4/3, .25)],     # tall half left, two wide right
        "m-tall2": [(.8, .6), (16/15, .2), (16/15, .2)],
        "m-wide": [(8/3, .5), (4/3, .25), (4/3, .25)],     # wide band on top, two below
        "m-wide2": [(20/9, .6), (5/3, .2), (5/3, .2)]},
    2: {"m-2c": [(2/3, .5), (2/3, .5)], "m-2r": [(8/3, .5), (8/3, .5)], "m-2t": [(8/9, 2/3), (4/9, 1/3)]},
}
MOVE_LEAD = .05                                            # crop share that moving cover 1 out of the big tile costs


def mosaic(a, covers=None):
    """-> (css class, covers in tile order)."""
    from itertools import permutations
    covers = list(covers if covers is not None else (a.get("covers") or [])[:3])
    d = os.path.join(ADIR, a["slug"], "covers"); rs = []
    for u in covers:
        try: w, h = Image.open(os.path.join(d, os.path.basename(u))).size; rs.append(w / h)
        except OSError: return "", covers
    opts = MOSAICS.get(len(rs))
    if not opts: return "", covers
    best = None
    for k, tiles in opts.items():
        for order in permutations(range(len(rs))):
            flip = sum(0.06 for (t, _), i in zip(tiles, order) if (t > 1) != (rs[i] > 1)) if len(rs) >= 5 else 0
            loss = sum(sh * (1 - min(t / rs[i], rs[i] / t)) for (t, sh), i in zip(tiles, order)) + flip + (MOVE_LEAD if order[0] else 0)
            key = (round(loss, 3), k != "", order != tuple(range(len(rs))))
            if best is None or key < best[0]: best = (key, k, order)
    return best[1], [covers[i] for i in best[2]]


def load():
    out = []
    if not os.path.isdir(ADIR): return out
    for slug in sorted(os.listdir(ADIR)):
        y = os.path.join(ADIR, slug, "album.yaml")
        if not os.path.isfile(y): continue
        a = yaml.safe_load(open(y, encoding="utf-8")) or {}
        a["slug"] = slug
        a["hand"] = os.path.isfile(os.path.join(ADIR, slug, "index.html"))
        a["date"] = datetime.strptime(str(a.get("date") or "2000-01-01"), "%Y-%m-%d")
        a["until"] = datetime.strptime(str(a.get("until") or a["date"].strftime("%Y-%m-%d")), "%Y-%m-%d")
        a["n"] = sum(len(p.get("frames") or []) for p in a.get("posts") or [])
        raw_covers = _covers(a)
        a["wide"] = len(raw_covers) >= 5
        a["mosaic"], a["covers"] = mosaic(a, raw_covers)
        a["feed_mosaic"], a["feed_covers"] = mosaic(a, raw_covers[:3])
        out.append(a)
    out.sort(key=lambda a: (not a["slug"].startswith("2600-"), a["until"]), reverse=True)
    return out


def card_html(href, when, name, sub, n, imgs, cls="", style="", mos=""):
    mosaic = (f'<span class="a-mosaic {mos}">' + "".join(f'<img loading="lazy" src="{esc(u)}" alt="">' for u in imgs[:3]) + "</span>") if imgs else ""
    sub = f'<span class="a-sub">{esc(sub)}</span>' if sub else ""
    st = f' style="{style}"' if style else ""
    return (f'<a class="acard dr-reveal{cls}" href="{href}"{st}>{mosaic}<span class="a-text"><span class="a-when">{esc(when)}</span>'
            f'<span class="a-name">{esc(name)}</span>{sub}<span class="a-n">{n} &rarr;</span></span></a>')


def card(a, cls="", style=""):
    return card_html(f"/albums/{a['slug']}/", a.get("when"), a.get("name"), a.get("sub"), f"album &middot; {a['n']} frames",
                     a.get("feed_covers") or a.get("covers") or [], cls, style, a.get("feed_mosaic", a.get("mosaic", "")))


def feed_end_cards(albums, n_wall, wall_thumbs):
    """End of the feed: back to home, and all albums."""
    listed = [a for a in albums if not a.get("hidden")]
    return [lambda st: card_html("/photos/", "home", "Still movements", "", f"{n_wall} frames", wall_thumbs, " more tile", st),
            lambda st: card_html("/albums/", "albums", "All albums", "", f"{len(listed)} albums",
                                 [a["covers"][0] for a in listed if a.get("covers")][:3], " more tile", st)]


def wall_cards(albums, n_photos, wall_thumbs):
    """End of the wall: the gallery and all albums."""
    listed = [a for a in albums if not a.get("hidden")]
    return [lambda st: card_html("/gallery/", "gallery", "The feed", "", f"{n_photos} frames", wall_thumbs, " more tile", st),
            lambda st: card_html("/albums/", "albums", "All albums", "", f"{len(listed)} albums",
                                 [a["covers"][0] for a in listed if a.get("covers")][:3], " more tile", st)]


INDEX_CSS = """
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));grid-auto-flow:dense;gap:36px 24px;margin-top:40px}
.al{display:flex;flex-direction:column;color:inherit;text-decoration:none}
.al.wide{grid-column:span 2;container-type:inline-size}
.al .mos{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);grid-template-rows:minmax(0,1fr) minmax(0,1fr);gap:4px;aspect-ratio:4/3;overflow:hidden;background:var(--bg2);border-radius:2px;box-shadow:0 0 0 1px color-mix(in oklab,var(--accent),transparent 86%),0 18px 40px -24px rgba(11,14,24,.38);transition:box-shadow .3s ease}
.al.wide .mos{gap:0;aspect-ratio:auto;height:calc((100cqw - 24px) * 3 / 8)}
.al .mos img{display:block;width:100%;height:100%;min-width:0;min-height:0;object-fit:cover;transition:transform .45s ease}
.al .mos img:first-child{grid-row:1/3}.al .mos img:only-child{grid-column:1/3}
/* 2- & 3-tile splits, picked per album by mosaic() */.al .mos.m-half{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.al .mos.m-tall2{grid-template-columns:minmax(0,3fr) minmax(0,2fr)}.al .mos.m-wide{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.al .mos.m-wide2{grid-template-columns:minmax(0,1fr) minmax(0,1fr);grid-template-rows:minmax(0,3fr) minmax(0,2fr)}.al .mos.m-wide img:first-child,.al .mos.m-wide2 img:first-child{grid-row:auto;grid-column:1/3}.al .mos.m-2c{grid-template-columns:minmax(0,1fr) minmax(0,1fr);grid-template-rows:minmax(0,1fr)}.al .mos.m-2t{grid-template-rows:minmax(0,1fr)}.al .mos.m-2r{grid-template-columns:minmax(0,1fr)}.al .mos.m-2c img:first-child,.al .mos.m-2t img:first-child,.al .mos.m-2r img:first-child{grid-row:auto}
/* 5-, 6- & 7-tile double-wide splits */
.al .mos.m-5a{grid-template-columns:minmax(0,7fr) minmax(0,8fr) minmax(0,8fr)}
.al .mos.m-5b{grid-template-columns:minmax(0,3fr) minmax(0,3fr) minmax(0,4fr) minmax(0,3fr)}.al .mos.m-5b img:nth-child(1){grid-column:1;grid-row:1/3}.al .mos.m-5b img:nth-child(2){grid-column:2;grid-row:1/3}.al .mos.m-5b img:nth-child(5){grid-column:4;grid-row:1/3}
.al .mos.m-6a{grid-template-columns:minmax(0,17fr) minmax(0,19fr) minmax(0,19fr) minmax(0,17fr)}.al .mos.m-6a img:nth-child(1){grid-column:1;grid-row:1/3}.al .mos.m-6a img:nth-child(6){grid-column:4;grid-row:1/3}
.al .mos.m-6b{grid-template-columns:minmax(0,17fr) minmax(0,18fr) minmax(0,18fr) minmax(0,18fr)}.al .mos.m-6b img:nth-child(1){grid-column:1;grid-row:1/3}.al .mos.m-6b img:nth-child(2){grid-column:2/4;grid-row:1}
.al .mos.m-6c{grid-template-columns:repeat(3,minmax(0,1fr))}.al .mos.m-6c img:first-child{grid-row:auto}
.al .mos.m-6d{grid-template-columns:minmax(0,19fr) minmax(0,18fr) minmax(0,26fr) minmax(0,18fr) minmax(0,19fr)}.al .mos.m-6d img:nth-child(1){grid-column:1;grid-row:1/3}.al .mos.m-6d img:nth-child(2){grid-column:2;grid-row:1/3}.al .mos.m-6d img:nth-child(5){grid-column:4;grid-row:1/3}.al .mos.m-6d img:nth-child(6){grid-column:5;grid-row:1/3}
.al .mos.m-7a{grid-template-columns:minmax(0,15fr) minmax(0,16fr) minmax(0,16fr) minmax(0,16fr)}
.al .mos.m-7b{grid-template-columns:minmax(0,16fr) minmax(0,17fr) minmax(0,16fr) minmax(0,17fr) minmax(0,16fr)}.al .mos.m-7b img:nth-child(1){grid-column:1;grid-row:1/3}.al .mos.m-7b img:nth-child(4){grid-column:3;grid-row:1/3}.al .mos.m-7b img:nth-child(7){grid-column:5;grid-row:1/3}
.al .mos.m-7c{grid-template-columns:minmax(0,22fr) minmax(0,15fr) minmax(0,15fr) minmax(0,15fr)}
.al .mos.m-7d{grid-template-columns:minmax(0,22fr) minmax(0,16fr) minmax(0,16fr) minmax(0,16fr) minmax(0,22fr)}.al .mos.m-7d img:nth-child(1){grid-column:1;grid-row:1/3}.al .mos.m-7d img:nth-child(2){grid-column:2/4;grid-row:1}.al .mos.m-7d img:nth-child(7){grid-column:5;grid-row:1/3}
.al:hover .mos{box-shadow:0 0 0 1px color-mix(in oklab,var(--accent),transparent 40%),0 22px 48px -20px color-mix(in oklab,var(--accent),transparent 68%)}
.al:hover .mos img{transform:scale(1.03)}
.al .when{display:flex;align-items:baseline;gap:6px;margin-bottom:8px;font-family:var(--mono);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
.al .when .n{color:var(--muted)}
.al h2{font-family:var(--display);font-weight:400;font-size:clamp(25px,2.5vw,33px);letter-spacing:-.02em;line-height:1.08;margin:12px 0 0}
.al h2 em{font-style:italic;color:var(--bruple)}
.al:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
@media (prefers-reduced-motion:reduce){.al .mos,.al .mos img{transition:none}.al:hover .mos img{transform:none}}
@media (max-width:680px){.grid{grid-template-columns:1fr;gap:28px}.al.wide{grid-column:span 1;container-type:normal}.al.wide .mos{height:auto;aspect-ratio:4/3;grid-template-columns:minmax(0,3fr) minmax(0,2fr) minmax(0,2fr)!important;grid-template-rows:minmax(0,1fr) minmax(0,1fr)!important}.al.wide .mos img{grid-column:auto!important;grid-row:auto!important}.al.wide .mos img:first-child{grid-row:1/3!important}.al.wide .mos img:nth-child(n+6){display:none}}
"""

THEME_BTN = ('<button type="button" class="cbtn tbtn" id="tbtn">'
             '<span class="t-dark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg><span class="sr">Switch to dark theme</span></span>'
             '<span class="t-light"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4.6"/><line x1="12" y1="1.7" x2="12" y2="3.7"/><line x1="12" y1="20.3" x2="12" y2="22.3"/><line x1="4.3" y1="4.3" x2="5.7" y2="5.7"/><line x1="18.3" y1="18.3" x2="19.7" y2="19.7"/><line x1="1.7" y1="12" x2="3.7" y2="12"/><line x1="20.3" y1="12" x2="22.3" y2="12"/><line x1="4.3" y1="19.7" x2="5.7" y2="18.3"/><line x1="18.3" y1="5.7" x2="19.7" y2="4.3"/></svg><span class="sr">Switch to light theme</span></span>'
             '</button>')
THEME_SCRIPT = ('<script>(()=>{const K="sadh-photos-theme",de=document.documentElement,m=document.querySelector(\'meta[name="color-scheme"]\'),b=document.getElementById("tbtn");'
                'const apply=v=>{if(v==="light"||v==="dark"){de.dataset.theme=v;if(m)m.content=v;}else{delete de.dataset.theme;if(m)m.content="light dark";}};'
                'if(b)b.onclick=()=>{const sys=matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light";const cur=de.dataset.theme||sys,next=cur==="dark"?"light":"dark";'
                'apply(next===sys?null:next);try{next===sys?localStorage.removeItem(K):localStorage.setItem(K,next);}catch{}};'
                'addEventListener("storage",e=>{if(e.key===K)apply(e.newValue);});})();</script></body></html>\n')


def index_page(tmpl, listed):
    """/albums/ in the album pages' own look: their head and styles, a grid of albums."""
    head = tmpl[:tmpl.find('<div class="wrap')].replace("{{TITLE_TEXT}} · sadh.studio", "Albums · sadh.studio")
    head = head.replace("</style>", INDEX_CSS + "</style>", 1).replace("<body>", '<body class="is-one">', 1)
    cards = []
    for a in listed:
        limit = 7 if a.get("wide") else 3
        imgs = "".join(f'<img loading="lazy" src="{esc(u)}" alt="">' for u in (a.get("covers") or [])[:limit])
        sub = f' <em>{esc(a.get("sub"))}</em>' if a.get("sub") else ""
        cls = "al wide" if a.get("wide") else "al"
        cards.append(f'<a class="{cls}" href="/albums/{a["slug"]}/">'
                     f'<span class="when"><span>{esc(a.get("when"))}</span><span class="n">&middot; {a["n"]} frames</span></span>'
                     f'<span class="mos {a.get("mosaic", "")}">{imgs}</span>'
                     f'<h2>{esc(a.get("name"))}{sub}</h2></a>')
    total = sum(a["n"] for a in listed)
    return (head + '<div class="wrap">\n  <header class="top"><div class="mast-txt">'
            f'<div class="kicker"><span>sadh.studio</span><span class="sep">&middot;</span><span>{len(listed)} albums &middot; {total} frames</span></div>'
            '<h1>Albums <em>by sadh</em></h1></div>\n'
            f'  <nav class="mnav" aria-label="Site"><a class="cbtn" href="/photos/">home</a><a class="cbtn" href="/gallery/">gallery</a>{THEME_BTN}</nav></header>\n'
            f'  <div class="grid">{"".join(cards)}</div>\n'
            '  <footer>photographs &copy; 2026 nafsadh &middot; <a href="/photos/">sadh.studio</a></footer>\n</div>\n'
            + THEME_SCRIPT)


def _short_nav(title):
    w = [x for x in re.split(r"[\s,&/—–-]+", str(title or "").strip())
         if x and x.lower() not in {"the", "a", "an", "of", "in", "on", "at", "to", "from", "and", "over", "across", "along", "through", "inside"}]
    return " ".join(w[:2]) if w else str(title or "")


def render_page(a, tmpl, base, feed_info=None):
    d = os.path.join(ADIR, a["slug"]); img = {}; posts = []; feed_info = feed_info or {}
    mf = os.path.join(d, "meta.json")
    meta = json.load(open(mf, encoding="utf-8")) if os.path.isfile(mf) else {}
    new_meta = {}
    has_idir = os.path.isdir(os.path.join(d, "img"))
    for p in a.get("posts") or []:
        fr = []
        for fid in p.get("frames") or []:
            fid = str(fid)
            f = os.path.join(d, "img", f"{fid}.jpg")
            if os.path.isfile(f):
                w, h = Image.open(f).size; v = _hash(f)
                new_meta[fid] = [w, h, v]
            elif fid in meta:
                w, h, v = meta[fid]
                new_meta[fid] = [w, h, v]
            else:
                print(f"  ! album {a['slug']}: no img/{fid}.jpg"); continue
            item = {"id": fid, "w": w, "h": h, "v": v}
            fi = feed_info.get(fid)
            if fi:
                item["hi"] = fi["hi"]
                if fi.get("t"): item["t"] = fi["t"]
                if fi.get("r"): item["r"] = fi["r"]
                if fi.get("ig"): item["ig"] = fi["ig"]
            fr.append(item); img[fid] = f"{fid}.jpg"
        if not fr: continue
        o = "portrait" if all(x["w"] <= x["h"] for x in fr) else "landscape" if all(x["w"] > x["h"] for x in fr) else "mixed"
        t = str(p.get("title") or "")
        s = str(p.get("nav") or _short_nav(t))
        posts.append({"id": str(p.get("id")), "t": t, "s": s, "day": "", "cap": "", "o": o, "f": fr})
    if has_idir and new_meta != meta:
        with open(mf, "w", encoding="utf-8") as out_f:
            json.dump(new_meta, out_f, separators=(",", ":"), sort_keys=True)
    name, sub = str(a.get("name") or a["slug"]), str(a.get("sub") or "")
    page = tmpl
    for k, v in {"TITLE_TEXT": esc(f"{name} {sub}".strip()), "NAME": esc(name), "SUB": esc(sub), "WHEN": esc(a.get("when")),
                 "IMG_JSON": json.dumps(img), "IMG_BASE": json.dumps(f"{base}{a['slug']}/" if base else "img/"),
                 "DATA_JSON": json.dumps({"posts": posts, "extras": []}, ensure_ascii=False)}.items():
        page = page.replace("{{" + k + "}}", v)
    if a.get("hidden"): page = page.replace("<head>", '<head><meta name="robots" content="noindex">', 1)
    return page


def deploy(out, darkroom_tmpl, styles_css, theme_js, feed_info=None):
    """Write /albums/<slug>/ for every album and the /albums/ index."""
    albums, base = load(), img_base()
    tmpl = open(os.path.join(HERE, "templates", "album.html"), encoding="utf-8").read()
    root = os.path.join(out, "albums"); shutil.rmtree(root, ignore_errors=True); os.makedirs(root, exist_ok=True)
    for a in albums:
        src, dst = os.path.join(ADIR, a["slug"]), os.path.join(root, a["slug"])
        if a["hand"]:
            shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("album.yaml", "meta.json", "abc.html", ".DS_Store", *(["img"] if base else [])))
            if base and not os.environ.get("GITHUB_ACTIONS") and os.path.isdir(os.path.join(src, "img")) and not os.path.exists(os.path.join(dst, "img")):
                os.symlink(os.path.join(src, "img"), os.path.join(dst, "img"))
            continue
        os.makedirs(dst, exist_ok=True)
        open(os.path.join(dst, "index.html"), "w", encoding="utf-8").write(render_page(a, tmpl, base, feed_info))
        if os.path.isdir(os.path.join(src, "covers")):
            shutil.copytree(os.path.join(src, "covers"), os.path.join(dst, "covers"))
        if os.path.isdir(os.path.join(src, "img")):
            if not base: shutil.copytree(os.path.join(src, "img"), os.path.join(dst, "img"))
            elif not os.environ.get("GITHUB_ACTIONS"): os.symlink(os.path.join(src, "img"), os.path.join(dst, "img"))
    listed = [a for a in albums if not a.get("hidden")]
    open(os.path.join(root, "index.html"), "w", encoding="utf-8").write(index_page(tmpl, listed))
    return albums
