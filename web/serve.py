"""Zip the game into web/game.zip and serve web/ on http://localhost:8000."""
import functools
import http.server
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
    http.server.ThreadingHTTPServer(("localhost", 8000), handler).serve_forever()
