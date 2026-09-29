"""Application entry point."""

import logging
from logging.handlers import RotatingFileHandler
import sys

from PySide6.QtCore import QLocale, QLockFile
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME, VERSION
from .storage import LocalStore, default_storage_path
from .ui import APP_LOGO, MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("ParCom")
    app.setWindowIcon(QIcon(str(APP_LOGO)))
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    QLocale.setDefault(QLocale(QLocale.Language.German, QLocale.Country.Switzerland))
    try:
        root = default_storage_path()
        (root / "logs").mkdir(parents=True, exist_ok=True)
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                            handlers=[RotatingFileHandler(root / "logs" / "app.log", maxBytes=2_000_000,
                                                          backupCount=2, encoding="utf-8")])
        lock = QLockFile(str(root / "app.lock"))
        if not lock.tryLock(100):
            QMessageBox.information(None, APP_NAME, "Die Anwendung ist bereits geöffnet oder der Datenspeicher ist gesperrt.")
            return 0
        logging.info("Starting %s %s", APP_NAME, VERSION)
        window = MainWindow(LocalStore(root))
    except Exception as error:
        logging.error("Startup failed: %s", type(error).__name__)
        QMessageBox.critical(None, "Start fehlgeschlagen", "Der lokale Anwendungsspeicher konnte nicht geöffnet werden. Bitte prüfen Sie Ihre Schreibrechte.")
        return 1
    window.show()
    result = app.exec()
    lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
