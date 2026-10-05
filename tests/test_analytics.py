import pandas as pd
import pytest

from parcom_analytics.analytics import DataError, analyze, parse_age


@pytest.mark.parametrize("value, expected", [("31 m", 31), ("2 h 45 m", 165), ("3 d 18 h", 5400),
                                            ("22 d 1 h", 31740), ("152 d 2 h", 219000),
                                            ("446 d 18 h", 643320), ("0 m", 0)])
def test_age_parser(value, expected):
    assert parse_age(value) == expected


@pytest.mark.parametrize("value", [None, "", "unknown", "-5 m", "3 days", "1 h garbage", 42])
def test_invalid_age(value):
    assert parse_age(value) is None


@pytest.mark.parametrize("kpi, field", [(1, "Anzahl neue Tickets"), (2, "Anzahl geschlossene Tickets")])
def test_monthly_counts_and_days(tickets, kpi, field):
    result = analyze(kpi, tickets)
    assert result.metrics[field] == 6
    assert result.chart.sum() == 6
    assert len(result.chart) == 31
    assert result.chart.iloc[0 if kpi == 1 else 1] == 2


@pytest.mark.parametrize("kpi", [3, 7])
def test_age_metrics_and_oldest_first(tickets, kpi):
    result = analyze(kpi, tickets)
    assert list(result.metrics.values())[0] == 6
    assert list(result.metrics.values())[1] == "446 d 18 h"
    assert result.metrics["Älter als 7 Tage"] == 3
    assert result.metrics["Älter als 30 Tage"] == 2
    assert result.details.iloc[0]["Ticket#"] == "DEMO-006"
    assert result.chart.sum() == 6
    if kpi == 3:
        assert result.metrics["Älter als 14 Tage"] == 3


def test_age_boundaries_and_unknowns(tickets):
    tickets["Alter"] = ["7 d", "14 d", "30 d", "30 d 1 m", None, "invalid"]
    result = analyze(3, tickets)
    assert result.metrics["Älter als 7 Tage"] == 3
    assert result.metrics["Älter als 14 Tage"] == 2
    assert result.metrics["Älter als 30 Tage"] == 1
    assert result.chart["Unbekannt"] == 2
    assert result.note


@pytest.mark.parametrize("kpi", [3, 7])
@pytest.mark.parametrize("missing", [["Status"], ["Priorität"], ["Status", "Priorität"]])
def test_age_kpis_allow_missing_optional_detail_columns(tickets, kpi, missing):
    expected = analyze(kpi, tickets)
    result = analyze(kpi, tickets.drop(columns=missing))
    assert result.metrics == expected.metrics
    pd.testing.assert_series_equal(result.chart, expected.chart)
    assert result.details["Ticket#"].tolist() == expected.details["Ticket#"].tolist()
    for column in missing:
        assert result.details[column].isna().all()
        assert column in result.note
    for column in set(result.details.columns) - set(missing):
        pd.testing.assert_series_equal(result.details[column], expected.details[column])


@pytest.mark.parametrize("kpi", [3, 7])
def test_optional_column_warning_preserves_invalid_age_warning(tickets, kpi):
    tickets.loc[0, "Alter"] = "invalid"
    result = analyze(kpi, tickets.drop(columns=["Status", "Priorität"]))
    assert "Status" in result.note and "Priorität" in result.note
    assert "1 Tickets ohne gültige Altersangabe" in result.note
    assert result.chart["Unbekannt"] == 1


def test_escalation_follow_up(tickets):
    result = analyze(4, tickets)
    assert result.metrics == {"Offene Tickets im Export": 6, "Davon Erstantwort eskaliert": 3}
    assert result.details["Ticket#"].tolist() == ["DEMO-002", "DEMO-003", "DEMO-006"]
    assert result.chart.tolist() == [3, 3]


@pytest.mark.parametrize("kpi, mean, median", [(5, 30, 25), (6, 300, 180)])
def test_duration_statistics_keep_zero(tickets, kpi, mean, median):
    result = analyze(kpi, tickets)
    assert result.metrics == {"Anzahl ausgewertete Tickets": 6, "Durchschnitt (Min.)": mean,
                              "Median (Min.)": median, "Werte mit 0 Minuten": 1}
    assert result.details.iloc[0]["Ticket#"] == "DEMO-006"
    assert result.chart.min() == 0


def test_invalid_numbers_are_not_silently_counted(tickets):
    tickets["Erstantwortzeit in Minuten"] = [0, "1.234,5", "10,5", -1, float("inf"), None]
    result = analyze(5, tickets)
    assert result.metrics["Anzahl ausgewertete Tickets"] == 3
    assert result.metrics["Durchschnitt (Min.)"] == 415
    assert result.metrics["Werte mit 0 Minuten"] == 1
    assert "3 Tickets" in result.note


def test_mixed_german_and_iso_dates(tickets):
    tickets["Erstellt"] = ["01.08.2026", "2026-08-01 12:30:00", "02.08.2026 13:00", None, "bad", "2026-08-31"]
    result = analyze(1, tickets)
    assert result.chart["01.08."] == 2
    assert result.chart.sum() == 4
    assert "2 Tickets" in result.note


@pytest.mark.parametrize("kpi", range(1, 8))
def test_missing_columns(tickets, kpi):
    with pytest.raises(DataError, match="nicht alle benötigten Spalten"):
        analyze(kpi, tickets.drop(columns="Ticket#"))


@pytest.mark.parametrize("kpi", range(1, 8))
def test_empty_workbooks_have_zero_metrics(tickets, kpi):
    result = analyze(kpi, tickets.iloc[:0])
    assert list(result.metrics.values())[0] == 0
    assert result.details.empty


def test_calculation_does_not_modify_input(tickets):
    before = tickets.copy(deep=True)
    for kpi in range(1, 8):
        analyze(kpi, tickets)
    pd.testing.assert_frame_equal(before, tickets)
