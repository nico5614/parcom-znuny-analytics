from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from parcom_analytics.web.assets import allowed_navigation, serve


def test_asset_server_has_no_http_bridge_and_never_serves_parent_files(tmp_path):
    root = tmp_path / "assets"
    root.mkdir()
    (root / "index.html").write_text("local React entry", encoding="utf-8")
    (tmp_path / "private.txt").write_text("must remain outside server", encoding="utf-8")
    server, url = serve(root)
    try:
        assert server.server_address[0] == "127.0.0.1"
        assert urlopen(url).read() == b"local React entry"
        with pytest.raises(HTTPError) as failure:
            urlopen(Request(url.replace("index.html", "js_api/anything"), data=b"", method="POST"))
        assert failure.value.code == 501
        with pytest.raises(HTTPError):
            urlopen(url.replace("index.html", "../private.txt"))
        with pytest.raises(HTTPError):
            urlopen(url.replace("index.html", "private.txt"))
    finally:
        server.shutdown()
        server.server_close()


def test_native_navigation_is_pinned_to_the_bundled_document():
    entry = "http://127.0.0.1:4178/index.html"
    assert allowed_navigation(entry, entry)
    assert allowed_navigation(entry + "#overview", entry)
    for target in ("https://znuny.parcom.ch", "https://mosaic.cruip.com", "file:///C:/private.txt", "javascript:alert(1)", "http://127.0.0.1:4179/index.html", "http://127.0.0.1:4178/other.html"):
        assert not allowed_navigation(target, entry)
