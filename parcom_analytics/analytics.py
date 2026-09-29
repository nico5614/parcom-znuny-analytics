"""Pure KPI calculations using exported rows, independent of the UI."""

from dataclasses import dataclass
from datetime import datetime
import math
import re

import pandas as pd

KPI_TITLES = {
    1: "KPI 1 – Neue Tickets letzter Monat",
    2: "KPI 2 – Geschlossene Tickets letzter Monat",
    3: "KPI 3 – Aktuell offene Tickets",
    4: "KPI 4 – Offene Tickets nach Eskalation",
    5: "KPI 5 – Reaktionszeit geschlossener Tickets",
    6: "KPI 6 – Lösungszeit geschlossener Tickets",
    7: "KPI 7 – Wartende Tickets",
}
KPI_DESCRIPTIONS = {
    1: "Zeigt alle im letzten Monat neu erstellten Tickets der PBX-Abteilung.",
    2: "Zeigt alle im letzten Monat geschlossenen Tickets der PBX-Abteilung.",
    3: "Zeigt den aktuellen offenen Ticketbestand der PBX-Abteilung inklusive wartender Tickets.",
    4: "Zeigt offene PBX-Tickets nach Eskalationsstatus und macht bereits eskalierte Tickets direkt sichtbar.",
    5: "Zeigt geschlossene Tickets der PBX-Abteilung nach Reaktionszeit und dient zur Auswertung, wie schnell auf Kundenanfragen reagiert wurde.",
    6: "Zeigt geschlossene Tickets der PBX-Abteilung nach Lösungszeit und dient zur Auswertung, wie lange die Bearbeitung bis zur Lösung eines Tickets dauert.",
    7: "Zeigt alle aktuell wartenden Tickets der PBX-Abteilung und dient zur Kontrolle und Nachverfolgung von noch nicht abgeschlossenen Fällen.",
}
AGE_COLUMNS = ["Ticket#", "Alter", "Titel", "Status", "Priorität"]
DETAIL_COLUMNS = {
    1: ["Ticket#", "Titel", "Erstellt", "Status"],
    2: ["Ticket#", "Titel", "Schließzeit", "Status"],
    3: AGE_COLUMNS,
    4: ["Ticket#", "Titel", "Alter", "Status", "Priorität", "FirstResponseTimeDestinationDate"],
    5: ["Ticket#", "Titel", "Erstantwortzeit in Minuten"],
    6: ["Ticket#", "Titel", "Lösungszeit in Minuten"],
    7: AGE_COLUMNS,
}


class DataError(ValueError):
    """A workbook cannot be analyzed; the message is suitable for the UI."""


@dataclass
class Analysis:
    kpi: int
    metrics: dict[str, int | float | str]
    chart: pd.Series
    chart_title: str
    chart_kind: str
    details: pd.DataFrame
    table_title: str
    note: str = ""


def parse_age(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(?:(\d+)\s*d\s*)?(?:(\d+)\s*h\s*)?(?:(\d+)\s*m\s*)?", value)
    if not match or all(part is None for part in match.groups()):
        return None
    days, hours, minutes = (int(part or 0) for part in match.groups())
    return days * 1440 + hours * 60 + minutes


def format_age(minutes: float) -> str:
    days, remaining = divmod(int(minutes), 1440)
    hours, minute = divmod(remaining, 60)
    if days:
        return f"{days} T {hours} Std"
    if hours:
        return f"{hours} Std {minute} Min"
    return f"{minute} Min"


def format_value(value: object) -> str:
    if pd.isna(value):
        return "–"
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, float):
        return f"{value:,.1f}".replace(",", "’").replace(".", ",")
    if isinstance(value, int):
        return f"{value:,}".replace(",", "’")
    return str(value)


def numeric_values(values: pd.Series) -> pd.Series:
    def convert(value):
        if isinstance(value, str):
            value = value.strip().replace(" ", "").replace("’", "").replace("'", "")
            if "," in value:
                value = value.replace(".", "").replace(",", ".")
        try:
            number = float(value)
            return number if math.isfinite(number) and number >= 0 else float("nan")
        except (ValueError, TypeError):
            return float("nan")
    return values.map(convert).astype(float)


def date_values(values: pd.Series) -> pd.Series:
    def convert(value):
        if pd.isna(value):
            return pd.NaT
        if isinstance(value, (int, float)):
            return pd.to_datetime(value, unit="D", origin="1899-12-30", errors="coerce")
        iso = bool(re.match(r"^\d{4}-\d{2}-\d{2}", str(value)))
        return pd.to_datetime(value, dayfirst=not iso, errors="coerce")
    return pd.to_datetime(values.map(convert), errors="coerce")


