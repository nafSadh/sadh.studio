#!/usr/bin/env bash
# sadh.studio
#   ./run.sh [port]          build, serve _site/ at http://localhost:8768/photos/, rebuild on change
#   ./run.sh build           build _site/ once
#   ./run.sh add <jpg>...    add edited exports (see _build/photos.py); --home, --stack <cover>
#   ./run.sh rm <id>...      remove photos
#   ./run.sh check           warn about mismatches between home.yaml, feed.yaml and photos/
set -euo pipefail
cd "$(dirname "$0")"
case "${1:-}" in
  build) exec python3 _build/build.py ;;
  add|rm) exec python3 _build/photos.py "$@" ;;
  check) exec python3 _build/check.py ;;
  *) exec python3 _build/serve.py "${1:-8768}" ;;
esac
