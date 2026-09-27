"""Zip the game and serve web/ on port 8000 at the host in argv[1] (default localhost)."""
import functools
import http.server
import sys
import zipfile
from pathlib import Path

WEB = Path(__file__).parent
GAME = WEB.parent / "ice_cream_truck"


def build_zip():
    with zipfile.ZipFile(WEB / "game.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for path in [*GAME.glob("*.py"), *(GAME / "assets").rglob("*")]:
            if path.is_file():
                zf.write(path, path.relative_to(GAME))


if __name__ == "__main__":
    build_zip()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=WEB)
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    http.server.ThreadingHTTPServer((host, 8000), handler).serve_forever()
