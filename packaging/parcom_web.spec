# Phase 0 onedir build. No installer release is produced here.
from pathlib import Path
root = Path(SPECPATH).parent
a = Analysis([str(root / "start_web.py")], pathex=[str(root)],
             datas=[(str(root / "frontend" / "dist"), "frontend/dist")],
             hiddenimports=[], hookspath=[],
             excludes=["PySide6", "PyQt5", "PyQt6", "tkinter", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ParCom_Analytics_Web",
          debug=False, strip=False, upx=False, console=False,
          icon=str(root / "assets" / "app_icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ParCom_Analytics_Web")
