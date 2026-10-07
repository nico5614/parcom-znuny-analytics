"""Transparent month-to-month trend scores derived from persisted exports."""

from dataclasses import dataclass, field
from datetime import datetime
import logging

import pandas as pd

from .analytics import DataError, analyze
from .storage import ImportRecord, LocalStore, MONTHLY_KPIS, read_workbook, reporting_month

LOGGER = logging.getLogger(__name__)
HISTORY_MESSAGE = "Für die Bewertung der Entwicklung wird mindestens ein weiterer vergleichbarer Datenstand benötigt."
METRICS = {
    "open_count": ("Backlog", "Offene Tickets", "count"),
    "open_old_share": ("Backlog", "Anteil offener Tickets über 30 Tage", "share"),
    "escalation_share": ("Eskalationen", "Eskalationsquote", "share"),
    "response": ("Reaktionszeit", "Reaktionszeit (Median)", "minutes"),
    "solution": ("Lösungszeit", "Lösungszeit (Median)", "minutes"),
    "waiting_count": ("Wartende Tickets", "Wartende Tickets", "count"),
    "waiting_old_share": ("Wartende Tickets", "Anteil wartender Tickets über 30 Tage", "share"),
}


@dataclass
class Period:
    month: str
    records: dict[int, ImportRecord]
    values: dict[str, float] = field(default_factory=dict)
    new_count: int = 0
    closed_count: int = 0
    issue: str = ""


@dataclass
class Score:
    current: Period
    previous: Period
    components: dict[str, float]
    areas: dict[str, float]
    value: float


@dataclass
class Report:
    periods: list[Period]
    scores: list[Score]
    issue: str

    @property
    def current(self) -> Score | None:
        if self.scores and self.scores[-1].current.month == self.periods[-1].month:
            return self.scores[-1]
        return None

    @property
    def previous_score(self) -> Score | None:
        if self.current:
            return next((score for score in self.scores
                         if score.current.month == self.current.previous.month), None)
        return None


def trend_score(previous: float, current: float) -> float:
    """Retention of the previous level; lower raw values are better."""
    return 100.0 if current <= previous else 100.0 * previous / current


def score_status(value: float) -> tuple[str, str]:
    if value >= 90:
        return "Sehr gut", "#23784c"
    if value >= 75:
        return "Gut", "#8a7300"
    if value >= 60:
        return "Aufmerksamkeit erforderlich", "#b85b0b"
    return "Kritisch", "#bd3838"


def score_period(current: Period, previous: Period) -> Score:
    components = {key: trend_score(previous.values[key], current.values[key]) for key in METRICS}
    areas = {}
    for area, _, _ in METRICS.values():
        members = [components[key] for key, spec in METRICS.items() if spec[0] == area]
        areas[area] = sum(members) / len(members)
    # Display, status and change use the same precision; intermediate scores stay unrounded.
    return Score(current, previous, components, areas, round(sum(areas.values()) / len(areas), 1))


def select_periods(records: list[ImportRecord]) -> list[Period]:
    """Use export months, with all snapshots on the latest snapshot day."""
    periods = []
    for month in sorted({record.export_timestamp[:7] for record in records}):
        candidates = [record for record in records if record.export_timestamp[:7] == month]
        snapshot_day = max((record.export_timestamp[:10] for record in candidates
                            if record.kpi_number not in MONTHLY_KPIS), default="")
        selected = {}
        for kpi in range(1, 8):
            eligible = [record for record in candidates if record.kpi_number == kpi
                        and (kpi in MONTHLY_KPIS or record.export_timestamp[:10] == snapshot_day)]
            if eligible:
                selected[kpi] = max(eligible, key=lambda record: datetime.fromisoformat(record.export_timestamp))
        period = Period(month, selected)
        missing = set(range(1, 8)) - selected.keys()
        if missing:
            names = ", ".join(f"KPI {kpi}" for kpi in sorted(missing))
            period.issue = f"Vollständiger Datenstand fehlt: {names}."
            if snapshot_day:
                period.issue += f" Snapshots müssen gemeinsam für den {datetime.fromisoformat(snapshot_day):%d.%m.%Y} vorliegen."
        elif len({record.timezone for record in selected.values()}) != 1:
            period.issue = "Die Exporte verwenden unterschiedliche Zeitzonen und sind nicht vergleichbar."
        periods.append(period)
    return periods


