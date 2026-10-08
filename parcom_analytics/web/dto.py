"""Presentation-only DTO adapters for the existing Python reports."""

from dataclasses import replace
from datetime import datetime

import numpy as np
import pandas as pd

from .. import agents
from ..analytics import analyze, detail_value, field_label, format_duration, format_value, metric_items
from ..live_metrics import analyze_live, server_datetime
from ..periods import PRESETS, TimeRange, ZURICH
from ..reports import HistoryPoint, comparison_label, comparison_rows, history_metrics, history_value
from ..storage import period_label
from ..service_desk import HISTORY_MESSAGE, METRICS, score_status
from .serialization import json_value

TYPES = ("Unclassified", "Störung", "Auftrag", "Reparatur", "Abklärung", "Wartung", "Projekt", "Spam", "Bestellung")


def period_dto(period, preset=None):
    return {"start": period.start.isoformat(), "end": period.end.isoformat(), "label": period.label,
            "startInput": period.start.astimezone(ZURICH).strftime("%Y-%m-%dT%H:%M"),
            "endInput": period.end.astimezone(ZURICH).strftime("%Y-%m-%dT%H:%M"),
            "preset": preset, "presets": list(PRESETS)}


def resolve_period(selection):
    if not isinstance(selection, dict):
        raise ValueError("Bitte einen Zeitraum auswählen.")
    key = selection.get("preset")
    if key is not None:
        if key not in PRESETS:
            raise ValueError("Ungültiger Standardzeitraum.")
        return TimeRange.preset(key)
    values = []
    for name in ("start", "end"):
        value = datetime.fromisoformat(selection[name])
        values.append((value if value.tzinfo else value.replace(tzinfo=ZURICH)).astimezone(ZURICH))
    return TimeRange(*values)


def metric(name, value, note="", tone="default"):
    return {"label": name, "value": str(value), "note": note, "tone": tone}


def chart(analysis):
    values = analysis.chart
    if analysis.chart_kind == "histogram":
        if values.empty:
            labels, numbers = [], []
        else:
            numbers, edges = np.histogram(values, bins=min(12, max(1, len(values.unique()))))
            labels = [f"{format_duration(max(0, start))}–{format_duration(max(0, end))}" for start, end in zip(edges, edges[1:])]
            numbers = numbers.tolist()
    else:
        labels, numbers = [str(value) for value in values.index], [float(value) for value in values]
    return json_value({"title": analysis.chart_title, "kind": "doughnut" if analysis.chart_kind == "donut" else "bar",
                       "labels": labels, "datasets": [{"label": "Tickets", "values": numbers, "color": "#8B6CFF"}]})


def table(frame, analysis=None, page=0, size=50):
    columns = [str(column) for column in frame.columns]
    ids = frame.attrs.get("ticket_ids", {})
    rows = []
    for position in range(page * size, min((page + 1) * size, len(frame))):
        row = frame.iloc[position]
        number = detail_value("Ticket#", row.get("Ticket#"))
        ticket_id = ids.get(str(row.get("Ticket#")))
        if "TicketID" in row and pd.notna(row["TicketID"]):
            ticket_id = str(row["TicketID"])
        rows.append({"key": ticket_id or f"{number}:{position}", "ticketId": ticket_id,
                     "cells": [detail_value(column, row[column]) for column in columns],
                     "maximum": bool(analysis and position in analysis.maximum_rows),
                     "tone": analysis.row_highlights[position] if analysis and analysis.row_highlights else ""})
    return {"columns": [{"key": column, "label": field_label(column)} for column in columns],
            "rows": rows, "total": len(frame), "page": page, "pageSize": size}


def filtered_report(cache, kpi, ticket_type=None):
    report = cache.reports()[kpi]
    if ticket_type is None:
        return report
    if ticket_type not in TYPES:
        raise ValueError("Ungültiger Tickettyp.")
    batch = cache.batch
    source = batch.frames[kpi]
    analysis = analyze_live(kpi, source.loc[source["Typ"].eq(ticket_type)], batch.period)
    history = [HistoryPoint(report.record, analysis)]
    if kpi in batch.previous:
        previous = batch.previous[kpi]
        history.insert(0, HistoryPoint(report.history[-2].record, analyze(kpi, previous.loc[previous["Typ"].eq(ticket_type)])))
    return replace(report, analysis=analysis, history=history, comparable=len(history) > 1,
                   history_note="Tickettyp: " + ticket_type, source=report.source + " · Typ: " + ticket_type)


