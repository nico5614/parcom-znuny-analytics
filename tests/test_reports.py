import re

import pandas as pd
import pytest
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtPdf import QPdfDocument
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from conftest import filename
from parcom_analytics.analytics import DataError, analyze, format_duration, metric_items
from parcom_analytics.charts import RED, ROW_COLORS, draw_chart, draw_history
from parcom_analytics.pdf_export import export_management_pdf, export_pdf
from parcom_analytics.reports import (available_records, comparison_rows, default_report_filename,
                                      load_management_report, load_report)
from parcom_analytics.storage import LocalStore, period_label
from parcom_analytics.ui import MainWindow
from parcom_analytics.theme import DARK_ROW_COLORS


@pytest.fixture
def report_store(tmp_path, tickets):
    store = LocalStore(tmp_path / "storage")
    for month in [9, 10]:
        frame = tickets.copy()
        frame["Titel"] = "PRIVATE-SYNTHETIC-TITLE"
        frame["Erstellt"] = [f"2026-{month-1:02}-{day:02}" for day in [1, 1, 2, 3, 3, 28]]
        frame["Schließzeit"] = [f"2026-{month-1:02}-{day:02}" for day in [2, 2, 3, 4, 4, 28]]
        frame["Erstantwortzeit in Minuten"] *= month-8
        frame["Lösungszeit in Minuten"] *= month-8
        for kpi in range(1, 8):
            source = tmp_path / filename(kpi, f"2026-{month:02}-29")
            frame.to_excel(source, index=False)
            store.import_file(source)
            source.unlink()
    return store


def pdf_text(path):
    document = QPdfDocument()
    assert document.load(str(path)) == QPdfDocument.Error.None_
    text = " ".join(document.getAllText(index).text() for index in range(document.pageCount()))
    document.close()
    return re.sub(r"\s+", "", text)


def test_latest_corrected_snapshot_remains_selectable(tmp_path, tickets):
    store = LocalStore(tmp_path / "store")
    source = tmp_path / filename(3)
    tickets.to_excel(source, index=False)
    store.import_file(source)
    tickets.iloc[:2].to_excel(source, index=False)
    store.import_file(source)
    latest = store.latest(3)
    assert latest == available_records(store, 3)[0]
    assert load_report(store, latest).analysis.metrics["Aktuell offene Tickets"] == 2


@pytest.mark.parametrize("value,expected", [(0, "0 min"), (45, "45 min"), (60, "1 h"), (83, "1 h 23 min"),
                                           (383, "6 h 23 min"), (1440, "1 d"), (1823, "1 d 6 h 23 min"),
                                           (5874, "4 d 1 h 54 min"), (83.5, "1 h 23,5 min"),
                                           (None, "–"), (-1, "–"), (float("inf"), "–")])
def test_shared_duration_format(value, expected):
    assert format_duration(value) == expected


@pytest.mark.parametrize("kpi", [3, 7])
def test_exact_age_classes_and_highlights(tickets, kpi):
    tickets["Alter"] = ["7 d", "7 d 1 m", "14 d", "14 d 1 m", "30 d", "30 d 1 m"]
    analysis = analyze(kpi, tickets)
    assert analysis.chart.to_dict() == {"0–7 Tage": 1, "8–14 Tage": 2, "15–30 Tage": 2, ">30 Tage": 1}
    assert analysis.metrics["Älter als 30 Tage"] == 1
    assert analysis.row_highlights == ["critical", "attention", "attention", "", "", ""]
    assert analysis.maximum_rows == {0}


@pytest.mark.parametrize("kpi,column", [(5, "Erstantwortzeit in Minuten"), (6, "Lösungszeit in Minuten")])
def test_percentile_maximum_and_ties(tickets, kpi, column):
    tickets[column] = [0, 10, 20, 30, 40, 80]
    analysis = analyze(kpi, tickets)
    assert analysis.references["p75"] == 37.5
    assert analysis.references["maximum"] == 80
    assert analysis.row_highlights == ["critical", "attention", "", "", "", ""]
    assert analysis.maximum_rows == {0}
    tickets[column] = [0, 10, 20, 80, 80, 80]
    analysis = analyze(kpi, tickets)
    assert analysis.maximum_rows == {0, 1, 2}
    assert analysis.row_highlights[:3] == ["critical"] * 3
    tickets[column] = [0] * 6
    analysis = analyze(kpi, tickets)
    assert analysis.row_highlights == [""] * 6
    assert analysis.references["median"] == 0