def load_period(store: LocalStore, period: Period) -> None:
    if period.issue:
        return
    analyses = {}
    for kpi, record in period.records.items():
        try:
            frame = read_workbook(store.root / record.stored_path)
            analyses[kpi] = analyze(kpi, frame)
        except Exception as error:
            LOGGER.warning("Service Desk KPI %s validation failed: %s", kpi, type(error).__name__)
            reason = str(error) if isinstance(error, DataError) else "Die gespeicherte Excel-Datei kann nicht gelesen werden. Bitte erneut importieren."
            period.issue = f"KPI {kpi}: {reason}"
            return
    fill_period(period, analyses)


def fill_period(period: Period, analyses: dict) -> None:
    """Derive score inputs from the same analyses displayed in UI and PDF."""
    values = {}
    for kpi, prefix in [(3, "open"), (7, "waiting")]:
        analysis = analyses[kpi]
        count = next(iter(analysis.metrics.values()))
        if analysis.references.get("invalid_values"):
            period.issue = f"KPI {kpi}: Für den Score müssen alle Altersangaben gültig sein."
            return
        values[f"{prefix}_count"] = count
        values[f"{prefix}_old_share"] = analysis.metrics["Älter als 30 Tage"] / count if count else 0.0
    if analyses[4].references.get("invalid_values"):
        period.issue = "KPI 4: Für den Score müssen alle Eskalationsangaben vorhanden sein."
        return
    values["escalation_share"] = analyses[4].references["escalation_rate"] / 100
    for kpi, key, column in [(5, "response", "Erstantwortzeit in Minuten"),
                             (6, "solution", "Lösungszeit in Minuten")]:
        analysis = analyses[kpi]
        if not analysis.metrics["Anzahl ausgewertete Tickets"] or analysis.references.get("invalid_values"):
            period.issue = f"KPI {kpi}: Für den Score werden Tickets mit durchgehend gültigen Minutenwerten benötigt (0 ist zulässig)."
            return
        values[key] = analysis.references["median"]
    period.values = values
    period.new_count = analyses[1].metrics["Anzahl neue Tickets"]
    period.closed_count = analyses[2].metrics["Anzahl geschlossene Tickets"]


def build_report(store: LocalStore) -> Report:
    periods = select_periods(store.records)
    if not periods:
        return Report([], [], "Importieren Sie zunächst Daten für alle sieben KPIs.")
    for period in periods:
        load_period(store, period)
    return compare_periods(periods)


def compare_periods(periods: list[Period]) -> Report:
    if not periods:
        return Report([], [], HISTORY_MESSAGE)
    scores = []
    comparison_issues = {}
    by_month = {period.month: period for period in periods}
    for current in periods:
        previous_month = reporting_month(datetime.fromisoformat(current.month + "-01"))
        previous = by_month.get(previous_month)
        if current.issue:
            comparison_issues[current.month] = current.issue
        elif previous is None:
            comparison_issues[current.month] = "Ein vollständiger Datenstand des unmittelbar vorherigen Exportmonats fehlt."
        elif previous.issue:
            comparison_issues[current.month] = f"Der Vergleichsmonat ist nicht auswertbar: {previous.issue}"
        elif current.records[1].timezone != previous.records[1].timezone:
            comparison_issues[current.month] = "Die Zeitzone hat sich gegenüber dem Vergleichsmonat geändert."
        else:
            scores.append(score_period(current, previous))
    return Report(periods, scores, comparison_issues.get(periods[-1].month, ""))


def history_series(report: Report) -> pd.Series:
    """Keep calendar gaps visible instead of connecting unrelated scores."""
    if not report.scores:
        return pd.Series(dtype=float)
    months = pd.period_range(report.scores[0].current.month, report.periods[-1].month, freq="M")
    return pd.Series({score.current.month: score.value for score in report.scores}).reindex(months.astype(str))
