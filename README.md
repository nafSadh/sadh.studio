# sadh.studio

Sadh's creative output. Hosted on GitHub Pages at **[sadh.studio](https://sadh.studio)**.

- `/` → `/photos/` — *still movements*, photos by sadh (Darkroom treatment).
- `/photo#<id>` — permanent URL for one frame; `<id>` is the camera filename stem (e.g. `DSCF3636`, `P5098471-2`), same as on disk. `/photos#<id>` works too.
- `/photos/full/<id>.jpg` — the web-sized image itself. Built from `~/photos/site` with
  `python3 build.py --deploy ~/src/sadh.studio`; `published.json` there is the source of truth.
- `photos/thumb/` 760px thumbnails · `photos/full/` 2200px web fulls.

Do not hand-edit `index.html`; rebuild it.
