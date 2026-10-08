"""Numeric comparison semantics; never fetch history to infer stock changes."""

import math
from datetime import datetime, timezone

from .analytics import numeric_values
from .live_metrics import analyze_live, operational_metrics
from .periods import TimeRange, ZURICH

FLOW_CONTEXT = "Ausgewählter Zeitraum"
SNAPSHOT_KPIS = {3, 4, 7}


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def comparison(value, previous=None, *, higher_is_better=False, metric_type="flow", **context):
    value, previous = number(value), number(previous)
    delta = value - previous if value is not None and previous is not None else None
    trend = "neutral"
    if delta:
        trend = "improvement" if (delta > 0) == higher_is_better else "deterioration"
    return {"value": value, "previous": previous, "delta": delta,
            "deltaPercent": delta / abs(previous) * 100 if delta is not None and previous else None,
            "trend": trend, "metricType": metric_type, "deltaAvailable": delta is not None,
            "contextLabel": FLOW_CONTEXT, **context}


def durations(frame, column):
    values = numeric_values(frame[column]).dropna()
    return {"median": float(values.median()) if len(values) else None,
            "mean": float(values.mean()) if len(values) else None}


def bounds(period):
    start, end = period.previous
    return {"selectedPeriod": {"start": period.start.isoformat(), "end": period.end.isoformat()},
            "comparisonPeriod": {"start": start.isoformat(), "end": end.isoformat()}}


def snapshot_context(batch):
    end = batch.period.end
    if not isinstance(end, datetime):
        end = datetime.fromisoformat(batch.captured_at)
    # The endpoint is classified when loaded, so offline replay does not move it.
    is_now = batch.snapshot_is_now
    if is_now is None:
        loaded = datetime.fromisoformat(batch.load_started_at or batch.captured_at)
        is_now = abs((loaded.astimezone(timezone.utc) - end.astimezone(timezone.utc)).total_seconds()) <= 2
    return {"snapshotAt": end.isoformat(), "snapshotIsNow": is_now,
            "contextLabel": "Stand jetzt" if is_now else f"Stand am {end.astimezone(ZURICH):%d.%m.%Y %H:%M}"}


def snapshot_analysis(cache, kpi, endpoint):
    """Only exact observed timestamps qualify, never a nearby arbitrary snapshot."""
    from .live_cache import restore_analysis
    for item in cache.history.values():
        record = item["record"]
        if record["kpi_number"] == kpi and datetime.fromisoformat(record["export_timestamp"]) == endpoint:
            if kpi != 4 or item.get("escalation_source") == "server":
                return restore_analysis(item["analysis"])
    return None


def analyses_at_end(cache):
    batch = cache.batch
    current = {kpi: analyze_live(kpi, frame, batch.period) for kpi, frame in batch.frames.items()}
    if isinstance(batch.period, TimeRange) and not snapshot_context(batch)["snapshotIsNow"]:
        for kpi in SNAPSHOT_KPIS:
            current[kpi] = snapshot_analysis(cache, kpi, batch.period.end)
    return current


def kpi_comparisons(cache, kpi, ticket_type=None):
    batch = cache.batch
    if ticket_type is not None:
        # Observations are aggregate-only; they cannot reconstruct stock by type.
        current_frame = batch.frames[kpi].loc[batch.frames[kpi]["Typ"].eq(ticket_type)]
    else:
        current_frame = batch.frames[kpi]
    if kpi in SNAPSHOT_KPIS:
        context = snapshot_context(batch)
        current = analyze_live(kpi, current_frame, batch.period) if context["snapshotIsNow"] else (
            snapshot_analysis(cache, kpi, batch.period.end) if ticket_type is None else None)
        previous = snapshot_analysis(cache, kpi, batch.period.start) if ticket_type is None else None
        if kpi == 4:
            names = {"Aktuell offen": lambda a: next(iter(a.metrics.values())),
                     "Aktuell eskaliert": lambda a: list(a.metrics.values())[1],
                     "Eskalationsquote": lambda a: a.references["escalation_rate"]}
        else:
            names = {"Aktuell offen" if kpi == 3 else "Wartende Tickets": lambda a: next(iter(a.metrics.values())),
                     "Älter als 30 Tage": lambda a: a.metrics["Älter als 30 Tage"]}
        return {name: comparison(read(current) if current else None, read(previous) if previous else None,
                                 metric_type="snapshot", valueAvailable=current is not None, **context)
                for name, read in names.items()}
    previous_frame = batch.previous.get(kpi)
    if previous_frame is not None and ticket_type is not None:
        previous_frame = previous_frame.loc[previous_frame["Typ"].eq(ticket_type)]
    if kpi in {1, 2}:
        name = "Neue Tickets" if kpi == 1 else "Geschlossene Tickets"
        return {name: comparison(len(current_frame), len(previous_frame) if previous_frame is not None else None,
                                 higher_is_better=kpi == 2)}
    column = "Erstantwortzeit in Minuten" if kpi == 5 else "Lösungszeit in Minuten"
    current = durations(current_frame, column)
    previous = durations(previous_frame, column) if previous_frame is not None else {"median": None, "mean": None}
    return {name: comparison(current[name], previous[name], unit="minutes") for name in ("median", "mean")}


