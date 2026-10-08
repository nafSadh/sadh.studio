# sadh.studio

Sadh's creative output. Hosted on GitHub Pages at **[sadh.studio](https://sadh.studio)**.

- `/` → `/photos/` — *still movements*, the wall: frames with `"wall": true` in `published.json` (default true; set it false to move a frame to the feed only).
- `/photos-all/` — every published frame, newest first.
- `/photo/<id>/` — permanent URL for one frame (og:image for previews), lands on `/photo/#<id>`. `<id>` is the camera filename stem (`DSCF3636`, `P5098471-2`), same as on disk. `/photos#<id>` works too.
- `/photos/full/<id>.jpg` — the 3200px web image; `/photos/thumb/<id>.jpg` the 760px thumb.

Built from `~/photos/site` with `python3 build.py --deploy ~/src/sadh.studio`; `published.json` there is the source of truth
(curate in `pick.html`, merge with `merge_picks.py`). Do not hand-edit the HTML; rebuild it.