@pytest.mark.parametrize("kpi", [1, 2])
def test_daily_mean_includes_calendar_zero_days(tickets, kpi):
    analysis = analyze(kpi, tickets)
    assert analysis.references["daily_mean"] == pytest.approx(6 / 31)
    assert analysis.references["daily_max"] == 2
    figure = Figure()
    draw_chart(figure, analysis)
    axis = figure.axes[0]
    assert axis.lines[0].get_ydata()[0] == pytest.approx(6 / 31)
    assert any("Höchstwert: 2" in text.get_text() for text in axis.texts)
    assert all(patch.get_facecolor()[:3] != (0.749, 0.286, 0.263) for patch in axis.patches)


def test_donut_and_histogram_references(tickets):
    analysis = analyze(4, tickets)
    assert analysis.references["escalation_rate"] == 50
    assert analysis.row_highlights == ["critical"] * 3
    figure = Figure()
    draw_chart(figure, analysis)
    assert len(figure.axes[0].patches) == 2
    assert all(patch.width == 0.29 for patch in figure.axes[0].patches)
    assert any(text.get_text() == "50,0 %" for text in figure.axes[0].texts)
    for kpi in [5, 6]:
        analysis = analyze(kpi, tickets)
        draw_chart(figure, analysis)
        assert [line.get_xdata()[0] for line in figure.axes[0].lines] == [analysis.references["median"], analysis.references["mean"]]


@pytest.mark.parametrize("kpi", range(1, 8))
def test_available_periods_and_as_of_history(report_store, kpi):
    records = available_records(report_store, kpi)
    assert len(records) == 2
    assert records[0].export_timestamp > records[1].export_timestamp
    older = load_report(report_store, records[1])
    current = load_report(report_store, records[0])
    assert len(older.history) == 1
    assert len(current.history) == 2
    assert "Keine vorherigen" in older.history_note
    assert "Kein Vergleich verfügbar" in comparison_rows(older)["Veränderung"].iloc[0]
    if kpi == 5:
        assert comparison_rows(current).iloc[0].tolist() == ["Median", "25 min", "50 min", "+25 min"]
    expected = "2026-08" if kpi in {1, 2, 5, 6} else "2026-09-29_10-52"
    assert expected in default_report_filename(older)


def test_management_requires_all_kpis_and_valid_values(report_store):
    report = load_management_report(report_store)
    assert len(report.kpis) == 7
    assert report.metrics["Abschlussverhältnis (geschlossen / neu)"] == "100,0 %"
    assert report.metrics["Ticketdifferenz (geschlossen − neu)"] == "0"
    assert report.metrics["Offene Tickets >30 Tage"] == "2"
    assert report.metrics["Median Reaktionszeit"] == "50 min"
    assert report.performance.current is not None
    report_store.records = [record for record in report_store.records if record.kpi_number != 7]
    with pytest.raises(DataError, match="Fehlende KPIs: 7"):
        load_management_report(report_store)


def test_management_does_not_mix_months_for_context(report_store):
    report_store.records = [record for record in report_store.records if not (record.kpi_number == 2 and record.reporting_month == "2026-09")]
    report = load_management_report(report_store)
    assert "Nicht vergleichbare" in report.metrics["Abschlussverhältnis (geschlossen / neu)"]
    assert "Nicht vergleichbare" in report.metrics["Ticketdifferenz (geschlossen − neu)"]


@pytest.mark.parametrize("kpi,column", [(3, "Alter"), (5, "Erstantwortzeit in Minuten")])
def test_management_blocks_invalid_current_data(report_store, kpi, column):
    record = available_records(report_store, kpi)[0]
    path = report_store.root / record.stored_path
    frame = pd.read_excel(path).astype(object)
    frame.loc[0, column] = "invalid"
    frame.to_excel(path, index=False)
    with pytest.raises(DataError, match=f"KPI {kpi}"):
        load_management_report(report_store)


def test_unreadable_history_is_not_silently_skipped(report_store):
    latest, previous = available_records(report_store, 5)
    (report_store.root / previous.stored_path).unlink()
    report = load_report(report_store, latest)
    assert report.history[0].analysis is None
    assert "Lücken" in report.history_note
    assert comparison_rows(report)["Veränderung"].iloc[0] == "Kein Vergleich verfügbar"
    figure = Figure()
    draw_history(figure, report)
    assert pd.isna(figure.axes[0].lines[0].get_ydata()[0])