def overview_comparisons(cache):
    result = {}
    for kpi in range(1, 8):
        values = kpi_comparisons(cache, kpi)
        if kpi in {5, 6}:
            suffix = "Reaktionszeit" if kpi == 5 else "Lösungszeit"
            for stat, value in values.items():
                result[("Median" if stat == "median" else "Durchschnitt") + " " + suffix] = value
        else:
            if kpi == 4:
                values.pop("Aktuell offen", None)
            result.update(values)
    batch = cache.batch
    new, closed = len(batch.frames[1]), len(batch.frames[2])
    old_new, old_closed = batch.previous.get(1), batch.previous.get(2)
    old_rate = len(old_closed) / len(old_new) * 100 if old_new is not None and old_closed is not None and len(old_new) else None
    result["Abschlussquote"] = comparison(closed / new * 100 if new else None, old_rate, higher_is_better=True, unit="percent")
    context = snapshot_context(batch)
    # Operational observations store no ticket details or credentials.
    current = operational_metrics(batch) if context["snapshotIsNow"] else cache.observations.get(batch.period.end.isoformat(), {}).get("operational", {})
    previous = cache.observations.get(batch.period.start.isoformat(), {}).get("operational", {})
    for name in ("Überfällige Warte-Tickets", "Überfällig + gesperrt", "Aktuell gesperrt"):
        if name == "Aktuell gesperrt" and context["snapshotIsNow"]:
            current[name] = int(batch.frames[3]["Sperre"].eq("Gesperrt").sum())
        result[name] = comparison(current.get(name), previous.get(name), metric_type="snapshot",
                                  valueAvailable=name in current, **context)
    result["Offene Tickets >30 Tage"] = result.pop("Älter als 30 Tage")
    return result


def interval_key(start, end):
    return start.astimezone(timezone.utc).isoformat() + "/" + end.astimezone(timezone.utc).isoformat()


def selected_performance(cache):
    """Same seven components/five area weights, applied to exact selected bounds."""
    from .live_cache import restore_analysis
    from .service_desk import METRICS, Period, fill_period, score_period
    batch, period = cache.batch, cache.batch.period
    selected = bounds(period)
    previous_start, previous_end = period.previous
    duration = previous_end.astimezone(timezone.utc) - previous_start.astimezone(timezone.utc)
    older_start = (previous_start.astimezone(timezone.utc) - duration).astimezone(ZURICH)

    def inputs(start, end, current=False):
        analyses = analyses_at_end(cache) if current else {
            kpi: snapshot_analysis(cache, kpi, end) for kpi in SNAPSHOT_KPIS}
        if not current:
            flow = cache.intervals.get(interval_key(start, end), {})
            analyses.update({int(key): restore_analysis(value) for key, value in flow.items()})
        result = Period(end.isoformat(), {})
        if any(analyses.get(kpi) is None for kpi in range(1, 8)):
            result.issue = "Für den Zeitraum fehlen exakte Bestands-Snapshots oder vergleichbare Zeitmessungen."
        else:
            fill_period(result, analyses)
        return result

    current = inputs(period.start, period.end, current=True)
    previous = inputs(previous_start, previous_end)
    older = inputs(older_start, previous_start)
    score = score_period(current, previous) if not current.issue and not previous.issue else None
    old_score = score_period(previous, older) if not previous.issue and not older.issue else None
    result = comparison(score.value if score else None, old_score.value if old_score else None,
                        higher_is_better=True, unit="percent", **selected)
    result.update({"issue": current.issue or previous.issue if not score else "",
                   "areas": score.areas if score else {}, "components": [], "history": []})
    if score:
        for key, (area, label, unit) in METRICS.items():
            result["components"].append({"key": key, "area": area, "label": label, "unit": unit,
                                         "before": previous.values[key], "after": current.values[key],
                                         "score": score.components[key]})
    if old_score:
        result["history"].append({"start": previous_start.isoformat(), "end": previous_end.isoformat(), "value": old_score.value})
    if score:
        result["history"].append({"start": period.start.isoformat(), "end": period.end.isoformat(), "value": score.value})
    return result
