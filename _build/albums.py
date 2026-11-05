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
    out, cdir, idir = [], os.path.join(d, "covers"), os.path.join(d, "img")
    for fid in ids[:3]:
        dst = os.path.join(cdir, f"{fid}.jpg")
        src = next((os.path.join(idir, f) for f in sorted(os.listdir(idir)) if f.startswith(fid) and f.endswith(".jpg")), None) if os.path.isdir(idir) else None
        if src and not (os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src)):
            os.makedirs(cdir, exist_ok=True)
            im = Image.open(src).convert("RGB"); im.thumbnail((COVER_EDGE, COVER_EDGE), Image.LANCZOS)
            im.save(dst, "JPEG", quality=COVER_Q, optimize=True, progressive=True)
        if os.path.exists(dst): out.append(f"/albums/{a['slug']}/covers/{fid}.jpg")
    return out


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
        a["covers"] = _covers(a)
        out.append(a)
    out.sort(key=lambda a: a["until"], reverse=True)
    return out


def card_html(href, when, name, sub, n, imgs, cls="", style=""):
    mosaic = ('<span class="a-mosaic">' + "".join(f'<img loading="lazy" src="{esc(u)}" alt="">' for u in imgs[:3]) + "</span>") if imgs else ""
    sub = f'<span class="a-sub">{esc(sub)}</span>' if sub else ""
    st = f' style="{style}"' if style else ""
    return (f'<a class="acard dr-reveal{cls}" href="{href}"{st}>{mosaic}<span class="a-text"><span class="a-when">{esc(when)}</span>'
            f'<span class="a-name">{esc(name)}</span>{sub}<span class="a-n">{n} &rarr;</span></span></a>')


def card(a, cls="", style=""):
    return card_html(f"/albums/{a['slug']}/", a.get("when"), a.get("name"), a.get("sub"), f"album &middot; {a['n']} frames",
                     a.get("covers") or [], cls, style)


def feed_end_cards(albums, n_wall, wall_thumbs):
    """End of the feed: back to the wall, and all albums."""
    listed = [a for a in albums if not a.get("hidden")]
    return [lambda st: card_html("/photos/", "the wall", "Still movements", "", f"{n_wall} frames", wall_thumbs, " more tile", st),
            lambda st: card_html("/albums/", "albums", "All albums", "", f"{len(listed)} albums",
                                 [a["covers"][0] for a in listed if a.get("covers")][:3], " more tile", st)]


def wall_cards(albums, n_photos, wall_thumbs, newest=2):
    """End of the wall: the gallery, the newest albums, all albums -> [(html_fn(style), )] as card specs."""
    listed = [a for a in albums if not a.get("hidden")]
    specs = [lambda st: card_html("/photos/all/", "gallery", "All photos", "", f"{n_photos} frames", wall_thumbs, " more tile", st)]
    specs += [(lambda a: lambda st: card(a, " tile", st))(a) for a in listed[:newest]]
    rest = [a["covers"][0] for a in listed[newest:] if a.get("covers")][:3]      # albums not already in the row
    specs += [lambda st: card_html("/albums/", "albums", "All albums", "", f"{len(listed)} albums", rest, " more tile", st)]
    return specs


INDEX_CSS = """
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:36px 24px;margin-top:40px}
.al{display:flex;flex-direction:column;color:inherit;text-decoration:none}
.al .mos{display:grid;grid-template-columns:2fr 1fr;grid-template-rows:1fr 1fr;gap:4px;aspect-ratio:4/3;overflow:hidden;background:var(--rule)}
.al .mos img{display:block;width:100%;height:100%;object-fit:cover;transition:transform .45s ease}
.al .mos img:first-child{grid-row:1/3}.al .mos img:only-child{grid-column:1/3}
.al:hover .mos img{transform:scale(1.03)}
.al .when{margin-top:14px;font-family:var(--mono);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
.al h2{font-family:var(--display);font-weight:400;font-size:clamp(30px,3.2vw,40px);line-height:1.02;margin:4px 0 0}
.al h2 em{font-style:italic;color:var(--accent)}
.al .n{margin-top:6px;font-family:var(--mono);font-size:12px;color:var(--muted)}
.al:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
.meta a{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--rule)}.meta a:hover{border-bottom-color:var(--accent)}
@media (max-width:640px){.grid{grid-template-columns:1fr;gap:28px}}
"""