def test_direct_download_selection_restart_and_clipboard(qapp, report_store, tmp_path, monkeypatch):
    window = MainWindow(report_store)
    window.show()
    window.navigate(4)
    assert window.analysis is None
    window.download_combo.setCurrentIndex(5)
    assert window.download_report.record.reporting_month == "2026-09"
    window.download_period_combo.setCurrentIndex(1)
    expected = window.download_report
    assert expected.record.reporting_month == "2026-08"
    assert window.pdf_button.isEnabled()
    path = tmp_path / "direct.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    QTest.mouseClick(window.pdf_button, Qt.MouseButton.LeftButton)
    text = pdf_text(path)
    assert "August2026" in text and "25min" in text and "HistorischeEntwicklung" in text
    window.navigate(2)
    window.kpi_combo.setCurrentIndex(3)
    window.snapshot_combo.setCurrentIndex(1)
    qapp.processEvents()
    assert window.current_report.record.export_timestamp.startswith("2026-09")
    model = window.detail_table.model()
    assert model.data(model.index(0, 0), Qt.ItemDataRole.BackgroundRole).name() == DARK_ROW_COLORS["critical"]
    QTest.mouseClick(window.detail_table.viewport(), Qt.MouseButton.LeftButton,
                     pos=window.detail_table.visualRect(model.index(0, 0)).center())
    assert QApplication.clipboard().text() == "DEMO-006"
    assert window.copy_note.text() == "Ticketnummer kopiert: DEMO-006"
    window.navigate(4)
    assert window.download_report.record == expected.record
    window.download_combo.setCurrentIndex(3)
    assert window.download_period_combo.count() == 2
    assert window.download_report.record.export_timestamp.startswith("2026-10")
    window.download_period_combo.setCurrentIndex(1)
    assert window.download_report.record.export_timestamp.startswith("2026-09")
    window.close()
    restarted = MainWindow(LocalStore(report_store.root))
    restarted.navigate(4)
    for kpi in range(1, 8):
        restarted.download_combo.setCurrentIndex(kpi)
        assert restarted.download_period_combo.count() == 2
    assert restarted.analysis is None
    restarted.close()


@pytest.mark.parametrize("kpi", range(1, 8))
def test_pdf_uses_shared_analysis_and_formatting(qapp, report_store, tmp_path, kpi):
    report = load_report(report_store, available_records(report_store, kpi)[0])
    figure = Figure(figsize=(10, 2.8))
    draw_chart(figure, report.analysis)
    path = tmp_path / default_report_filename(report)
    export_pdf(path, report.analysis, period_label(report.record), figure, report)
    text = pdf_text(path)
    for name, value in metric_items(report.analysis):
        assert re.sub(r"\s+", "", name) in text
        assert re.sub(r"\s+", "", value) in text
    assert "HistorischeEntwicklung" in text
    assert "DEMO-006" in text
    if kpi in {5, 6}:
        assert "Median(Min.)" not in text
        assert "inMinuten" not in text


def test_service_desk_direct_pdf_is_aggregate_and_score_optional(qapp, report_store, tmp_path, monkeypatch):
    window = MainWindow(report_store)
    window.navigate(4)
    window.download_combo.setCurrentIndex(8)
    assert window.analysis is None
    assert window.service_desk.report.periods == []
    assert window.pdf_button.isEnabled()
    path = tmp_path / "management.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    window.save_pdf()
    text = pdf_text(path)
    for expected in ["ServiceDesk", "Performance", "Datenbasis", "Eskalationsquote", "Ticketdifferenz", "Verlauf", "50min"]:
        assert expected in text
    for forbidden in ["DEMO-", "PRIVATE-SYNTHETIC-TITLE", "Ticket#", "Kundennummer"]:
        assert forbidden not in text
    report_store.records = [record for record in report_store.records if record.export_timestamp.startswith("2026-10")]
    window.refresh_download_choices()
    assert window.download_report.performance.current is None
    assert window.pdf_button.isEnabled()
    window.save_pdf()
    assert "PerformanceScorenoch nichtverfügbar".replace(" ", "") in pdf_text(path)
    report_store.records = [record for record in report_store.records if record.kpi_number != 1]
    window.refresh_download_choices()
    assert not window.pdf_button.isEnabled()
    assert "alle 7 KPIs" in window.download_note.text()
    window.close()


def test_download_empty_states(qapp, tmp_path, tickets):
    store = LocalStore(tmp_path / "store")
    window = MainWindow(store)
    assert "Keine Auswertungen verfügbar." in window.download_note.text()
    source = tmp_path / filename(1)
    tickets.to_excel(source, index=False)
    store.import_file(source)
    window.download_combo.setCurrentIndex(2)
    assert window.download_note.text() == "Für diese KPI sind keine Daten vorhanden."
    assert not window.pdf_button.isEnabled()
    window.close()
