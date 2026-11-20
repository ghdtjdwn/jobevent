import json
import struct
from importlib.resources import files


def test_installation_assets_and_private_cache_policy():
    assets = files("jobevent.static")
    manifest = json.loads(assets.joinpath("manifest.webmanifest").read_text())
    assert manifest["start_url"] == "/app" and manifest["display"] == "standalone"
    for icon in manifest["icons"]:
        data = assets.joinpath(icon["src"][1:]).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        w, h = struct.unpack(">II", data[16:24])
        assert icon["sizes"] == f"{w}x{h}"
    assert "caches." not in assets.joinpath("sw.js").read_text()
