# PyInstaller onedir build; version resources are generated from the app constants.
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "start.py")], pathex=[str(root)],
    datas=[(str(root / "assets"), "assets")],
    hiddenimports=["openpyxl", "tzdata"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "pytest"],
    hookspath=[], hooksconfig={"matplotlib": {"backends": ["QtAgg"]}},
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ParCom_Znuny_Analytics",
          debug=False, strip=False, upx=False, console=False,
          icon=str(root / "assets" / "app_icon.ico"),
          version=str(root / "build" / "version_info.txt"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ParCom_Znuny_Analytics")
