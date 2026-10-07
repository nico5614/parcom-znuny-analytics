"""Shared report selection and history, using the existing storage and analysis."""

from dataclasses import dataclass
from datetime import datetime
import logging

import pandas as pd

from .analytics import Analysis, DataError, analyze, format_duration, format_value
from .service_desk import Report, build_report
from .storage import ImportRecord, LocalStore, MONTHLY_KPIS, period_label, read_workbook

LOGGER = logging.getLogger(__name__)


@dataclass
class HistoryPoint:
    record: ImportRecord
    analysis: Analysis | None


@dataclass
class KpiReport:
    record: ImportRecord
    analysis: Analysis
    history: list[HistoryPoint]
    history_note: str = ""
    source: str = "Lokaler Import"
    comparable: bool = True


@dataclass
class ManagementReport:
    kpis: dict[int, KpiReport]
    performance: Report
    metrics: dict[str, str]


def available_records(store: LocalStore, kpi: int) -> list[ImportRecord]:
    if kpi in MONTHLY_KPIS:
        return [store.latest(kpi, month) for month in store.months(kpi)]
    # One selectable snapshot per timestamp; the last import resolves equal timestamps.
    snapshots = {record.export_timestamp: record for record in store.records if record.kpi_number == kpi}
    return sorted(snapshots.values(), key=lambda record: datetime.fromisoformat(record.export_timestamp), reverse=True)


def load_report(store: LocalStore, record: ImportRecord) -> KpiReport:
    analysis = analyze(record.kpi_number, read_workbook(store.root / record.stored_path))
    records = available_records(store, record.kpi_number)
    records = list(reversed(records[records.index(record):]))
    history, unavailable = [], []
    for candidate in records:
        try:
            previous = analysis if candidate == record else analyze(candidate.kpi_number, read_workbook(store.root / candidate.stored_path))
            if candidate.timezone != record.timezone:
                raise DataError("Abweichende Zeitzone")
        except Exception as error:
            LOGGER.warning("History KPI %s unavailable: %s", record.kpi_number, type(error).__name__)
            previous = None
            unavailable.append(period_label(candidate))
        history.append(HistoryPoint(candidate, previous))
    note = "Keine vorherigen Daten vorhanden; es wird keine Entwicklung abgeleitet." if len(history) == 1 else ""
    if unavailable:
        note = "Nicht auswertbare oder nicht vergleichbare Datenstände (Lücken im Verlauf): " + "; ".join(unavailable)
    return KpiReport(record, analysis, history, note)


def history_metrics(analysis: Analysis) -> dict[str, tuple[float, str]]:
    kpi, metrics = analysis.kpi, analysis.metrics
    if kpi in {1, 2}:
        return {next(iter(metrics)): (float(next(iter(metrics.values()))), "count")}
    if kpi in {3, 7}:
        return {next(iter(metrics)): (float(next(iter(metrics.values()))), "count"),
                "Älter als 30 Tage": (float(metrics["Älter als 30 Tage"]), "count")}
    if kpi == 4:
        return {"Eskalationsquote": (analysis.references["escalation_rate"], "percent")}
    return {"Median": (analysis.references["median"], "minutes"),
            "Durchschnitt": (analysis.references["mean"], "minutes")}


def history_value(value: float, unit: str) -> str:
    if pd.isna(value):
        return "–"
    if unit == "minutes":
        return format_duration(value)
    if unit == "percent":
        return f"{format_value(float(value))} %"
    return format_value(int(value))


def comparison_rows(report: KpiReport) -> pd.DataFrame:
    rows = []
    previous = report.history[-2].analysis if report.comparable and len(report.history) > 1 else None
    for name, (current, unit) in history_metrics(report.analysis).items():
        old = history_metrics(previous)[name][0] if previous else float("nan")
        difference = current - old
        if pd.isna(difference):
            change = "Kein Vergleich verfügbar"
        else:
            sign = "+" if difference > 0 else "−" if difference < 0 else "±"
            suffix = " Prozentpunkte" if unit == "percent" else ""
            amount = format_value(abs(difference)) if unit == "percent" else history_value(abs(difference), unit)
            change = f"{sign}{amount}{suffix}"
        rows.append([name, history_value(old, unit), history_value(current, unit), change])
    return pd.DataFrame(rows, columns=["Kennzahl", "Vorher", "Ausgewählt", "Veränderung"])


