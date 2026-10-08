from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from parcom_analytics.comparisons import comparison, durations, overview_comparisons, snapshot_context
from parcom_analytics.live_cache import LiveCache
from parcom_analytics.periods import TimeRange, ZURICH
from parcom_analytics.web.dto import overview, analysis_dto, resolve_period
from parcom_analytics.web.settings import Settings
from parcom_analytics.web.validation import validation_batch


@pytest.fixture
def cache(tmp_path):
    cache = LiveCache(tmp_path)
    cache.update(validation_batch())
    return cache


@pytest.mark.parametrize("preset,days", [("1T", 1), ("1W", 7), ("1M", 30), ("3M", 92), ("6M", 183), ("1J", 365)])
def test_rolling_end_and_equal_previous(preset, days):
    end = datetime(2026, 10, 8, 12, tzinfo=ZURICH)
    period = TimeRange.preset(preset, end)
    assert period.end == end
    assert (period.end - period.start).days == days
    start, finish = period.previous
    assert finish == period.start
    assert finish.astimezone(timezone.utc) - start.astimezone(timezone.utc) == end.astimezone(timezone.utc) - period.start.astimezone(timezone.utc)


def test_custom_exact_bounds_and_dst():
    selection = {"start": "2026-03-25T12:34", "end": "2026-04-01T13:56"}
    period = resolve_period(selection)
    assert period.start.strftime("%Y-%m-%dT%H:%M") == selection["start"]
    assert period.end.strftime("%Y-%m-%dT%H:%M") == selection["end"]
    start, end = period.previous
    assert end.astimezone(timezone.utc) - start.astimezone(timezone.utc) == period.end.astimezone(timezone.utc) - period.start.astimezone(timezone.utc)


@pytest.mark.parametrize("name,higher", [("new", False), ("closed", True), ("closure rate", True), ("response", False), ("solution", False), ("escalation", False), ("waiting", False), ("backlog", False)])
def test_semantic_trends(name, higher):
    rising = comparison(12, 10, higher_is_better=higher)
    falling = comparison(8, 10, higher_is_better=higher)
    assert rising["trend"] == ("improvement" if higher else "deterioration")
    assert falling["trend"] == ("deterioration" if higher else "improvement")
    assert rising["delta"] == 2 and rising["deltaPercent"] == 20
    assert comparison(10, 10, higher_is_better=higher)["trend"] == "neutral"


def test_no_percent_from_zero_or_unknown_and_signed_time():
    assert comparison(10, 0)["deltaPercent"] is None
    assert comparison(None, 0)["deltaAvailable"] is False
    assert comparison(60, 132, unit="minutes")["delta"] == -72


def test_mean_secondary_median_primary_preserve_zero(cache):
    frame = cache.batch.frames[5].copy()
    frame["Erstantwortzeit in Minuten"] = [0, 10, 1000, None, -1, "invalid"] * 4
    stats = durations(frame, "Erstantwortzeit in Minuten")
    assert stats == {"median": 10, "mean": pytest.approx(1010 / 3)}
    cache.batch.frames[5] = frame
    dto = analysis_dto(cache, 5)
    assert dto["primaryStatistic"] == "median"
    assert dto["comparisons"]["median"]["value"] == 10
    assert dto["comparisons"]["mean"]["value"] == pytest.approx(1010 / 3)


def test_flow_dto_counts_closure_rate_context(cache, tmp_path):
    dto = overview(cache, Settings(tmp_path))
    data = dto["comparisons"]
    assert data["Neue Tickets"]["value"] == 28
    assert data["Neue Tickets"]["previous"] == 16
    assert data["Neue Tickets"]["trend"] == "deterioration"
    assert data["Geschlossene Tickets"]["trend"] == "improvement"
    assert data["Abschlussquote"]["value"] == pytest.approx(24 / 28 * 100)
    assert data["Neue Tickets"]["contextLabel"] == "Ausgewählter Zeitraum"
    assert dto["selectedPeriod"]["start"] == cache.batch.period.start.isoformat()
    assert dto["comparisonPeriod"]["end"] == cache.batch.period.start.isoformat()


def test_now_snapshot_no_guessed_delta(cache):
    item = overview_comparisons(cache)["Aktuell offen"]
    assert item["value"] == 32 and item["snapshotIsNow"]
    assert item["contextLabel"] == "Stand jetzt"
    assert not item["deltaAvailable"] and item["previous"] is None


def test_historical_endpoint_never_uses_current_stock(cache, tmp_path):
    end = datetime(2026, 9, 15, 23, 59, tzinfo=ZURICH)
    cache.batch = replace(cache.batch, period=TimeRange(end - timedelta(days=14), end), snapshot_is_now=False)
    item = overview_comparisons(cache)["Aktuell offen"]
    assert item["snapshotAt"] == end.isoformat() and not item["snapshotIsNow"]
    assert item["contextLabel"] == "Stand am 15.09.2026 23:59"
    assert item["value"] is None and not item["deltaAvailable"]
    dto = analysis_dto(cache, 3)
    assert all(card["value"] == "–" for card in dto["metrics"])
    assert dto["chart"]["labels"] == [] and dto["table"]["total"] == 0
    assert next(card for card in overview(cache, Settings(tmp_path))["metrics"] if card["label"] == "Aktuell offen")["value"] == "–"


def test_exact_end_and_start_snapshot_delta_survive_restart(cache, tmp_path):
    end = datetime.fromisoformat(cache.batch.captured_at)
    start = end - timedelta(days=7)
    initial = replace(cache.batch, captured_at=start.isoformat())
    initial.frames = {k: v.copy() for k, v in initial.frames.items()}
    initial.frames[3] = initial.frames[3].iloc[:20]
    cache.update(initial)
    # Request a historical endpoint already captured; today's frames differ.
    cache.batch = replace(cache.batch, period=TimeRange(start, end), snapshot_is_now=False)
    item = overview_comparisons(cache)["Aktuell offen"]
    assert item["value"] == 32 and item["previous"] == 20
    assert item["delta"] == 12 and item["trend"] == "deterioration"
    cache.update(replace(cache.batch, captured_at=(end + timedelta(seconds=10)).isoformat()))
    restored = LiveCache(tmp_path)
    assert overview_comparisons(restored)["Aktuell offen"] == item
