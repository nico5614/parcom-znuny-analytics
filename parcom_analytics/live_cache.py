"""Minimal last-run ticket cache and aggregate-only historical observations."""

from dataclasses import asdict, dataclass, replace
from copy import copy
from datetime import date, datetime
import json
import logging
import math
import os
from pathlib import Path

import pandas as pd

from .analytics import Analysis, DataError, analyze, date_values
from .live_metrics import analyze_live, operational_metrics
from .periods import TimeRange
from .live_data import DateRange, LiveBatch, NORMALIZED_COLUMNS, TIMEZONE
from .reports import HistoryPoint, KpiReport, management_report
from .service_desk import Period, compare_periods, fill_period
from .storage import FileMetadata, MONTHLY_KPIS, reporting_month

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveRecord(FileMetadata):
    stored_path: str = ""
    period_start: str | None = None
    period_end: str | None = None


def clean_json(value):
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def aggregate(analysis):
    return clean_json({"kpi": analysis.kpi, "metrics": analysis.metrics, "references": analysis.references,
                       "chart": analysis.chart.to_dict() if analysis.chart_kind != "histogram" else {},
                       "chart_title": analysis.chart_title, "chart_kind": analysis.chart_kind,
                       "table_title": analysis.table_title, "note": analysis.note})


def restore_analysis(item):
    return Analysis(item["kpi"], item["metrics"], pd.Series(item["chart"], dtype=float),
                    item["chart_title"], item["chart_kind"], pd.DataFrame(), item["table_title"], item["note"],
                    {key: float("nan") if value is None else value for key, value in item["references"].items()})


def monthly_frames(batch, month):
    start = date.fromisoformat(month + "-01")
    end = (pd.Timestamp(start) + pd.offsets.MonthEnd()).date()
    first = batch.period.start.date() if isinstance(batch.period.start, datetime) else batch.period.start
    last = batch.period.end.date() if isinstance(batch.period.end, datetime) else batch.period.end
    if isinstance(batch.period.start, datetime):
        if batch.period.start > datetime.combine(start, datetime.min.time(), batch.period.start.tzinfo) or batch.period.end < datetime.combine(end, datetime.max.time().replace(microsecond=0), batch.period.end.tzinfo):
            return None
    if first > start or last < end:
        return None
    frames = {}
    for kpi in MONTHLY_KPIS:
        frame = batch.frames[kpi]
        field = "Erstellt" if kpi == 1 else "Schließzeit"
        dates = date_values(frame[field])
        if dates.isna().any():
            raise DataError("Znuny liefert Tickets ohne gültiges Erstellungs- oder Schliessdatum.")
        frames[kpi] = frame.loc[dates.dt.strftime("%Y-%m") == month].reset_index(drop=True)
    return frames


