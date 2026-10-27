#!/usr/bin/env python3
"""Serve _site/ on a port and rebuild on source change.

Watches home.yaml, feed.yaml, CNAME, the photos and _build/** (skipping _site/,
.cache/ and __pycache__/). On any change, runs build.py. Unknown paths get /404.html,
like GitHub Pages.

Usage: python3 _build/serve.py [port]   (default 8768)
"""
import functools, http.server, os, socket, socketserver, subprocess, sys, threading, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = REPO / "_build" / "build.py"
SITE = REPO / "_site"
SUFFIXES = {".yaml", ".yml", ".jpg", ".jpeg", ".py", ".html", ".css"}
SKIP_DIRS = {"_site", ".cache", "__pycache__", ".git", ".github"}


def collect_mtimes():
    out = {}
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if Path(name).suffix.lower() in SUFFIXES:
                p = Path(root) / name
                try: out[p] = p.stat().st_mtime
                except OSError: pass
    return out


def build():
    subprocess.run([sys.executable, str(BUILD)], cwd=REPO, check=False)


def pick_port(preferred, tries=20):
    for port in range(preferred, preferred + tries):
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try: s.bind(("", port)); return port
            except OSError: continue
    sys.exit(f"no free port in {preferred}-{preferred + tries - 1}; free one with:  lsof -ti :{preferred} | xargs kill")


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store"); super().end_headers()
    def log_message(self, *a): pass
    def send_error(self, code, *a, **k):
        page = SITE / "404.html"
        if code == 404 and page.exists():
            self.send_response(404); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(page.read_bytes()); return
        super().send_error(code, *a, **k)


def main():
    port = pick_port(int(sys.argv[1]) if len(sys.argv) > 1 else 8768)
    print("→ initial build…", flush=True); build()
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("", port), functools.partial(Handler, directory=str(SITE)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"→ http://localhost:{port}/photos/   (Ctrl-C to stop)", flush=True)
    last = collect_mtimes()
    try:
        while True:
            time.sleep(1)
            curr = collect_mtimes()
            changed = sorted({p for p in curr if last.get(p) != curr[p]} | {p for p in last if p not in curr})
            if changed:
                for p in changed[:5]: print(f"  · {p.relative_to(REPO)}", flush=True)
                if len(changed) > 5: print(f"  · (+{len(changed) - 5} more)", flush=True)
                build(); last = collect_mtimes()
    except KeyboardInterrupt:
        print("\n→ stopping…", flush=True)
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
