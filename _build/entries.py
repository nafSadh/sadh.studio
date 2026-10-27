"""Read and write home.yaml / feed.yaml, keeping their layout.

home.yaml   contents: a list of photos, the wall in order
feed.yaml   contents: photos and stacks, newest first
              - photo: <ID>            a single photo
              - photos: <cover ID>     a stack of the same scene, one tile in the feed;
                stack: [<photo>, ...]  its photos, the cover first (a photo that is on the
                                       wall is listed here by ID only)
A photo: photo, origin, location, date, caption, ig, reddit: [{post, sub}].
In a stack, location / date / caption sit on the stack and hold for its photos.
"""
import json, re
from pathlib import Path
import yaml

PHOTO_KEYS = ("photo", "origin", "location", "date", "caption", "ig", "reddit")


def load(path):
    """-> (header comment text, contents list)"""
    text = Path(path).read_text(encoding="utf-8")
    head = "".join(ln + "\n" for ln in text.split("\n")[: next((i for i, ln in enumerate(text.split("\n")) if ln.startswith("contents:")), 0)])
    return head, (yaml.safe_load(text) or {}).get("contents") or []


def q(v):
    s = str(v)
    if s == "": return '""'
    return s if re.fullmatch(r"[^\"':#{}\[\],&*!|>%@`\\\n]+", s) and s == s.strip() and not re.fullmatch(r"[\d.:\- ]+", s) or re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d", s) else json.dumps(s, ensure_ascii=False)


def date_str(v):
    return v.strftime("%Y-%m-%d %H:%M") if hasattr(v, "strftime") else str(v)


def photo_lines(p, ind, skip=()):
    L = []
    for k in PHOTO_KEYS:
        if k in skip or p.get(k) in (None, "", []): continue
        v = p[k]
        if k == "reddit":
            L.append(f"{ind}reddit:")
            for r in v: L += [f"{ind}  - post: {q(r['post'])}", f"{ind}    sub: {q(r['sub'])}"]
        else:
            L.append(f"{ind}{k}: {q(date_str(v) if k == 'date' else v)}")
    for k, v in p.items():                       # keep anything hand-added that we don't know about
        if k not in PHOTO_KEYS and k not in ("photos", "stack") and k not in skip and v not in (None, ""):
            L.append(f"{ind}{k}: {q(v)}")
    L[0] = L[0].replace(ind, ind[:-2] + "- ", 1)
    return L


def dump(path, head, contents):
    L = [head.rstrip("\n"), "", "contents:"] if head.strip() else ["contents:"]
    for it in contents:
        if "photos" in it:
            L.append(f"  - photos: {q(it['photos'])}")
            for k in ("location", "date", "caption"):
                if it.get(k) not in (None, ""): L.append(f"    {k}: {q(date_str(it[k]) if k == 'date' else it[k])}")
            L.append("    stack:")
            for m in it.get("stack") or []: L += photo_lines(m, "        ")
        else:
            L += photo_lines(it, "    ")
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")