def analysis_dto(cache, kpi, ticket_type=None, page=0):
    report = filtered_report(cache, kpi, ticket_type)
    result = report.analysis
    from ..analytics import KPI_TITLES, KPI_DESCRIPTIONS
    comparisons = table(comparison_rows(report))
    histories = []
    for name, (_, unit) in history_metrics(result).items():
        histories.append({"label": name, "values": [history_metrics(point.analysis).get(name, (None, unit))[0] if point.analysis is not None else None for point in report.history], "color": "#4C8DFF" if histories else "#8B6CFF"})
    labels = [period_label(point.record) for point in report.history]
    types = cache.batch.frames[kpi]["Typ"].fillna("Typ unbekannt").value_counts().sort_index()
    return json_value({"title": KPI_TITLES[kpi].split(" – ", 1)[-1], "description": KPI_DESCRIPTIONS[kpi],
                       "metrics": [metric(name, value) for name, value in metric_items(result)],
                       "chart": chart(result), "history": {"title": "Entwicklung", "kind": "line", "labels": labels, "datasets": histories, "unitLabel": {"minutes": "Minuten", "percent": "%", "count": "Tickets"}[next(iter(history_metrics(result).values()))[1]]},
                       "historyNote": report.history_note + " " + comparison_label(report), "comparison": comparisons,
                       "types": list(TYPES), "typeChart": {"title": "Tickettypen", "kind": "bar", "labels": types.index.tolist(), "datasets": [{"label": "Tickets", "values": types.values.tolist(), "color": "#32D5FF"}]},
                       "note": result.note, "highlightNote": result.highlight_note,
                       "tableTitle": result.table_title, "table": table(result.details, result, page)})


def identities(cache, settings):
    registry = {key: agents.identity(key) for key in agents.SEED_AGENTS if key != "1"}
    registry.update(settings.get("agent_registry", {}))
    if cache.batch:
        registry.update({item["id"]: item for item in cache.batch.identities if item["id"] != "1"})
    return registry


def selected_agents(cache, settings):
    return set(settings.get("team_selection", [key for key in agents.SEED_AGENTS if key != "1"])) & set(identities(cache, settings))


def agent_rows(cache, settings, agent_id=None):
    chosen = {agent_id} if agent_id else selected_agents(cache, settings)
    rows = agents.metrics(cache.batch, sorted(chosen))
    registry = identities(cache, settings)
    for row in rows:
        item = registry[row["id"]]
        row["label"] = item["code"] if not item["code"].startswith("ID ") else (item["login"] or item["code"]) + " · Kürzel nicht zugeordnet"
    return sorted(rows, key=lambda row: (-row["Geschlossen"], row["label"]))