def analyze(kpi: int, source: pd.DataFrame) -> Analysis:
    frame = source.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    required = DETAIL_COLUMNS[kpi] + (["FirstResponseTimeEscalation"] if kpi == 4 else [])
    if kpi in {3, 7}:
        required = ["Ticket#", "Alter", "Titel"]
    if not frame.columns.is_unique or not set(required).issubset(frame.columns):
        raise DataError("Die importierte Datei enthält nicht alle benötigten Spalten für diese KPI.")
    details = frame.reindex(columns=DETAIL_COLUMNS[kpi]).copy()
    note = ""
    if kpi in {1, 2}:
        field = "Erstellt" if kpi == 1 else "Schließzeit"
        dates = date_values(frame[field])
        counts = dates.dropna().dt.normalize().value_counts().sort_index()
        if not counts.empty:
            start = counts.index.min().replace(day=1)
            end = counts.index.max() + pd.offsets.MonthEnd(0)
            counts = counts.reindex(pd.date_range(start, end), fill_value=0)
        counts.index = counts.index.strftime("%d.%m.")
        missing = int(dates.isna().sum())
        if missing:
            note = f"{missing} Tickets ohne gültiges Datum sind in der Gesamtzahl, aber nicht im Tagesdiagramm enthalten."
        metrics = {"Anzahl neue Tickets" if kpi == 1 else "Anzahl geschlossene Tickets": len(frame)}
        return Analysis(kpi, metrics, counts, "Tickets nach Erstellungstag" if kpi == 1 else "Tickets nach Schliessungstag",
                        "daily", details, "Ticketdetails", note)
    if kpi in {3, 7}:
        notes = []
        missing_details = [column for column in ("Status", "Priorität") if column not in frame.columns]
        if missing_details:
            notes.append(f"Nicht im Export enthalten: {', '.join(missing_details)}. Diese Angaben werden als «–» angezeigt.")
        ages = frame["Alter"].map(parse_age).astype(float)
        metrics = {"Aktuell offene Tickets" if kpi == 3 else "Anzahl wartende Tickets": len(frame),
                   "Ältestes offenes Ticket" if kpi == 3 else "Ältestes wartendes Ticket":
                       format_age(ages.max()) if ages.notna().any() else "–",
                   "Älter als 7 Tage": int((ages > 7 * 1440).sum())}
        if kpi == 3:
            metrics["Älter als 14 Tage"] = int((ages > 14 * 1440).sum())
        metrics["Älter als 30 Tage"] = int((ages > 30 * 1440).sum())
        chart = pd.Series({"Bis 7 Tage": int((ages <= 7 * 1440).sum()),
                           "Über 7–14 Tage": int(((ages > 7 * 1440) & (ages <= 14 * 1440)).sum()),
                           "Über 14–30 Tage": int(((ages > 14 * 1440) & (ages <= 30 * 1440)).sum()),
                           "Über 30 Tage": int((ages > 30 * 1440).sum())})
        missing = int(ages.isna().sum())
        if missing:
            chart["Unbekannt"] = missing
            notes.append(f"{missing} Tickets ohne gültige Altersangabe; Alterskennzahlen berücksichtigen nur gültige Werte.")
        details = details.loc[ages.sort_values(ascending=False, na_position="last", kind="stable").index]
        return Analysis(kpi, metrics, chart, "Ticketbestand nach Alter", "bar", details,
                        "Ticketdetails · älteste zuerst", " ".join(notes))
    if kpi == 4:
        flags = numeric_values(frame["FirstResponseTimeEscalation"])
        if not flags.isin([0, 1]).all():
            raise DataError("Die Spalte FirstResponseTimeEscalation enthält ungültige Werte. Erwartet werden 0 oder 1.")
        escalated = flags.eq(1)
        count = int(escalated.sum())
        return Analysis(kpi, {"Offene Tickets im Export": len(frame), "Davon Erstantwort eskaliert": count},
                        pd.Series({"Eskaliert": count, "Nicht eskaliert": len(frame) - count}),
                        "Erstantwort-Eskalation", "bar", details.loc[escalated], "Eskalierte Tickets · Nachverfolgung")
    field = "Erstantwortzeit in Minuten" if kpi == 5 else "Lösungszeit in Minuten"
    values = numeric_values(frame[field])
    valid = values.dropna()
    missing = int(values.isna().sum())
    if missing:
        note = f"{missing} Tickets ohne gültigen Minutenwert wurden nicht ausgewertet. Null-Minuten-Werte sind enthalten."
    else:
        note = "Null-Minuten-Werte sind in allen Kennzahlen enthalten."
    metrics = {"Anzahl ausgewertete Tickets": len(valid),
               "Durchschnitt (Min.)": float(valid.mean()) if len(valid) else "–",
               "Median (Min.)": float(valid.median()) if len(valid) else "–",
               "Werte mit 0 Minuten": int(valid.eq(0).sum())}
    details[field] = values
    details = details.loc[valid.sort_values(ascending=False, kind="stable").index]
    return Analysis(kpi, metrics, valid, "Verteilung der Reaktionszeit" if kpi == 5 else "Verteilung der Lösungszeit",
                    "histogram", details, "Langsamste Reaktionen" if kpi == 5 else "Längste Lösungszeiten", note)
