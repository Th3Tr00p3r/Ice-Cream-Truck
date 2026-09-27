"""Build web/game.zip and web/wheels/, then serve web/ on port 8000 at the host in argv[1] (default localhost)."""
import functools
import http.server
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

WEB = Path(__file__).parent
GAME = WEB.parent / "ice_cream_truck"
WHEELS = WEB / "wheels"
# Pure-Python wheels the page loads; must match the file names in index.html.
PACKAGES = {"arcade": "4.0.0.dev7", "pyglet": "3.0.dev8", "pytiled-parser": "2.2.9"}
# Parts of the arcade wheel the game never uses in the browser (macOS ffmpeg libs, examples and their assets).
ARCADE_UNUSED = ("arcade/lib/", "arcade/examples/", "arcade/resources/assets/")


def build_zip():
    with zipfile.ZipFile(WEB / "game.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for path in [*GAME.glob("*.py"), *(GAME / "assets").rglob("*")]:
            if path.is_file():
                zf.write(path, path.relative_to(GAME))


def download_wheel(name, version):
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json") as response:
        wheel = next(url for url in json.load(response)["urls"] if url["filename"].endswith(".whl"))
    with urllib.request.urlopen(wheel["url"]) as response:
        return wheel["filename"], response.read()


def trim_wheel(data, unused_prefixes):
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(
        out, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        for item in src.infolist():
            if item.filename.startswith(unused_prefixes):
                continue
            content = src.read(item)
            if item.filename.endswith(".dist-info/RECORD"):
                lines = content.decode().splitlines()
                content = "\n".join(
                    line for line in lines if not line.startswith(unused_prefixes)
                ).encode()
            dst.writestr(item, content)
    return out.getvalue()


def build_wheels():
    WHEELS.mkdir(exist_ok=True)
    for name, version in PACKAGES.items():
        if any(WHEELS.glob(f"{name.replace('-', '_')}-{version}-*.whl")):
            continue
        filename, data = download_wheel(name, version)
        if name == "arcade":
            data = trim_wheel(data, ARCADE_UNUSED)
        (WHEELS / filename).write_bytes(data)
        print(f"{filename}: {len(data) / 1e6:.1f} MB")


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")  # revalidate so edits reach the tablet
        super().end_headers()


if __name__ == "__main__":
    build_zip()
    build_wheels()
    handler = functools.partial(NoCacheHandler, directory=WEB)
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    http.server.ThreadingHTTPServer((host, 8000), handler).serve_forever()
