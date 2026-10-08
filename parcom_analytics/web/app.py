"""Windows-only WebView2 host with an opt-in, credential-free packaging probe."""

import argparse
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

from .bridge import DesktopBridge
from .serialization import json_value


def asset_root():
    root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    return root / "frontend" / "dist"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-report", type=Path)
    parser.add_argument("--validation", action="store_true", help="Isolated synthetic data, never connects to Znuny")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("This desktop host requires Windows WebView2.")
    import webview

    entry = asset_root() / "index.html"
    if not entry.is_file():
        raise RuntimeError("Frontend fehlt. Zuerst pnpm --dir frontend build ausführen.")
    webview.settings["ALLOW_DOWNLOADS"] = False
    webview.settings["ALLOW_FILE_URLS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    bridge = DesktopBridge()
    if args.validation:
        from ..live_cache import LiveCache
        from .validation import ValidationClient, validation_batch
        root = Path(tempfile.mkdtemp(prefix="parcom-web-validation-"))
        cache = LiveCache(root)
        cache.update(validation_batch())
        bridge = DesktopBridge(client=ValidationClient(), root=root, cache=cache, fetch=validation_batch)
    window = webview.create_window("ParCom Analytics", str(entry), js_api=bridge,
                                   width=args.width, height=args.height, min_size=(900, 600),
                                   background_color="#08111B", text_select=True)
    bridge._publish = lambda event: window.run_js(
        "window.dispatchEvent(new CustomEvent('parcom:desktop', {detail:"
        + json.dumps(json_value(event), ensure_ascii=True, allow_nan=False) + "}));")
    window.events.closed += bridge._close

    def smoke():
        if args.smoke_report is None:
            return
        success = bridge._probe_confirmed.wait(40)
        report = {"ok": success, "python": platform.python_version(),
                  "frozen": bool(getattr(sys, "frozen", False)),
                  "renderer": webview.guilib.renderer,
                  "react_committed_python_event": success,
                  "local_assets": entry.is_file(),
                  "path": os.environ.get("PATH", "")}
        args.smoke_report.parent.mkdir(parents=True, exist_ok=True)
        args.smoke_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        window.destroy()

    # pywebview bridge calls and start callbacks run on worker threads.
    # No HTTP API is exposed: this server only serves the bundled static assets.
    webview.start(smoke, gui="edgechromium", debug=False, private_mode=True, http_server=True)
    return 0 if not args.smoke_report or bridge._probe_confirmed.is_set() else 1