def agents_dto(cache, settings, agent_id=None, page=0):
    registry = identities(cache, settings)
    if agent_id is not None and agent_id not in registry:
        raise ValueError("Unbekannter Techniker.")
    chosen = {agent_id} if agent_id else selected_agents(cache, settings)
    rows = agent_rows(cache, settings, agent_id)
    batch = cache.batch
    activity = pd.DataFrame(batch.agents)
    current = activity.loc[activity["period"].eq("current")] if not activity.empty else activity
    response = current.loc[current["ResponseByID"].isin(chosen)] if not current.empty else current
    from ..analytics import numeric_values
    median = numeric_values(response["response_minutes"]).median() if not response.empty else None
    cards = [metric(name, sum(row[name] for row in rows), "Aktueller Bestand" if name in ("Aktuell im Besitz", "Davon gesperrt") else "Ausgewählter Zeitraum")
             for name in ("Aktuell im Besitz", "Davon gesperrt", "Geschlossen", "Erstantworten")]
    cards.append(metric("Median Reaktionszeit", format_duration(median), "Ereignisbasierte Erstantworten"))
    owned = batch.frames[3].loc[batch.frames[3]["OwnerID"].map(str).isin(chosen)].copy()
    events = current.loc[current["ClosedByID"].isin(chosen) | current["ResponseByID"].isin(chosen)].copy() if not current.empty else current
    combined = pd.concat([owned, events], ignore_index=True).groupby("TicketID", sort=False, dropna=False).first().reset_index()
    for source, target in (("OwnerID", "Besitzer"), ("ClosedByID", "Geschlossen durch"), ("ResponseByID", "Erste Antwort")):
        combined[target] = combined[source].map(agents.code) if source in combined else "–"
    details = combined.reindex(columns=["Ticket#", "Titel", "Typ", "Status", "Besitzer", "Sperre", "Geschlossen durch", "Erste Antwort"])
    details.attrs["ticket_ids"] = dict(zip(combined["Ticket#"].map(str), combined["TicketID"].map(str)))
    most = max((row["Geschlossen"] for row in rows), default=0)
    leaders = " / ".join(row["label"] for row in rows if row["Geschlossen"] == most)
    system = int(current["ClosedByID"].eq("1").sum()) if not current.empty else 0
    unknown = int(batch.frames[2]["ClosedByID"].isna().sum())
    history_note = "Ticket-Historie noch nicht geladen. Historische Agentenkennzahlen sind nicht verfügbar."
    if not batch.history_loaded:
        for card in cards[2:]:
            card["value"] = "–"
        for row in rows:
            row["Geschlossen"] = row["Erstantworten"] = row["Reaktionszeit (Min.)"] = None
    return json_value({"registry": list(sorted(registry.values(), key=lambda item: item["name"])), "selected": sorted(selected_agents(cache, settings)),
                       "historyLoaded": batch.history_loaded,
                       "metrics": cards, "rows": rows, "note": f"{len(chosen)} Techniker · SYSTEM-Abschlüsse: {system} · Unbekannte Abschlüsse: {unknown}" if batch.history_loaded else history_note,
                       "rankingNote": history_note if not batch.history_loaded else f"Meiste Abschlüsse im Zeitraum: {leaders} · {most} Tickets" if most else "Keine menschlichen Abschlüsse für die Auswahl vorhanden.",
                       "chart": {"title": "Geschlossene Tickets nach Techniker", "kind": "bar", "labels": [row["label"] for row in rows], "datasets": [{"label": "Geschlossene Tickets", "values": [row["Geschlossen"] for row in rows], "color": "#32D5FF"}]},
                       "table": table(details, page=page)})


