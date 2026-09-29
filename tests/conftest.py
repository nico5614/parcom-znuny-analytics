"""Synthetic data only; real Znuny exports must never enter the test suite."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase


@pytest.fixture
def tickets():
    return pd.DataFrame({
        "Ticket#": [f"DEMO-{number:03}" for number in range(1, 7)],
        "Titel": ["Synthetisches Testticket"] * 6,
        "Erstellt": ["2026-08-01", "2026-08-01", "2026-08-02", "2026-08-03", "2026-08-03", "2026-08-31"],
        "Schließzeit": ["2026-08-02", "2026-08-02", "2026-08-03", "2026-08-04", "2026-08-04", "2026-08-31"],
        "Status": ["open", "pending reminder", "open", "pending auto", "open", "open"],
        "Priorität": ["3 normal"] * 6,
        "Alter": ["31 m", "2 h 45 m", "3 d 18 h", "22 d 1 h", "152 d 2 h", "446 d 18 h"],
        "FirstResponseTimeEscalation": [0, 1, "1", 0, 0, 1],
        "FirstResponseTimeDestinationDate": ["2026-09-30 12:00:00"] * 6,
        "Erstantwortzeit in Minuten": [0, 10, 20, 30, 40, 80],
        "Lösungszeit in Minuten": [0, 60, 120, 240, 480, 900],
    })


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    # The Windows offscreen Qt plugin does not discover system fonts itself.
    if os.name == "nt":
        fonts = Path(os.environ["WINDIR"]) / "Fonts"
        for name in ["segoeui.ttf", "segoeuib.ttf", "segoeuil.ttf", "seguisb.ttf"]:
            QFontDatabase.addApplicationFont(str(fonts / name))
    return app


def filename(kpi=7, date="2026-09-29", time="10-52", zone="Europe_Zurich"):
    return f"KPI_{kpi}___PBX__Test_Created_{date}_{time}_TimeZone_{zone}.xlsx"
