"""Generate Windows resources from the shared version and existing logo."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from parcom_analytics import APP_NAME, DISPLAY_VERSION, PUBLISHER, VERSION, WINDOWS_VERSION


def main():
    output = ROOT / "build"
    output.mkdir(exist_ok=True)
    parts = tuple(int(value) for value in WINDOWS_VERSION.split("."))
    strings = {"CompanyName": PUBLISHER, "FileDescription": APP_NAME, "FileVersion": WINDOWS_VERSION,
               "InternalName": "ParCom_Znuny_Analytics", "LegalCopyright": f"© {PUBLISHER}",
               "OriginalFilename": "ParCom_Znuny_Analytics.exe", "ProductName": APP_NAME,
               "ProductVersion": VERSION}
    info = VSVersionInfo(ffi=FixedFileInfo(filevers=parts, prodvers=parts, mask=0x3f, flags=0,
                                         OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
                         kids=[StringFileInfo([StringTable("040704B0", [StringStruct(k, v) for k, v in strings.items()])]),
                               VarFileInfo([VarStruct("Translation", [0x407, 1200])])])
    (output / "version_info.txt").write_text(str(info), encoding="utf-8")
    (output / "version.iss").write_text(f'#define AppVersion "{VERSION}"\n#define DisplayVersion "{DISPLAY_VERSION}"\n'
                                       f'#define AppPublisher "{PUBLISHER}"\n#define AppName "{APP_NAME}"\n', encoding="utf-8")
    icon = ROOT / "assets" / "app_icon.ico"
    if not icon.exists():
        # Format conversion only; the supplied logo is not redesigned or retouched.
        with Image.open(ROOT / "assets" / "app_logo.png") as original:
            original.save(icon, format="ICO", sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
    app = QApplication.instance() or QApplication([])
    image = QImage(328, 628, QImage.Format.Format_RGB32)
    image.fill(QColor("#14181f"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    logo = QImage(str(ROOT / "assets" / "app_logo.png"))
    painter.drawImage(54, 76, logo.scaled(220, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    painter.setPen(QColor("#e7ebef"))
    painter.setFont(QFont("Segoe UI", 17, QFont.Weight.DemiBold))
    painter.drawText(image.rect().adjusted(28, 325, -28, -60), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                     "ParCom\nZnuny Analytics")
    painter.end()
    image.save(str(output / "wizard.bmp"))


if __name__ == "__main__":
    main()