def overview(cache, settings):
    management = cache.management()
    metrics, performance = management.metrics, management.performance
    score = performance.current
    score_text = f"{format_value(score.value)} %" if score else "–"
    issue = performance.issue or HISTORY_MESSAGE if not score else "100 % = keine Verschlechterung; keine SLA-Bewertung."
    top = [metric("Performance Score", score_text, "Trendindex · monatlicher Vergleich"),
           metric("Neue Tickets", metrics["Neue Tickets"], "Ausgewählter Zeitraum"),
           metric("Geschlossene Tickets", metrics["Geschlossene Tickets"], "Ausgewählter Zeitraum"),
           metric("Abschlussquote", metrics["Abschlussverhältnis (geschlossen / neu)"], "Geschlossen / neu"),
           metric("Aktuell offen", metrics["Offene Tickets"], "Aktueller Bestand")]
    operational_names = ("Wartende Tickets", "Überfällige Warte-Tickets", "Überfällig + gesperrt", "Offene Tickets >30 Tage")
    operational = [metric(name, metrics.get(name, "–"), "Aktueller Bestand", "danger" if name in operational_names[1:3] and metrics.get(name, "0") != "0" else "default") for name in operational_names]
    services = [metric(name, metrics[name], "Ausgewählter Zeitraum" if "Median" in name else "Aktueller Bestand") for name in ("Median Reaktionszeit", "Median Lösungszeit", "Eskalationsquote")]
    new, closed = (management.kpis[kpi].analysis.chart for kpi in (1, 2))
    labels = list(dict.fromkeys([*new.index, *closed.index]))
    volume = {"title": "Ticketentwicklung", "kind": "line", "labels": labels,
              "datasets": [{"label": "Neue Tickets", "values": [float(new.get(label, 0)) for label in labels], "color": "#8B6CFF"},
                           {"label": "Geschlossene Tickets", "values": [float(closed.get(label, 0)) for label in labels], "color": "#32D5FF"}]}
    rows = agent_rows(cache, settings)
    agent_chart = {"title": "Agentenverteilung", "kind": "bar", "labels": [row["label"] for row in rows],
                   "datasets": [{"label": "Aktuell im Besitz", "values": [row["Aktuell im Besitz"] for row in rows], "color": "#4C8DFF"}]}
    waiting = management.kpis[7].analysis
    details = waiting.details
    action = details.loc[details["Timer"].eq("Überfällig")].copy()
    action.attrs = details.attrs.copy()
    action = action[[column for column in ("Ticket#", "Titel", "Besitzer", "Timer", "Sperre") if column in action]]
    breakdown = []
    if score:
        for key, (_, name, unit) in METRICS.items():
            breakdown.append({"label": name, "before": history_value(score.previous.values[key] * (100 if unit == "share" else 1), "percent" if unit == "share" else unit),
                              "after": history_value(score.current.values[key] * (100 if unit == "share" else 1), "percent" if unit == "share" else unit),
                              "score": f"{format_value(score.components[key])} %"})
    return json_value({"metrics": top, "operational": operational, "services": services, "volume": volume,
                       "agentChart": agent_chart, "action": table(action, page=0, size=5),
                       "waitingNote": " · ".join(f"{name}: {metrics.get(name, '–')}" for name in ("Aktive Timer", "Ohne Timer", "Timer unbekannt", "Automatisches Schliessen vorgemerkt")),
                       "score": {"issue": issue, "status": score_status(score.value)[0] if score else "Vergleich fehlt", "areas": [{"label": name, "value": value} for name, value in score.areas.items()] if score else [], "breakdown": breakdown,
                                 "history": {"title": "Performance im Verlauf", "kind": "line", "labels": [point.current.month for point in performance.scores], "datasets": [{"label": "Trendindex", "values": [point.value for point in performance.scores], "color": "#8B6CFF"}]}}})


def ticket_details(cache, ticket_id):
    for frame in (*cache.batch.frames.values(), *cache.batch.previous.values()):
        match = frame.loc[frame["TicketID"].map(str).eq(ticket_id)]
        if match.empty:
            continue
        row = match.iloc[0]
        fields = []
        for label, column in (("Ticketnummer", "Ticket#"), ("Status", "Status"), ("Typ", "Typ"), ("Queue", "Queue"),
                              ("Erstellt", "Erstellt"), ("Geändert", "Zuletzt geändert"), ("Alter", "Alter"), ("Owner", "OwnerID"),
                              ("Lock/Free", "Sperre"), ("Warte-Timer", "Timer"), ("Warten bis", "Warten bis"),
                              ("Kundennummer", "Kundennummer"), ("First Response", "FirstResponse"),
                              ("Reaktionszeit", "Erstantwortzeit in Minuten"), ("Solution Time", "Lösungszeit in Minuten"), ("Escalation", "Aktuell eskaliert")):
            value = row.get(column)
            if column == "OwnerID":
                value = agents.code(value)
            elif column in ("Erstellt", "Zuletzt geändert", "Warten bis", "FirstResponse"):
                stamp = server_datetime(value)
                value = stamp.strftime("%d.%m.%Y %H:%M") if stamp else "–"
            elif column == "Aktuell eskaliert":
                value = {0: "Nein", 1: "Ja"}.get(value, "Unbekannt")
            elif column == "Kundennummer" and str(value) == "00325":
                value = "Kein Kunde zugewiesen"
            fields.append({"label": label, "value": detail_value(column, value)})
        return {"id": ticket_id, "number": detail_value("Ticket#", row["Ticket#"]), "title": format_value(row["Titel"]), "fields": fields}
    raise ValueError("Dieses Ticket ist im geladenen Datenstand nicht enthalten.")
