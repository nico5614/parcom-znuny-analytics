# WebView host must contain neither Qt bindings nor their runtime hooks/DLLs.
from pathlib import Path
root = Path(SPECPATH).parent
a = Analysis([str(root / "start_web.py")], pathex=[str(root)],
             datas=[(str(root / "frontend" / "dist"), "frontend/dist")],
             hiddenimports=[], hookspath=[],
             excludes=["PySide6", "shiboken6", "PyQt5", "PyQt6", "tkinter", "pytest",
                       "parcom_analytics.web.pdf_worker"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ParCom Znuny Analytics",
          debug=False, strip=False, upx=False, console=False,
          icon=str(root / "assets" / "app_icon.ico"),
          version=str(root / "build" / "version_info.txt"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ParCom_Analytics_Web")
