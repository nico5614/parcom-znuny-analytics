"""Regression: the WebView host starts and exports without loading Qt."""
from pathlib import Path
import subprocess
import sys
import textwrap

from parcom_analytics.web import pdf_export


def test_normal_webview_startup_when_every_qt_import_is_forbidden():
    script = textwrap.dedent('''
        import builtins, sys, tempfile
        from pathlib import Path
        from unittest.mock import MagicMock
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.startswith(("PySide", "PyQt", "shiboken")):
                raise AssertionError("Qt requested by WebView host: " + name)
            return original(name, *args, **kwargs)
        builtins.__import__ = guarded
        webview = MagicMock()
        webview.settings = {}
        webview.guilib.renderer = "edgechromium"
        sys.modules["webview"] = webview
        from parcom_analytics.web import app
        sys.argv = ["start_web.py"]
        with tempfile.TemporaryDirectory() as directory:
            entry = Path(directory)
            (entry / "index.html").write_text("<html></html>")
            app.asset_root = lambda: entry
            assert app.main() == 0
        assert webview.start.call_args.kwargs["gui"] == "edgechromium"
        assert not any(name.startswith(("PySide", "shiboken")) for name in sys.modules)
        assert "parcom_analytics.web.pdf_worker" not in sys.modules
        assert "parcom_analytics.web.pdf_export" not in sys.modules
    ''')
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True, timeout=30)


def test_frozen_export_launches_separate_bundle_and_leaves_host_environment(monkeypatch, tmp_path):
    import os
    calls = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "ParCom_Analytics_Web.exe"))
    original_environment = dict(os.environ)
    def run(command, **kwargs):
        import pickle
        assert Path(command[1]).is_file()
        with Path(command[1]).open("rb") as stream:
            assert pickle.load(stream) == (tmp_path / "output.pdf", {"trusted": True})
        calls.append((command, kwargs))
    monkeypatch.setattr(pdf_export.subprocess, "run", run)
    pdf_export.run_export(tmp_path / "output.pdf", {"trusted": True})
    command, kwargs = calls[0]
    assert command[0] == str(tmp_path / "pdf_worker" / "ParCom_PDF_Worker.exe")
    assert not Path(command[1]).exists()
    assert kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert kwargs["env"]["QT_QPA_PLATFORM"] == "offscreen"
    assert dict(os.environ) == original_environment


def test_webview_bundle_excludes_qt_and_worker_has_its_own_analysis():
    root = Path(__file__).resolve().parents[1]
    analyses = []
    def analysis(scripts, **kwargs):
        from types import SimpleNamespace
        analyses.append((scripts, kwargs))
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])
    scope = {"SPECPATH": str(root / "packaging"), "Analysis": analysis,
             "PYZ": lambda *a, **k: None, "EXE": lambda *a, **k: None,
             "COLLECT": lambda *a, **k: None}
    for spec in ("parcom_web.spec", "parcom_pdf_worker.spec"):
        exec((root / "packaging" / spec).read_text(), scope)
    assert "PySide6" in analyses[0][1]["excludes"]
    assert "shiboken6" in analyses[0][1]["excludes"]
    assert "parcom_analytics.web.pdf_worker" in analyses[0][1]["excludes"]
    assert Path(analyses[1][0][0]).name == "start_pdf_worker.py"
    assert "webview" in analyses[1][1]["excludes"]
    from parcom_analytics.live_cache import LiveRecord
    assert LiveRecord.__module__ in analyses[1][1]["hiddenimports"]


def test_windows_build_sanitizes_path_for_both_pyinstaller_bundles():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "build_web.ps1").read_text()
    sanitized = script.index("$env:PATH = (Join-Path $env:WINDIR 'System32')")
    assert sanitized < script.index("packaging/parcom_web.spec") < script.index("packaging/parcom_pdf_worker.spec")
    assert "finally { $env:PATH = $originalBuildPath }" in script
