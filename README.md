# sadh.studio

Sadh's creative output. Hosted on GitHub Pages at **[sadh.studio](https://sadh.studio)**, built by
GitHub Actions from this repo on every push (same model as sadh.ink).

## What's where

- `feed.yaml` -- the feed at `/photos/all/`: every photo, newest first, with stacks.
- `home.yaml` -- the wall at `/photos/`, the site's home, in order. Wall photos are in both
  files; `./run.sh check` flags any differences.
- `photos/` -- the photos, `<ID>.jpg` (the edited web export, long edge up to 3200px).
- `_build/` -- `build.py` (the generator), `serve.py` (local server + rebuild on change),
  `photos.py` (add / remove), `check.py` (sanity check).
- `_site/` -- the generated site (not committed).

A photo, in either file:

    - photo: PA174308                     # camera ID, no edit suffix; the file is photos/PA174308.jpg
      origin: ~/photos/26.10.17 Panther/edits/PA174308-2.jpg
      location: Panther Beach
      date: 2026-10-17 17:47
      caption:                            # optional, identifying names only
      ig: DeqgzNzlK5N                     # optional, Instagram post shortcode
      reddit:                             # optional
        - post: 1xc3tm3
          sub: r/EarthPorn

feed.yaml also has stacks, same-scene photos shown as one tile:

    - photos: PA174380                    # the cover
      location: Panther Beach             # location, date, caption hold for the whole stack
      date: 2026-10-17 17:51
      stack:                              # the cover first
        - photo: PA174380
          origin: ~/photos/26.10.17 Panther/edits/PA174380.jpg
        - photo: PA174400
          origin: ~/photos/26.10.17 Panther/edits/PA174400.jpg

## Pages

- `/photos/` -- *still movements*, the wall.
- `/photos/all/` -- every listed photo, newest first; same-scene variations stack (`under:`).
- `/photo/<id>/` -- permanent page for one photo; `<id>` is the camera ID (`DSCF3636`,
  `P5098471`); old links with an edit suffix (`P5098471-2`) still land on it. `/photo/<id>.jpg` is the full image, `/photo/<id>.thumb.jpg` the 760px thumb.

## Adding and removing

Edit the yaml directly: drop `<ID>.jpg` (the web export) into `photos/`, write its entry in
`feed.yaml`, and copy the entry into `home.yaml` to put it on the wall. `./run.sh check`
warns about slips (a wall photo that differs between the two files, missing or unlisted
files, stacks without their cover, dates that disagree with the file, ...); the build prints
the same warnings.

Or let the helper do the copying and the typing:

    ./run.sh add ~/photos/26.10.17\ Panther/edits/PA174126.jpg                    # into feed.yaml
    ./run.sh add ~/photos/26.10.17\ Panther/edits/PA174126.jpg --home             # ...and onto the wall
    ./run.sh add ~/photos/26.10.17\ Panther/edits/PA174126.jpg --stack PA174380   # into that stack
    ./run.sh rm PA174126                                                           # out of everything

`add` resizes the export to 3200px, names it by camera ID, and fills in origin, date and
location (from another photo of the same ~/photos album, or `--location`).

## Local

    ./run.sh          # build, serve at http://localhost:8768/photos/, rebuild on change
    ./run.sh build    # build once
    ./run.sh check    # sanity check

Needs Python 3 with `pyyaml` and `pillow`.
