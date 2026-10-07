from dataclasses import asdict, replace

import pandas as pd
import pytest

from conftest import filename
from parcom_analytics import service_desk as desk
from parcom_analytics.storage import ImportRecord, LocalStore, parse_filename


@pytest.fixture
def history(tmp_path, tickets, monkeypatch):
    store = LocalStore(tmp_path / "storage")
    frames = {}

    def add(date, kpis=range(1, 8), time="10-52", zone="Europe_Zurich", data=None):
        for kpi in kpis:
            name = filename(kpi, date, time, zone)
            record = ImportRecord(**asdict(parse_filename(name)), original_filename=name,
                                  stored_filename=name, stored_path=name, sha256="0" * 64)
            store.records.append(record)
            frames[name] = (tickets if data is None else data).copy()
        return store

    monkeypatch.setattr(desk, "read_workbook", lambda path: frames[path.name])
    return store, frames, add


@pytest.mark.parametrize("before,now,expected", [(10, 10, 100), (10, 5, 100), (10, 20, 50),
                                                (0, 0, 100), (0, 1, 0), (1, 0, 100)])
def test_trend_score(before, now, expected):
    assert desk.trend_score(before, now) == expected


@pytest.mark.parametrize("value,status", [(100, "Sehr gut"), (90, "Sehr gut"), (89.9, "Gut"),
                                         (75, "Gut"), (74.9, "Aufmerksamkeit erforderlich"),
                                         (60, "Aufmerksamkeit erforderlich"), (59.9, "Kritisch"), (0, "Kritisch")])
def test_status_boundaries(value, status):
    assert desk.score_status(value)[0] == status


def test_five_equal_areas_and_zero_handling():
    previous = desk.Period("2026-09", {}, dict.fromkeys(desk.METRICS, 10.0))
    current = desk.Period("2026-10", {}, dict(previous.values))
    current.values.update(open_count=20, response=40, solution=5, waiting_old_share=20)
    result = desk.score_period(current, previous)
    assert result.areas == {"Backlog": 75, "Eskalationen": 100, "Reaktionszeit": 25,
                            "Lösungszeit": 100, "Wartende Tickets": 75}
    assert result.value == 75
    previous.values = dict.fromkeys(desk.METRICS, 0.0)
    current.values = dict.fromkeys(desk.METRICS, 1.0)
    assert desk.score_period(current, previous).value == 0


def test_history_gating_and_context_only(history, tickets):
    store, frames, add = history
    assert desk.build_report(store).current is None
    add("2026-08-29")
    assert desk.build_report(store).current is None
    add("2026-08-30")
    assert desk.build_report(store).current is None  # Another day is not another period.
    slower = tickets.copy()
    slower["Erstantwortzeit in Minuten"] *= 2
    slower["Lösungszeit in Minuten"] *= 2
    add("2026-09-29", data=slower)
    report = desk.build_report(store)
    assert report.current.value == 80
    assert report.previous_score is None
    add("2026-10-29")
    report = desk.build_report(store)
    assert [score.value for score in report.scores] == [80, 100]
    assert report.previous_score.value == 80
    assert report.current.current.values["open_old_share"] == pytest.approx(2 / 6)
    assert report.current.current.values["escalation_share"] == 0.5
    assert report.current.current.values["response"] == 25  # Includes the 0 minute row.
    frames[filename(1, "2026-10-29")] = pd.concat([tickets] * 10)
    frames[filename(2, "2026-10-29")] = tickets.iloc[:0]
    result = desk.build_report(store).current
    assert result.value == 100
    assert (result.current.new_count, result.current.closed_count) == (60, 0)


def test_latest_incomplete_never_falls_back_and_snapshot_day_must_match(history):
    store, _, add = history
    add("2026-09-29")
    add("2026-10-29")
    assert desk.build_report(store).current.value == 100
    add("2026-10-30", [7])
    report = desk.build_report(store)
    assert report.current is None
    assert "KPI 3, KPI 4" in report.issue
    assert "30.10.2026" in report.issue
    add("2026-10-30", [3, 4])
    assert desk.build_report(store).current.value == 100
    add("2026-11-29", [1])
    report = desk.build_report(store)
    assert report.current is None
    assert len(report.scores) == 1
    assert pd.isna(desk.history_series(report)["2026-11"])


def test_latest_export_and_year_boundary(history, tickets):
    store, _, add = history
    add("2025-12-29")
    add("2026-01-29")
    slower = tickets.copy()
    slower["Erstantwortzeit in Minuten"] *= 2
    add("2026-01-30", [5], data=slower)
    report = desk.build_report(store)
    assert report.current.value == 90
    assert report.current.current.records[5].reporting_month == "2025-12"
    assert report.current.previous.month == "2025-12"


def test_calendar_gaps_are_not_comparisons_or_connected_lines(history):
    store, _, add = history
    for month in [5, 6, 8, 9]:
        add(f"2026-{month:02}-29")
    report = desk.build_report(store)
    assert [score.current.month for score in report.scores] == ["2026-06", "2026-09"]
    series = desk.history_series(report)
    assert series.index.tolist() == ["2026-06", "2026-07", "2026-08", "2026-09"]
    assert series.isna().tolist() == [False, True, True, False]
    assert report.previous_score is None


@pytest.mark.parametrize("kpi,column,value", [(3, "Alter", "unknown"), (7, "Alter", None),
                                             (5, "Erstantwortzeit in Minuten", -1),
                                             (6, "Lösungszeit in Minuten", float("inf")),
                                             (4, "FirstResponseTimeEscalation", 2),
                                             (4, "FirstResponseTimeEscalation", None)])
