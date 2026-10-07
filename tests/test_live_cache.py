from datetime import date
from dataclasses import replace
import json
from pathlib import Path

import pandas as pd
import pytest

from parcom_analytics.analytics import analyze, parse_age
from parcom_analytics.live_cache import LiveCache
from parcom_analytics.live_data import DateRange, FIELD_MAP, LiveBatch, normalize_tickets
from parcom_analytics.storage import LocalStore
from conftest import filename


@pytest.fixture
def batch(tickets):
    raw = [{**{key: row.get(column) for key, column in FIELD_MAP.items()},
            "Age": parse_age(row["Alter"]) * 60, "CustomerID": "PRIVATE-CUSTOMER",
            "SessionID": "SECRET-SESSION", "Password": "SECRET-PASSWORD"}
           for row in tickets.to_dict("records")]
    frame = normalize_tickets(raw)
    return LiveBatch(DateRange(date(2026, 8, 1), date(2026, 8, 31)), "2026-09-29T10:52:00+02:00",
                     {kpi: frame.copy() for kpi in range(1, 8)})


@pytest.mark.parametrize("kpi", range(1, 8))
def test_excel_live_same_engine_and_zero_values(tickets, batch, kpi):
    excel, live = analyze(kpi, tickets), analyze(kpi, batch.frames[kpi])
    assert excel.metrics == live.metrics
    pd.testing.assert_series_equal(excel.chart, live.chart)


def test_missing_extended_values_remain_unknown(batch):
    frame = batch.frames[4].copy()
    frame["FirstResponseTimeEscalation"] = [None, 1, 0, None, 0, 1]
    analysis = analyze(4, frame)
    assert analysis.references["escalation_rate"] == pytest.approx(100/3)
    assert "2 Tickets ohne Eskalationsfeld" in analysis.note
    assert analysis.chart.to_dict() == {"Eskaliert": 2, "Nicht eskaliert": 2, "Unbekannt": 2}
    frame["Erstantwortzeit in Minuten"] = [None, 0, 10, 20, 30, 40]
    analysis = analyze(5, frame)
    assert analysis.metrics["Anzahl ausgewertete Tickets"] == 5
    assert analysis.metrics["Werte mit 0 Minuten"] == 1


def test_cache_privacy_persistence_and_real_snapshots(tmp_path, batch):
    cache = LiveCache(tmp_path)
    cache.update(batch)
    text = cache.path.read_text(encoding="utf-8")
    for forbidden in ["Password", "SessionID", "CustomerID", "SECRET", "PRIVATE-CUSTOMER"]:
        assert forbidden not in text
    payload = json.loads(text)
    assert "Titel" not in json.dumps(payload["history"])
    assert "DEMO-" not in json.dumps(payload["history"])
    restarted = LiveCache(tmp_path)
    assert len(restarted.reports()) == 7
    assert restarted.reports()[7].record.export_timestamp == batch.captured_at
    assert len(restarted.reports()[7].history) == 1
    assert restarted.performance().current is None
    assert restarted.management().metrics["Median Reaktionszeit"] == "25 min"
    restarted.clear()
    assert not restarted.path.exists() and restarted.reports() == {}


def test_live_history_ordering_and_same_existing_score_formula(tmp_path, batch):
    cache = LiveCache(tmp_path)
    cache.update(batch)
    frames = {kpi: frame.copy() for kpi, frame in batch.frames.items()}
    for frame in frames.values():
        for column in ["Erstellt", "Schließzeit"]:
            frame[column] = pd.to_datetime(frame[column]).map(lambda value: value + pd.DateOffset(months=1)).astype(str)
    # Keep only real September dates after moving the synthetic August 31 date.
    newer = LiveBatch(DateRange(date(2026, 9, 1), date(2026, 9, 30)), "2026-10-01T10:52:00+02:00", frames)
    cache.update(newer)
    report = cache.performance()
    assert report.current.value == 100
    assert [point.record.export_timestamp for point in cache.reports()[3].history] == [batch.captured_at, newer.captured_at]
    assert [point.record.reporting_month for point in cache.reports()[5].history] == ["2026-08", "2026-09"]
    assert cache.reports()[5].comparable


def test_partial_month_never_becomes_complete_score_or_monthly_trend(tmp_path, batch):
    cache = LiveCache(tmp_path)
    partial = replace(batch, period=DateRange(date(2026, 8, 5), date(2026, 8, 31)))
    cache.update(partial)
    assert not cache.reports()[1].comparable
    assert "nicht vollständig" in cache.performance().issue
    assert not any(item["record"]["reporting_month"] for item in cache.history.values())


def test_corrupt_cache_does_not_affect_excel(tmp_path):
    path = tmp_path / "live-cache.json"
    path.write_text("broken", encoding="utf-8")
    cache = LiveCache(tmp_path)
    assert cache.batch is None and cache.warning
    assert path.read_text() == "broken"


def test_delete_dataset_preserves_original_and_persists(tmp_path, tickets):
    source = tmp_path / filename(3)
    tickets.to_excel(source, index=False)
    store = LocalStore(tmp_path / "store")
    store.import_file(source)
    record = store.records[0]
    store.delete_record(record)
    assert source.exists()
    assert not (store.root / record.stored_path).exists()
    assert LocalStore(store.root).records == []


def test_delete_rollback_on_index_failure(tmp_path, tickets, monkeypatch):
    source = tmp_path / filename(7)
    tickets.to_excel(source, index=False)
    store = LocalStore(tmp_path / "store")
    store.import_file(source)
    record = store.records[0]
    def fail(records):
        raise OSError("test write failure")
    monkeypatch.setattr(store, "_save", fail)
    with pytest.raises(OSError):
        store.delete_record(record)
    assert (store.root / record.stored_path).exists()
    assert store.records == [record]


def test_live_cache_write_failure_keeps_last_successful_state(tmp_path, batch, monkeypatch):
    cache = LiveCache(tmp_path)
    cache.update(batch)
    original = cache.path.read_bytes()
    def fail(*args):
        raise OSError("synthetic disk failure")
    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(OSError):
        cache.update(replace(batch, captured_at="2026-09-30T10:52:00+02:00"))
    assert cache.path.read_bytes() == original
    assert cache.batch.captured_at == batch.captured_at
    assert not cache.path.with_suffix(".json.tmp").exists()


def test_live_management_pdf_contains_aggregates_only(qapp, tmp_path, batch):
    from parcom_analytics.pdf_export import export_management_pdf
    from test_reports import pdf_text
    cache = LiveCache(tmp_path)
    cache.update(batch)
    target = tmp_path / "management.pdf"
    export_management_pdf(target, cache.management())
    text = pdf_text(target)
    assert "25min" in text and "ZnunyLive" in text
    for private in ["DEMO-", "SynthetischesTestticket", "PRIVATE-CUSTOMER", "SECRET"]:
        assert private not in text