class LiveCache:
    def __init__(self, root: Path):
        self.path = root / "live-cache.json"
        self.batch = None
        self.history = {}
        self.periods = {}
        self.observations = {}
        self.intervals = {}
        self.warning = ""
        self._reports = None
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                current = payload["current"]
                period = (TimeRange(datetime.fromisoformat(current["start"]), datetime.fromisoformat(current["end"])) if "T" in current["start"] else DateRange(date.fromisoformat(current["start"]), date.fromisoformat(current["end"])))
                datetime.fromisoformat(current["captured_at"])
                frames = {int(kpi): pd.DataFrame(rows, columns=NORMALIZED_COLUMNS, dtype=object)
                          for kpi, rows in current["frames"].items()}
                if set(frames) != set(range(1, 8)):
                    raise ValueError("Incomplete cache")
                previous = {int(kpi): pd.DataFrame(rows, columns=NORMALIZED_COLUMNS, dtype=object) for kpi,rows in current.get("previous", {}).items()}
                self.batch = LiveBatch(period, current["captured_at"], frames, previous, current.get("agents", []), current.get("note", ""), current.get("identities", []), current.get("load_started_at", ""))
                self.batch.history_loaded = current.get("history_loaded", True)
                self.batch.snapshot_is_now = current.get("snapshot_is_now")
                self.history, self.periods = payload["history"], payload["periods"]
                self.observations = payload.get("observations", {})
                self.intervals = payload.get("intervals", {})
                self.reports()
            except (ValueError, KeyError, TypeError, OSError):
                self.batch, self.history, self.periods = None, {}, {}
                self.observations = {}
                self.intervals = {}
                self.warning = "Der letzte Znuny-Datenstand konnte nicht gelesen werden. Excel-Daten bleiben verfügbar."
                LOGGER.warning("Live cache could not be read")

    def update(self, batch: LiveBatch, cancel=None):
        # Fully prepare and validate before replacing the previous offline fallback.
        analyses = {kpi: analyze(kpi, frame) for kpi, frame in batch.frames.items()}
        history, periods = dict(self.history), dict(self.periods)
        observations = dict(self.observations)
        intervals = dict(self.intervals)
        if isinstance(batch.period, TimeRange):
            from .comparisons import interval_key
            intervals[interval_key(batch.period.start, batch.period.end)] = {
                str(kpi): aggregate(analyses[kpi]) for kpi in (1, 2, 5, 6)}
            if {1, 2, 5, 6}.issubset(batch.previous):
                intervals[interval_key(*batch.period.previous)] = {
                    str(kpi): aggregate(analyze(kpi, batch.previous[kpi])) for kpi in (1, 2, 5, 6)}
            operations = operational_metrics(batch)
            operations["Aktuell gesperrt"] = int(batch.frames[3]["Sperre"].eq("Gesperrt").sum())
            observations[batch.captured_at] = {"operational": operations}
        for kpi in (3, 4, 7):
            key = f"{kpi}:{batch.captured_at}"
            record = LiveRecord(kpi, batch.captured_at, TIMEZONE, None, key)
            snapshot = analyze_live(kpi, batch.frames[kpi], batch.period) if isinstance(batch.period, TimeRange) else analyses[kpi]
            history[key] = {"record": asdict(record), "analysis": aggregate(snapshot),
                            "escalation_source":"server" if isinstance(batch.period,TimeRange) else "first_response"}
        monthly = {}
        for month in pd.period_range(batch.period.start.date() if isinstance(batch.period.start, datetime) else batch.period.start, batch.period.end.date() if isinstance(batch.period.end, datetime) else batch.period.end, freq="M").astype(str):
            frames = monthly_frames(batch, month)
            if frames is None:
                continue
            monthly[month] = {kpi: analyze(kpi, frame) for kpi, frame in frames.items()}
            for kpi, analysis in monthly[month].items():
                key = f"{kpi}:{month}"
                record = LiveRecord(kpi, batch.captured_at, TIMEZONE, month, key)
                history[key] = {"record": asdict(record), "analysis": aggregate(analysis)}
        stamp = datetime.fromisoformat(batch.captured_at)
        previous_month = reporting_month(stamp)
        records = {kpi: LiveRecord(kpi, batch.captured_at, TIMEZONE,
                                  previous_month if kpi in MONTHLY_KPIS else None) for kpi in range(1, 8)}
        score_period = Period(stamp.strftime("%Y-%m"), records)
        if previous_month in monthly:
            fill_period(score_period, {**analyses, **monthly[previous_month]})
        else:
            score_period.records = {kpi: LiveRecord(kpi, batch.captured_at, TIMEZONE, None,
                                    period_start=batch.period.start.isoformat() if kpi in MONTHLY_KPIS else None,
                                    period_end=batch.period.end.isoformat() if kpi in MONTHLY_KPIS else None) for kpi in range(1, 8)}
            score_period.issue = "Der Live-Zeitraum enthält den vorherigen Kalendermonat nicht vollständig. Für den Score werden vollständige Monatsdaten und echte Snapshots benötigt."
        periods[score_period.month] = asdict(score_period)
        safe_frames = {kpi: frame.reindex(columns=NORMALIZED_COLUMNS).astype(object).where(pd.notna(frame), None).to_dict("records")
                       for kpi, frame in batch.frames.items()}
        payload = clean_json({"current": {"start": batch.period.start.isoformat(), "end": batch.period.end.isoformat(),
                                          "captured_at": batch.captured_at, "frames": safe_frames,
                                          "previous": {kpi: frame.reindex(columns=NORMALIZED_COLUMNS).astype(object).where(pd.notna(frame), None).to_dict("records") for kpi, frame in batch.previous.items()},
                                          "agents": batch.agents, "note": batch.note, "identities":batch.identities,
                                          "load_started_at":batch.load_started_at, "history_loaded":batch.history_loaded,
                                          "snapshot_is_now":batch.snapshot_is_now},
                              "history": history, "periods": periods, "observations": observations,
                              "intervals": intervals})
        candidate = copy(self)
        candidate.batch, candidate.history, candidate.periods = batch, history, periods
        candidate.observations = observations
        candidate.intervals = intervals
        candidate._reports = None
        reports = candidate.reports()
        temporary = self.path.with_suffix(".json.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as output:
                json.dump(payload, output, ensure_ascii=False, allow_nan=False)
                output.flush()
                os.fsync(output.fileno())
            if cancel is not None and cancel.is_set():
                from .znuny import ZnunyError
                raise ZnunyError("Laden abgebrochen.")
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.batch, self.history, self.periods = batch, history, periods
        self.observations = observations
        self.intervals = intervals
        self._reports = reports

    def reports(self):
        if self._reports is not None:
            return self._reports
        if self.batch is None:
            return {}
        batch, reports = self.batch, {}
        for kpi, frame in batch.frames.items():
            analysis = analyze_live(kpi, frame, batch.period) if isinstance(batch.period, TimeRange) else analyze(kpi, frame)
            historical = False
            if isinstance(batch.period, TimeRange) and kpi in {3, 4, 7}:
                from .comparisons import snapshot_context, snapshot_analysis
                historical = not snapshot_context(batch)["snapshotIsNow"]
                if historical:
                    saved = snapshot_analysis(self, kpi, batch.period.end)
                    analysis = saved or replace(analysis,
                        metrics={key: float("nan") if isinstance(value, (int, float)) else "–" for key, value in analysis.metrics.items()},
                        references={key: float("nan") for key in analysis.references},
                        chart=pd.Series(dtype=float), details=analysis.details.iloc[:0], row_highlights=[], maximum_rows=set(),
                        note="Kein exakter Snapshot für diesen Endzeitpunkt verfügbar.")
            monthly = kpi in MONTHLY_KPIS
            single_month = (batch.period.start.day == 1 and
                            batch.period.end == (pd.Timestamp(batch.period.start) + pd.offsets.MonthEnd()).date())
            month = batch.period.start.strftime("%Y-%m") if monthly and single_month else None
            record = LiveRecord(kpi, batch.captured_at, TIMEZONE, month, f"current:{kpi}",
                                batch.period.start.isoformat() if monthly else None,
                                batch.period.end.isoformat() if monthly else None)
            history = [HistoryPoint(LiveRecord(**item["record"]), restore_analysis(item["analysis"]))
                       for item in self.history.values() if item["record"]["kpi_number"] == kpi
                       and (kpi != 4 or not isinstance(batch.period,TimeRange) or item.get("escalation_source") == "server")
                       and (not monthly or item["record"]["reporting_month"] <= batch.period.end.strftime("%Y-%m"))]
            history.sort(key=lambda item: item.record.reporting_month or item.record.export_timestamp)
            note = "Monatsverlauf: ausschliesslich vollständig geladene Kalendermonate." if monthly else "Verlauf ausschliesslich tatsächlich aufgenommener Snapshots."
            if len(history) < 2:
                note += " Für einen Verlauf wird mindestens ein weiterer Datenstand benötigt."
            if not history:
                history = [HistoryPoint(record, analysis)]
            if monthly and kpi in batch.previous:
                start, end = batch.period.previous
                old_record = LiveRecord(kpi, batch.captured_at, TIMEZONE, None, f"previous:{kpi}", start.isoformat(), end.isoformat())
                old_analysis = analyze(kpi, batch.previous[kpi])
                history = [HistoryPoint(old_record, old_analysis), HistoryPoint(record, analysis)]
                note = "Vergleich mit dem direkt vorhergehenden, gleich langen Zeitraum."
            if isinstance(batch.period, TimeRange) and kpi in {3, 4, 7}:
                context = snapshot_context(batch)
                record = replace(record, export_timestamp=batch.period.end.isoformat() if historical else batch.captured_at)
                old = snapshot_analysis(self, kpi, batch.period.start)
                history = [HistoryPoint(record, analysis)]
                if old:
                    history.insert(0, HistoryPoint(replace(record, export_timestamp=batch.period.start.isoformat()), old))
                note = context["contextLabel"] + ". Delta nur mit exaktem Start-Snapshot."
            reports[kpi] = KpiReport(record, analysis, history, note, "Znuny Live · lokal gespeicherter Datenstand",
                                     comparable=old is not None if isinstance(batch.period, TimeRange) and kpi in {3, 4, 7} else kpi in batch.previous or not monthly or single_month)
        self._reports = reports
        return reports

    def performance(self):
        if self.batch is not None and isinstance(self.batch.period, TimeRange):
            from .comparisons import selected_report
            return selected_report(self)
        periods = [Period(**{**item, "records": {int(kpi): LiveRecord(**record) for kpi, record in item["records"].items()}})
                   for _, item in sorted(self.periods.items())]
        return compare_periods(periods)

    def selected_performance(self):
        from .comparisons import selected_performance
        return selected_performance(self)

    def management(self):
        reports = self.reports()
        if len(reports) != 7:
            raise DataError("Keine lokalen Znuny-Daten verfügbar.")
        result = management_report(reports, self.performance())
        if isinstance(self.batch.period, TimeRange):
            result.metrics.update({key:str(value) for key,value in operational_metrics(self.batch).items()})
            from .comparisons import overview_comparisons, snapshot_context
            semantics = overview_comparisons(self)
            for label, key in (("Offene Tickets", "Aktuell offen"), ("Wartende Tickets", "Wartende Tickets"),
                               ("Offene Tickets >30 Tage", "Offene Tickets >30 Tage"), ("Eskalationsquote", "Eskalationsquote")):
                value = semantics[key]["value"]
                result.metrics[label] = "–" if value is None else (f"{value:.1f} %" if key == "Eskalationsquote" else str(int(value)))
            if not snapshot_context(self.batch)["snapshotIsNow"]:
                saved = self.observations.get(self.batch.period.end.isoformat(), {}).get("operational", {})
                result.metrics.update({key: str(saved[key]) if key in saved else "–" for key in operational_metrics(self.batch)})
        return result

    def clear(self):
        self.path.unlink(missing_ok=True)
        self.batch, self.history, self.periods = None, {}, {}
        self.observations = {}
        self.intervals = {}
        self._reports = None
