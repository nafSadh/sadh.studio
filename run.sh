#!/usr/bin/env bash
# sadh.studio — local commands
#   ./run.sh serve   serve this repo at http://localhost:8768/  (absolute /photos/... paths work)
#   ./run.sh build   rebuild from ~/photos/site/published.json into this repo
#   ./run.sh         build, then serve
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SITE="$HOME/photos/site"
PORT="${PORT:-8768}"
cmd="${1:-all}"
build() { (cd "$SITE" && python3 build.py --deploy "$HERE"); }
serve() {
  echo "→ http://localhost:$PORT/photos/   (ctrl-c to stop)"
  python3 - "$HERE" "$PORT" <<'PY'
import http.server, socketserver, os, sys, functools
root, port = sys.argv[1], int(sys.argv[2])
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def log_message(self, *a): pass
    def send_error(self, code, *a, **k):            # mimic GitHub Pages: unknown paths get /404.html
        if code == 404 and os.path.exists(os.path.join(root, '404.html')):
            self.send_response(404); self.send_header('Content-Type', 'text/html'); self.end_headers()
            self.wfile.write(open(os.path.join(root, '404.html'), 'rb').read()); return
        super().send_error(code, *a, **k)
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('', port), functools.partial(H, directory=root)) as s: s.serve_forever()
PY
}
case "$cmd" in
  build) build ;;
  serve) serve ;;
  all)   build; serve ;;
  *) echo "usage: $0 [build|serve]"; exit 1 ;;
esac
