"""Independent Qt-only bundle, placed below the WebView distribution."""
from pathlib import Path
root = Path(SPECPATH).parent
a = Analysis([str(root / "start_pdf_worker.py")], pathex=[str(root)],
             # Pickle reconstructs LiveRecord from this module dynamically.
             datas=[], hiddenimports=["parcom_analytics.live_cache"], hookspath=[],
             excludes=["webview", "pythonnet", "clr", "PyQt5", "PyQt6", "tkinter", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ParCom_PDF_Worker",
          # The launcher uses CREATE_NO_WINDOW and captures failures; no crash dialog.
          debug=False, strip=False, upx=False, console=True,
          icon=str(root / "assets" / "app_icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="pdf_worker")
