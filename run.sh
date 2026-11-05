#!/usr/bin/env bash
# sadh.studio
#   ./run.sh [port]          build, serve _site/ at http://localhost:8768/photos/, rebuild on change
#   ./run.sh build           build _site/ once
#   ./run.sh add <jpg>...    add edited exports (see _build/photos.py); --home, --stack <cover>
#   ./run.sh rm <id>...      remove photos
#   ./run.sh check           warn about mismatches between home.yaml, feed.yaml and photos/
#   ./run.sh albums [shoot]  port ~/photos/posts/<shoot> into albums/<slug>/, then fold in the feed's frames (albums_feed.py)
#   ./run.sh sync            upload album images to Cloudflare R2 (see _build/albums_sync.sh)
set -euo pipefail
cd "$(dirname "$0")"
case "${1:-}" in
  build) exec python3 _build/build.py ;;
  add|rm) exec python3 _build/photos.py "$@" ;;
  check) exec python3 _build/check.py ;;
  albums) shift; python3 _build/albums_port.py ~/photos "$@" && exec python3 _build/albums_feed.py ;;
  sync) exec _build/albums_sync.sh ;;
  *) exec python3 _build/serve.py "${1:-8768}" ;;
esac
