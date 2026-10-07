"""Live-only time buckets, current escalation membership and operational details."""

from datetime import datetime, timezone
import math
import pandas as pd

from .analytics import analyze
from .periods import TimeRange, ZURICH


def server_datetime(value):
    if value is None or str(value) in ("", "0", "None", "nan", "NaT"):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            return datetime.fromtimestamp(float(value), ZURICH)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(ZURICH)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def period_series(frame, kpi, period):
    edges = period.buckets()
    stamps = frame["Erstellt" if kpi == 1 else "Schließzeit"].map(server_datetime)
    counts, labels = [], []
    for index, (start, end) in enumerate(zip(edges, edges[1:])):
        counts.append(sum(stamp is not None and start <= stamp < end for stamp in stamps))
        if (period.end-period.start).days <= 1:
            labels.append(start.strftime("%d.%m. %H:%M"))
        elif (period.end-period.start).days <= 32:
            labels.append(start.strftime("%d.%m."))
        else:
            labels.append(f"{start:%d.%m.}–{end:%d.%m.}")
    return pd.Series(counts, index=labels, dtype=int)


def analyze_live(kpi, frame, period):
    result = analyze(kpi, frame)
    if kpi in {1, 2} and isinstance(period, TimeRange):
        result.chart = period_series(frame, kpi, period)
        result.chart_title = "Neue Tickets im Zeitraum" if kpi == 1 else "Geschlossene Tickets im Zeitraum"
        result.chart_kind = "period"
        result.references["daily_mean"] = len(frame) / max(1, (period.end-period.start).total_seconds()/86400)
        result.references["daily_max"] = float(result.chart.max()) if not result.chart.empty else 0.0
    if kpi == 4 and frame["Aktuell eskaliert"].notna().all():
        mask = frame["Aktuell eskaliert"].eq(1)
        count = int(mask.sum())
        result.metrics = {"Aktuell offene Tickets":len(frame), "Davon aktuell eskaliert":count}
        result.chart = pd.Series({"Eskaliert":count, "Nicht eskaliert":len(frame)-count})
        result.chart_title = "Aktuelle Eskalationen"
        result.references["escalation_rate"] = count/len(frame)*100 if len(frame) else 0.0
        result.references["invalid_values"] = 0
        result.details = frame.loc[mask].copy()
        result.note = "Aktueller Eskalationsstatus gemäss Znuny."
        result.highlight_note = "Rot: aktuell eskalierte Tickets."
        result.row_highlights = ["critical"] * count
    indexes = result.details.index
    columns = ["Ticket#", "Titel", "Status", "Typ", "Queue", "Erstellt", "Zuletzt geändert", "Alter",
               "OwnerID", "Sperre", "Timer", "Warten bis", "Kundennummer", "Erstantwortzeit in Minuten", "Lösungszeit in Minuten"]
    result.details = frame.loc[indexes].reindex(columns=columns).copy()
    for column in ("Erstellt", "Zuletzt geändert", "Warten bis"):
        result.details[column] = result.details[column].map(lambda value: server_datetime(value).strftime("%d.%m.%Y %H:%M") if server_datetime(value) else "–")
    if kpi == 7:
        result.row_highlights = ["critical" if row["Timer"] == "Überfällig" and row["Sperre"] == "Gesperrt"
                                 else "attention" if row["Timer"] == "Überfällig" else "" for _,row in frame.loc[indexes].iterrows()]
        result.highlight_note = "Rot: überfällig und gesperrt · Amber: überfälliger Timer."
    return result


def operational_metrics(batch):
    waiting = batch.frames[7]
    overdue = waiting["Timer"].eq("Überfällig")
    known = waiting["Timer"].isin(["Kein Timer", "Aktiv", "Überfällig"])
    return {"Aktive Timer":int(waiting["Timer"].eq("Aktiv").sum()),
            "Ohne Timer":int(waiting["Timer"].eq("Kein Timer").sum()),
            "Timer unbekannt":int((~known).sum()),
            "Überfällige Warte-Tickets":int(overdue.sum()),
            "Überfällig + gesperrt":int((overdue & waiting["Sperre"].eq("Gesperrt")).sum()),
            "Automatisches Schliessen vorgemerkt":int(batch.frames[3]["StateType"].eq("pending auto").sum())}