def index_page(tmpl, listed):
    """/albums/ in the album pages' own look: their head and styles, a grid of albums."""
    head = tmpl[:tmpl.find('<div class="wrap">')].replace("{{TITLE_TEXT}} · sadh.studio", "Albums · sadh.studio")
    head = head.replace("</style>", INDEX_CSS + "</style>", 1)
    cards = []
    for a in listed:
        imgs = "".join(f'<img loading="lazy" src="{esc(u)}" alt="">' for u in (a.get("covers") or [])[:3])
        sub = f' <em>{esc(a.get("sub"))}</em>' if a.get("sub") else ""
        cards.append(f'<a class="al" href="/albums/{a["slug"]}/"><span class="mos">{imgs}</span>'
                     f'<span class="when">{esc(a.get("when"))}</span><h2>{esc(a.get("name"))}{sub}</h2>'
                     f'<span class="n">{a["n"]} frames</span></a>')
    total = sum(a["n"] for a in listed)
    return (head + '<div class="wrap">\n  <header class="top"><h1>Albums <em>by sadh</em></h1>\n'
            f'  <div class="meta"><span>{len(listed)} albums &middot; {total} frames</span>'
            '<a href="/photos/">the wall</a><a href="/photos/all/">all photos</a></div></header>\n'
            f'  <div class="grid">{"".join(cards)}</div>\n'
            '  <footer>photographs &copy; 2026 nafsadh &middot; <a href="/photos/" style="color:inherit">sadh.studio</a></footer>\n</div>\n')


def render_page(a, tmpl, base):
    d = os.path.join(ADIR, a["slug"]); img = {}; posts = []
    for p in a.get("posts") or []:
        fr = []
        for fid in p.get("frames") or []:
            f = os.path.join(d, "img", f"{fid}.jpg")
            if not os.path.isfile(f): print(f"  ! album {a['slug']}: no img/{fid}.jpg"); continue
            w, h = Image.open(f).size
            fr.append({"id": fid, "w": w, "h": h, "v": _hash(f)}); img[fid] = f"{fid}.jpg"
        if not fr: continue
        o = "portrait" if all(x["w"] <= x["h"] for x in fr) else "landscape" if all(x["w"] > x["h"] for x in fr) else "mixed"
        posts.append({"id": str(p.get("id")), "t": str(p.get("title") or ""), "day": "", "cap": "", "o": o, "f": fr})
    name, sub = str(a.get("name") or a["slug"]), str(a.get("sub") or "")
    page = tmpl
    for k, v in {"TITLE_TEXT": esc(f"{name} {sub}".strip()), "NAME": esc(name), "SUB": esc(sub), "WHEN": esc(a.get("when")),
                 "IMG_JSON": json.dumps(img), "IMG_BASE": json.dumps(f"{base}{a['slug']}/" if base else "img/"),
                 "DATA_JSON": json.dumps({"posts": posts, "extras": []}, ensure_ascii=False)}.items():
        page = page.replace("{{" + k + "}}", v)
    if a.get("hidden"): page = page.replace("<head>", '<head><meta name="robots" content="noindex">', 1)
    return page


def deploy(out, darkroom_tmpl, styles_css, theme_js):
    """Write /albums/<slug>/ for every album and the /albums/ index."""
    albums, base = load(), img_base()
    tmpl = open(os.path.join(HERE, "templates", "album.html"), encoding="utf-8").read()
    root = os.path.join(out, "albums"); shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
    for a in albums:
        src, dst = os.path.join(ADIR, a["slug"]), os.path.join(root, a["slug"])
        if a["hand"]:
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("album.yaml", ".DS_Store", *(["img"] if base else [])))
            continue
        os.makedirs(dst)
        open(os.path.join(dst, "index.html"), "w", encoding="utf-8").write(render_page(a, tmpl, base))
        if os.path.isdir(os.path.join(src, "covers")):
            shutil.copytree(os.path.join(src, "covers"), os.path.join(dst, "covers"))
        if not base and os.path.isdir(os.path.join(src, "img")):
            shutil.copytree(os.path.join(src, "img"), os.path.join(dst, "img"))
    listed = [a for a in albums if not a.get("hidden")]
    open(os.path.join(root, "index.html"), "w", encoding="utf-8").write(index_page(tmpl, listed))
    return albums
