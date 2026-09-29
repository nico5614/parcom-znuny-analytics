import time
import re
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QSize, Qt
from PySide6.QtPdf import QPdfDocument
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from parcom_analytics.storage import LocalStore
from parcom_analytics.ui import MainWindow
from conftest import filename


def wait_for_import(qapp, window):
    deadline = time.monotonic() + 20
    while window.worker is not None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert window.worker is None, "Import did not finish"


def test_complete_desktop_workflow(qapp, tmp_path, tickets, monkeypatch):
    store = LocalStore(tmp_path / "storage")
    window = MainWindow(store)
    window.show()
    qapp.processEvents()
    assert window.size() == QSize(1280, 800)
    assert window.kpi_combo.currentData() is None
    assert window.empty_title.text() == "Keine Dateien hochgeladen"
    assert not window.pdf_button.isEnabled()
    for index, button in enumerate(window.nav_buttons):
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert window.stack.currentIndex() == index
        assert button.isChecked()
        assert window.size() == QSize(1280, 800)
    paths = []
    for kpi in range(1, 8):
        source = tmp_path / filename(kpi)
        tickets.to_excel(source, index=False)
        paths.append(str(source))
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: (paths, ""))
    window.navigate(1)
    QTest.mouseClick(window.upload_button, Qt.MouseButton.LeftButton)
    wait_for_import(qapp, window)
    assert len(store.records) == 7
    assert all(row[3] == "Importiert" for row in window.import_rows)
    assert window.empty_title.text() == "Keine KPI ausgewählt"
    assert window.kpi_combo.currentData() is None
    window.navigate(2)
    for kpi in range(1, 8):
        window.kpi_combo.setCurrentIndex(kpi)
        qapp.processEvents()
        assert window.analysis is not None
        assert window.analysis.kpi == kpi
        assert window.pdf_button.isEnabled()
        assert window.month_combo.isVisible() == (kpi in {1, 2, 5, 6})
        assert len(window.figure.axes) == 1
        assert window.detail_table.model().rowCount() == (3 if kpi == 4 else 6)
        assert "August 2026" in window.current_period if kpi in {1, 2, 5, 6} else "29.09.2026 – 10:52 Uhr" in window.current_period
    window.resize(1050, 650)
    qapp.processEvents()
    assert window.size() == QSize(1050, 650)
    assert window.canvas.height() >= 190
    assert window.canvas.geometry().bottom() < window.canvas.parentWidget().height()
    pdf = tmp_path / "dashboard.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(pdf), ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    window.navigate(3)
    QTest.mouseClick(window.pdf_button, Qt.MouseButton.LeftButton)
    assert pdf.read_bytes().startswith(b"%PDF")
    document = QPdfDocument()
    assert document.load(str(pdf)) == QPdfDocument.Error.None_
    text = " ".join(document.getAllText(page).text() for page in range(document.pageCount()))
    for expected in ["ParCom Znuny Analytics", "KPI 7", "DEMO-006", "Erstellt am", "29.09.2026"]:
        assert expected in text
    assert not document.render(0, QSize(1200, 850)).isNull()
    document.close()
    window.close()
    for path in paths:
        Path(path).unlink()
    restarted = MainWindow(LocalStore(store.root))
    restarted.kpi_combo.setCurrentIndex(1)
    assert restarted.analysis.metrics["Anzahl neue Tickets"] == 6
    restarted.close()


def test_missing_kpi_month_columns_and_local_file(qapp, tmp_path, tickets):
    store = LocalStore(tmp_path / "storage")
    source = tmp_path / filename(1)
    tickets.to_excel(source, index=False)
    store.import_file(source)
    window = MainWindow(store)
    window.kpi_combo.setCurrentIndex(2)
    assert window.empty_title.text() == "Keine Datei für diese KPI vorhanden."
    window.kpi_combo.setCurrentIndex(1)
    window.month_combo.addItem("Januar 2020", "2020-01")
    window.month_combo.setCurrentIndex(1)
    assert window.empty_title.text() == "Für den ausgewählten Monat ist keine Datei vorhanden."
    assert not window.pdf_button.isEnabled()
    window.month_combo.setCurrentIndex(0)
    local = store.root / store.records[0].stored_path
    tickets.drop(columns="Ticket#").to_excel(local, index=False)
    window.refresh_dashboard()
    assert "nicht alle benötigten Spalten" in window.empty_body.text()
    assert not window.pdf_button.isEnabled()
    local.unlink()
    window.refresh_dashboard()
    assert window.analysis is None
    assert "erneut" in window.empty_body.text()
    window.close()


def test_pdf_contains_all_rows_and_repeats_table_headers(qapp, tmp_path, tickets):
    from parcom_analytics.analytics import analyze
    from parcom_analytics.pdf_export import export_pdf
    store = LocalStore(tmp_path / "storage")
    window = MainWindow(store)
    data = pd.concat([tickets] * 35, ignore_index=True)
    data["Ticket#"] = [f"SYNTHETIC-{number:04}" for number in range(len(data))]
    analysis = analyze(7, data)
    window._render_analysis(analysis, "Datenstand: 29.09.2026 – 10:52 Uhr")
    pdf = tmp_path / "multipage.pdf"
    export_pdf(pdf, analysis, window.current_period, window.figure)
    document = QPdfDocument()
    assert document.load(str(pdf)) == QPdfDocument.Error.None_
    assert document.pageCount() > 2
    pages = [document.getAllText(page).text() for page in range(document.pageCount())]
    # QtPdf can return individual glyphs separated by whitespace at page boundaries.
    text = re.sub(r"\s+", "", " ".join(pages))
    for number in range(len(data)):
        assert f"SYNTHETIC-{number:04}" in text
    assert all("Ticket#" in re.sub(r"\s+", "", page) for page in pages[1:])
    assert all("Seite" in page for page in pages)
    document.close()
    window.close()
