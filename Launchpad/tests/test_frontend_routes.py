"""Page and asset routes for the React build: / serves frontend/dist when built, else the vanilla page; /classic is
always the vanilla page; /assets/<file> serves only plain file names from the build's assets folder."""
import re

from fastapi.testclient import TestClient

from app import server
from app.server import create_app
from app.settings import Settings

VANILLA_MARK = "const Bridge"          # only in prototype/launchpad-orbit.html


def _client(project):
    return TestClient(create_app(1234, "x", Settings(project=project, engine="fake")))


def _fake_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<!doctype html><title>react shell</title><div id="root"></div>'
                                     '<script type="module" src="./assets/index-abc123.js"></script>', encoding="utf-8")
    (dist / "assets" / "index-abc123.js").write_text("console.log('hi')", encoding="utf-8")
    (dist / "assets" / "index-abc123.css").write_text("body{}", encoding="utf-8")
    (dist / "assets" / "notes.exe").write_text("no", encoding="utf-8")
    (tmp_path / "secret.js").write_text("outside", encoding="utf-8")
    return dist


def test_root_serves_react_build_when_present(project, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "FRONTEND_DIST", _fake_dist(tmp_path))
    client = _client(project)
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "react shell" in r.text and VANILLA_MARK not in r.text
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "connect-src 'self' ws://127.0.0.1:1234" in csp
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"


def test_root_falls_back_to_vanilla_without_build(project, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "FRONTEND_DIST", tmp_path / "no-such-dist")
    r = _client(project).get("/")
    assert r.status_code == 200 and VANILLA_MARK in r.text
    assert "default-src 'self'" in r.headers["content-security-policy"]


def test_classic_always_serves_vanilla_with_same_headers(project, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "FRONTEND_DIST", _fake_dist(tmp_path))
    client = _client(project)
    root, classic = client.get("/"), client.get("/classic")
    assert classic.status_code == 200 and VANILLA_MARK in classic.text
    for h in ("content-security-policy", "x-content-type-options", "referrer-policy", "cache-control"):
        assert classic.headers[h] == root.headers[h]


def test_assets_served_from_build_with_fixed_types(project, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "FRONTEND_DIST", _fake_dist(tmp_path))
    client = _client(project)
    js = client.get("/assets/index-abc123.js")
    assert js.status_code == 200 and js.headers["content-type"].startswith("application/javascript")
    assert js.headers["x-content-type-options"] == "nosniff" and "immutable" in js.headers["cache-control"]
    css = client.get("/assets/index-abc123.css")
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")


def test_assets_refuse_odd_names_types_and_escapes(project, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "FRONTEND_DIST", _fake_dist(tmp_path))
    client = _client(project)
    for url in ("/assets/notes.exe", "/assets/missing-1.js", "/assets/..%2Fsecret.js", "/assets/%2E%2E%2Fsecret.js",
                "/assets/.hidden.js", "/assets/..\\secret.js"):
        assert client.get(url).status_code == 404, url
    assert client.get("/assets/../secret.js").status_code == 404


def test_assets_404_without_build(project, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "FRONTEND_DIST", tmp_path / "no-such-dist")
    assert _client(project).get("/assets/index-abc123.js").status_code == 404


def test_committed_build_assets_resolve(project):
    """When the repo's own build exists, every asset its index.html references is served (same origin, relative)."""
    index = server.FRONTEND_DIST / "index.html"
    if not index.is_file():
        return
    html = index.read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="\./(assets/[^"]+)"', html)
    assert refs, "the build should reference its assets with relative ./assets/ paths"
    assert "http://" not in html and "https://" not in html
    client = _client(project)
    for ref in refs:
        r = client.get("/" + ref)
        assert r.status_code == 200, ref