def comparison_label(report: KpiReport) -> str:
    if not report.comparable:
        return "Für diesen Zeitraum ist kein vergleichbarer vorheriger Datenstand vorhanden."
    if len(report.history) < 2:
        return "Kein vorheriger Datenstand vorhanden"
    return "Vergleich mit: " + period_label(report.history[-2].record)


def load_management_report(store: LocalStore) -> ManagementReport:
    records = {kpi: available_records(store, kpi) for kpi in range(1, 8)}
    missing = [str(kpi) for kpi, candidates in records.items() if not candidates]
    if missing:
        raise DataError("Für die Service-Desk-Gesamtübersicht werden Daten für alle 7 KPIs benötigt. "
                        "Fehlende KPIs: " + ", ".join(missing))
    kpis = {kpi: load_report(store, candidates[0]) for kpi, candidates in records.items()}
    for kpi, report in kpis.items():
        analysis = report.analysis
        if analysis.references.get("invalid_values", 0) or (kpi in {5, 6} and analysis.chart.empty):
            raise DataError(f"KPI {kpi}: Für die Gesamtübersicht fehlen gültige Alters- oder Zeitwerte. Bitte prüfen Sie den Export.")
    return management_report(kpis, build_report(store))


def management_report(kpis: dict[int, KpiReport], performance: Report) -> ManagementReport:
    metrics = {"Neue Tickets": format_value(kpis[1].analysis.metrics["Anzahl neue Tickets"]),
               "Geschlossene Tickets": format_value(kpis[2].analysis.metrics["Anzahl geschlossene Tickets"])}
    new = kpis[1].analysis.metrics["Anzahl neue Tickets"]
    closed = kpis[2].analysis.metrics["Anzahl geschlossene Tickets"]
    same_month = period_label(kpis[1].record) == period_label(kpis[2].record)
    metrics["Abschlussverhältnis (geschlossen / neu)"] = (f"{format_value(closed / new * 100)} %" if new else "Nicht berechenbar: keine neuen Tickets") if same_month else "Nicht vergleichbare Berichtsmonate"
    metrics["Ticketdifferenz (geschlossen − neu)"] = format_value(closed - new) if same_month else "Nicht vergleichbare Berichtsmonate"
    metrics.update({
        "Offene Tickets": format_value(kpis[3].analysis.metrics["Aktuell offene Tickets"]),
        "Offene Tickets >30 Tage": format_value(kpis[3].analysis.metrics["Älter als 30 Tage"]),
        "Eskalationsquote": f'{format_value(kpis[4].analysis.references["escalation_rate"])} %',
        "Median Reaktionszeit": format_duration(kpis[5].analysis.references["median"]),
        "Median Lösungszeit": format_duration(kpis[6].analysis.references["median"]),
        "Wartende Tickets": format_value(kpis[7].analysis.metrics["Anzahl wartende Tickets"]),
        "Wartende Tickets >30 Tage": format_value(kpis[7].analysis.metrics["Älter als 30 Tage"]),
    })
    return ManagementReport(kpis, performance, metrics)


def default_report_filename(report: KpiReport | ManagementReport) -> str:
    if isinstance(report, ManagementReport):
        return f"Service_Desk_{datetime.now():%Y-%m-%d}.pdf"
    names = {1: "Neue_Tickets", 2: "Geschlossene_Tickets", 3: "Offene_Tickets", 4: "Eskalationen",
             5: "Reaktionszeit", 6: "Loesungszeit", 7: "Wartende_Tickets"}
    record = report.record
    period = (f"{record.period_start}_{record.period_end}" if getattr(record, "period_start", None)
              else record.reporting_month or datetime.fromisoformat(record.export_timestamp).strftime("%Y-%m-%d_%H-%M"))
    return f"KPI_{record.kpi_number}_{names[record.kpi_number]}_{period}.pdf"
