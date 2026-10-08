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
from .assets import allowed_navigation, serve


def asset_root():
    root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    return root / "frontend" / "dist"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-report", type=Path)
    parser.add_argument("--smoke-pdf", action="store_true", help="Explicitly test optional PDF subprocess")
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
    server, url = serve(entry.parent)
    window = webview.create_window("ParCom Analytics", url, js_api=bridge,
                                   width=args.width, height=args.height, min_size=(900, 600),
                                   background_color="#08111B", text_select=True)
    bridge._publish = lambda event: window.run_js(
        "window.dispatchEvent(new CustomEvent('parcom:desktop', {detail:"
        + json.dumps(json_value(event), ensure_ascii=True, allow_nan=False) + "}));")
    window.events.closed += bridge._close
    def secure_native():
        control = window.native.browser.webview
        def guard_navigation(sender, event):
            event.Cancel = not allowed_navigation(str(event.Uri), url)
        def disable_form_storage(sender, event):
            if event.IsSuccess:
                sender.CoreWebView2.Settings.IsPasswordAutosaveEnabled = False
                sender.CoreWebView2.Settings.IsGeneralAutofillEnabled = False
        control.NavigationStarting += guard_navigation
        control.CoreWebView2InitializationCompleted += disable_form_storage
    window.events.before_show += secure_native
    def choose_save(filename):
        result = window.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename, file_types=("PDF-Dateien (*.pdf)",))
        return result[0] if result else None
    bridge._choose_save = choose_save

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
        def qt_state():
            import ctypes
            get_module = ctypes.windll.kernel32.GetModuleHandleW
            get_module.argtypes = [ctypes.c_wchar_p]
            get_module.restype = ctypes.c_void_p
            return {"modules": [name for name in sys.modules if name.startswith(("PySide6", "shiboken6"))],
                    "dlls": [name for name in ("Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll") if get_module(name)]}
        report["qt_before_export"] = qt_state()
        args.smoke_report.parent.mkdir(parents=True, exist_ok=True)
        if success and args.validation:
            try:
                assert bridge.continueOffline()["ok"]
                assert bridge.getOverview()["ok"]
                assert all(bridge.getAnalysis(kpi)["ok"] for kpi in range(1, 8))
                assert bridge.getAgents()["ok"]
                report["synthetic_reports"] = True
                if args.smoke_pdf:
                    bridge._choose_save = lambda filename: str(args.smoke_report.with_name(filename))
                    exports = [bridge.exportPdf(target) for target in ("overview", "5")]
                    report["pdf_exports"] = all(item["ok"] and not item["data"]["cancelled"] for item in exports)
                    report["ok"] = report["ok"] and report["pdf_exports"]
            except Exception:
                report["ok"] = False
                report["synthetic_reports"] = False
        report["qt_after_export"] = qt_state()
        report["ok"] = report["ok"] and not any(report[key][kind] for key in ("qt_before_export", "qt_after_export") for kind in ("modules", "dlls"))
        args.smoke_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        window.destroy()

    # pywebview bridge calls and start callbacks run on worker threads.
    # No HTTP API is exposed: this server only serves the bundled static assets.
    try:
        webview.start(smoke, gui="edgechromium", debug=False, private_mode=True)
    finally:
        server.shutdown()
        server.server_close()
    if args.smoke_report:
        return 0 if json.loads(args.smoke_report.read_text(encoding="utf-8"))["ok"] else 1
    return 0