def test_bad_values_prevent_partial_scores(history, kpi, column, value):
    store, frames, add = history
    add("2026-09-29")
    add("2026-10-29")
    frame = frames[filename(kpi, "2026-10-29")].astype(object)
    frame.loc[0, column] = value
    frames[filename(kpi, "2026-10-29")] = frame
    report = desk.build_report(store)
    assert report.current is None
    assert f"KPI {kpi}" in report.issue


def test_empty_stocks_are_zero_but_empty_durations_are_unknown(history, tickets):
    store, _, add = history
    add("2026-09-29")
    add("2026-10-29")
    add("2026-10-30", [3, 4, 7], data=tickets.iloc[:0])
    report = desk.build_report(store)
    assert report.current.value == 100
    assert report.current.current.values["escalation_share"] == 0
    assert report.current.current.values["open_old_share"] == 0
    add("2026-10-30", [5], data=tickets.iloc[:0])
    assert "KPI 5" in desk.build_report(store).issue
    assert desk.build_report(store).current is None


def test_missing_file_columns_previous_invalid_and_timezone(history):
    store, frames, add = history
    add("2026-09-29")
    add("2026-10-29")
    old = frames.pop(filename(3, "2026-09-29"))
    report = desk.build_report(store)
    assert report.current is None
    assert "Vergleichsmonat" in report.issue
    frames[filename(3, "2026-09-29")] = old
    frames[filename(3, "2026-10-29")] = old.drop(columns="Alter")
    assert "Spalten" in desk.build_report(store).issue
    frames[filename(3, "2026-10-29")] = old
    store.records = [replace(record, timezone="UTC") if record.export_timestamp.startswith("2026-10") else record
                     for record in store.records]
    assert "Zeitzone" in desk.build_report(store).issue
    store.records[-1] = replace(store.records[-1], timezone="Europe/Zurich")
    assert "unterschiedliche Zeitzonen" in desk.build_report(store).issue


@pytest.mark.parametrize("factor,expected,color", [(8, "↓ -10,0 Prozentpunkte", "#e08181"),
                                                  (4, "→ 0,0 Prozentpunkte", "#a2afbe")])
def test_score_decline_stability_and_incomplete_latest_ui(qapp, history, tickets, factor, expected, color):
    from parcom_analytics.ui import MainWindow

    store, _, add = history
    for month, multiplier in [(8, 1), (9, 2), (10, factor)]:
        frame = tickets.copy()
        frame["Erstantwortzeit in Minuten"] *= multiplier
        frame["Lösungszeit in Minuten"] *= multiplier
        add(f"2026-{month:02}-29", data=frame)
    window = MainWindow(store)
    window.show()
    window.navigate(3)
    page = window.service_desk
    assert page.change_label.text() == expected
    assert color in page.change_label.styleSheet()
    assert page.change_widgets["response"][2].text() == "↓ Verschlechtert"
    add("2026-11-29", [7])
    page.refresh()
    assert page.empty_card.isVisible()
    assert not page.hero.isVisible()
    assert not page.changes_card.isVisible()
    assert page.history_card.isVisible()
    assert "November 2026" in page.period_label.text()
    assert len(page.figure.axes[0].collections) == 0  # No historic point is highlighted as current.
    window.close()


def test_service_desk_import_refresh_persistence_and_navigation(qapp, tmp_path, tickets):
    from PySide6.QtCore import QSize
    from parcom_analytics.ui import MainWindow
    from test_ui import wait_for_import

    store = LocalStore(tmp_path / "storage")
    window = MainWindow(store)
    window.show()
    window.navigate(3)
    page = window.service_desk
    qapp.processEvents()
    assert page.empty_card.isVisible()
    assert not page.hero.isVisible()
    paths = []
    for month in [8, 9, 10]:
        frame = tickets.copy()
        if month == 9:
            frame["Erstantwortzeit in Minuten"] *= 2
            frame["Lösungszeit in Minuten"] *= 2
        for kpi in range(1, 8):
            path = tmp_path / filename(kpi, f"2026-{month:02}-29")
            frame.to_excel(path, index=False)
            paths.append(path)
    window.import_files(paths[:7])
    wait_for_import(qapp, window)
    assert page.report.current is None
    assert page.empty_card.isVisible()
    window.import_files(paths[7:])
    wait_for_import(qapp, window)
    qapp.processEvents()
    assert page.report.current.value == 100
    assert page.score_label.text() == "100,0 %"
    assert page.previous_label.text() == "Vormonat: 80,0 %"
    assert page.change_label.text() == "↑ +20,0 Prozentpunkte"
    assert page.hero.isVisible()
    assert not page.empty_card.isVisible()
    assert len(page.figure.axes) == 1
    assert len(page.figure.axes[0].patches) == 4
    assert page.sources_table.model().rowCount() == 21
    assert "80" not in page.context_label.text()
    window.kpi_combo.setCurrentIndex(7)
    for index in range(5):
        window.navigate(index)
        qapp.processEvents()
        assert window.size() == QSize(1280, 800)
    assert window.analysis.kpi == 7
    assert window.download_combo.currentData() is None
    window.download_combo.setCurrentIndex(7)
    assert window.download_report.analysis.kpi == 7
    window.navigate(3)
    window.resize(1050, 650)
    qapp.processEvents()
    assert window.size() == QSize(1050, 650)
    assert page.horizontalScrollBar().maximum() == 0
    page.method_button.click()
    qapp.processEvents()
    assert page.method_card.isVisible()
    assert page.horizontalScrollBar().maximum() == 0
    window.close()
    for path in paths:
        path.unlink()
    restarted = MainWindow(LocalStore(store.root))
    restarted.navigate(3)
    assert restarted.service_desk.report.current.value == 100
    assert restarted.service_desk.report.previous_score.value == 80
    restarted.close()
