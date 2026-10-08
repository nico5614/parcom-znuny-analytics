"""Presentation-only DTO adapters for the existing Python reports."""

from dataclasses import replace
from datetime import datetime

import numpy as np
import pandas as pd

from .. import agents
from ..analytics import analyze, detail_value, field_label, format_duration, format_value, metric_items
from ..live_metrics import analyze_live, server_datetime
from ..periods import PRESETS, TimeRange, ZURICH
from ..reports import HistoryPoint, comparison_label, history_metrics, history_value
from ..storage import period_label
from ..service_desk import score_status
from ..comparisons import bounds, kpi_comparisons, overview_comparisons, snapshot_context, snapshot_analysis
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


def compared_metric(name, display, data, unit="count", **kwargs):
    """Keep the accepted frontend's formatted value and add numeric semantics."""
    item = metric(name, display, data["contextLabel"], **kwargs)
    item.update({key: value for key, value in data.items() if key != "value"})
    item["numericValue"] = data["value"]
    if data["value"] is None:
        item["value"] = "–"
    elif unit == "minutes":
        item["value"] = format_duration(data["value"])
    elif unit == "percent":
        item["value"] = f'{format_value(data["value"])} %'
    else:
        item["value"] = format_value(int(data["value"]))
    return item


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
    histories = []
    for name, (_, unit) in history_metrics(result).items():
        histories.append({"label": name, "values": [history_metrics(point.analysis).get(name, (None, unit))[0] if point.analysis is not None else None for point in report.history], "color": "#4C8DFF" if histories else "#8B6CFF"})
    labels = [period_label(point.record) for point in report.history]
    types = cache.batch.frames[kpi]["Typ"].fillna("Typ unbekannt").value_counts().sort_index()
    semantic = kpi_comparisons(cache, kpi, ticket_type)
    cards = [metric(name, value) for name, value in metric_items(result)]
    if kpi in {1, 2}:
        key = "Neue Tickets" if kpi == 1 else "Geschlossene Tickets"
        cards[0] = compared_metric(cards[0]["label"], cards[0]["value"], semantic[key])
    elif kpi in {5, 6}:
        for index, item in enumerate(cards):
            stat = "median" if item["label"] == "Median" else "mean" if item["label"] == "Durchschnitt" else None
            if stat:
                cards[index] = compared_metric(item["label"], item["value"], semantic[stat], "minutes")
                cards[index]["primary"] = stat == "median"
    else:
        context = snapshot_context(cache.batch)
        for item in cards:
            item.update(context)
            item["note"] = context["contextLabel"]
        keys = list(semantic)
        cards[0] = compared_metric(cards[0]["label"], cards[0]["value"], semantic[keys[0]])
        if kpi == 4:
            cards[1] = compared_metric(cards[1]["label"], cards[1]["value"], semantic["Aktuell eskaliert"])
            cards[-1] = compared_metric(cards[-1]["label"], cards[-1]["value"], semantic["Eskalationsquote"], "percent")
        if not context["snapshotIsNow"]:
            historical = snapshot_analysis(cache, kpi, cache.batch.period.end) if ticket_type is None else None
            # Stored snapshots contain aggregates, not historic ticket details/types.
            result = historical or replace(result, chart=pd.Series(dtype=float), details=result.details.iloc[:0],
                                            note="Kein exakter Snapshot für diesen Endzeitpunkt verfügbar.")
            if historical:
                cards = [metric(name, value, context["contextLabel"]) for name, value in metric_items(historical)]
                cards[0] = compared_metric(cards[0]["label"], cards[0]["value"], semantic[keys[0]])
            else:
                for item in cards:
                    item["value"] = "–"
            types = pd.Series(dtype=int)
    comparison_data = pd.DataFrame([
        [name, history_value(item["previous"], item.get("unit", "percent" if name == "Eskalationsquote" else "count")) if item["previous"] is not None else "–",
         history_value(item["value"], item.get("unit", "percent" if name == "Eskalationsquote" else "count")) if item["value"] is not None else "–",
         item["delta"] if item["deltaAvailable"] else "Kein Vergleich verfügbar"]
        for name, item in semantic.items()], columns=["Kennzahl", "Vorher", "Ausgewählt", "Veränderung"])
    comparisons = table(comparison_data)
    return json_value({"title": KPI_TITLES[kpi].split(" – ", 1)[-1], "description": KPI_DESCRIPTIONS[kpi],
                       "metrics": cards, "primaryStatistic": "median" if kpi in {5, 6} else None,
                       "comparisons": semantic, **bounds(cache.batch.period),
                       "chart": chart(result), "history": {"title": "Entwicklung", "kind": "line", "labels": labels, "datasets": histories, "unitLabel": {"minutes": "Minuten", "percent": "%", "count": "Tickets"}[next(iter(history_metrics(result).values()))[1]]},
                       "historyNote": report.history_note + " " + ("Delta nur mit exaktem Start-Snapshot; keine Schätzung aus benachbarten Beobachtungen." if kpi in {3, 4, 7} else comparison_label(report)), "comparison": comparisons,
                       "types": list(TYPES), "typeChart": {"title": "Tickettypen", "kind": "bar", "labels": types.index.tolist(), "datasets": [{"label": "Tickets", "values": types.values.tolist(), "color": "#32D5FF"}]},
                       "note": result.note, "highlightNote": result.highlight_note,
                       "tableTitle": result.table_title, "table": table(result.details, result, page)})


def identities(cache, settings, apply_overrides=True):
    registry = agents.discover(cache.batch, settings.get("agent_registry", {}))
    overrides = settings.get("agent_overrides", {}) if apply_overrides else {}
    return {key: agents.resolved_identity(item, overrides.get(key)) if apply_overrides else item
            for key, item in registry.items()}


def selected_agents(cache, settings):
    return set(settings.get("team_selection", [key for key in agents.SEED_AGENTS if key != "1"])) & set(identities(cache, settings))


def agent_rows(cache, settings, agent_id=None):
    chosen = {agent_id} if agent_id else selected_agents(cache, settings)
    registry = identities(cache, settings)
    # Rank against every observed human, regardless of the frontend's team filter.
    rows = [row for row in agents.metrics(cache.batch, sorted(registry)) if row["id"] in chosen]
    for row in rows:
        item = registry[row["id"]]
        row.update({"displayName": item["name"], "abbreviation": item["code"], "Techniker": item["code"]})
        row["label"] = item["code"] if not item["code"].startswith("ID ") else (item["login"] or item["code"]) + " · Kürzel nicht zugeordnet"
    return sorted(rows, key=lambda row: (-(row["Geschlossen"] or 0), row["label"]))


def agents_dto(cache, settings, agent_id=None, page=0):
    registry = identities(cache, settings)
    if agent_id is not None and agent_id not in registry:
        raise ValueError("Unbekannter Techniker.")
    chosen = {agent_id} if agent_id else selected_agents(cache, settings)
    rows = agent_rows(cache, settings, agent_id)
    batch = cache.batch
    activity = pd.DataFrame(batch.agents)
    if not activity.empty and "Queue" in activity:
        from ..znuny import DEFAULT_QUEUES
        activity = activity.loc[activity["Queue"].isin(DEFAULT_QUEUES) | activity["Queue"].isna()]
    current = activity.loc[activity["period"].eq("current")] if not activity.empty else activity
    response = current.loc[current["ResponseByID"].isin(chosen)] if not current.empty else current
    if not response.empty:
        response = response.drop_duplicates("TicketID")
    from ..analytics import numeric_values
    times = numeric_values(response["response_minutes"]).dropna() if not response.empty else []
    median = float(times.median()) if len(times) else None
    mean = float(times.mean()) if len(times) else None
    cards = [metric(name, sum(row[name] for row in rows) if all(row[name] is not None for row in rows) else "–", snapshot_context(batch)["contextLabel"] if name in ("Aktuell im Besitz", "Davon gesperrt") else "Ausgewählter Zeitraum")
             for name in ("Aktuell im Besitz", "Davon gesperrt", "Geschlossen", "Erstantworten")]
    cards.append(metric("Median Reaktionszeit", format_duration(median), "Ereignisbasierte Erstantworten"))
    cards[-1].update({"median": median if batch.history_loaded else None,
                     "mean": mean if batch.history_loaded else None, "primaryStatistic": "median"})
    for item in cards[:2]:
        item.update({**snapshot_context(batch), "metricType": "snapshot", "deltaAvailable": False,
                     "snapshotAvailable": snapshot_context(batch)["snapshotIsNow"]})
    owned = batch.frames[3].loc[batch.frames[3]["OwnerID"].map(str).isin(chosen)].copy()
    if not snapshot_context(batch)["snapshotIsNow"]:
        owned = owned.iloc[:0]
    events = current.loc[current["ClosedByID"].isin(chosen) | current["ResponseByID"].isin(chosen)].copy() if not current.empty else current
    combined = pd.concat([owned, events], ignore_index=True).groupby("TicketID", sort=False, dropna=False).first().reset_index()
    for source, target in (("OwnerID", "Besitzer"), ("ClosedByID", "Geschlossen durch"), ("ResponseByID", "Erste Antwort")):
        combined[target] = combined[source].map(lambda value: registry.get(str(value), {}).get("code", agents.code(value))) if source in combined else "–"
    details = combined.reindex(columns=["Ticket#", "Titel", "Typ", "Status", "Besitzer", "Sperre", "Geschlossen durch", "Erste Antwort"])
    details.attrs["ticket_ids"] = dict(zip(combined["Ticket#"].map(str), combined["TicketID"].map(str)))
    most = max((row["Geschlossen"] or 0 for row in rows), default=0)
    leaders = " / ".join(row["label"] for row in rows if row["Geschlossen"] == most)
    system = int(current["ClosedByID"].eq("1").sum()) if not current.empty else 0
    unknown = int(batch.frames[2]["ClosedByID"].isna().sum())
    history_note = "Ticket-Historie noch nicht geladen. Historische Agentenkennzahlen sind nicht verfügbar."
    if not batch.history_loaded:
        for card in cards[2:]:
            card["value"] = "–"
        for row in rows:
            row["Geschlossen"] = row["Erstantworten"] = row["Reaktionszeit (Min.)"] = None
    # Include a winner outside the selected team, too.
    global_rows = agents.metrics(batch, sorted(registry))
    winners = [{**row, "displayName": registry[row["id"]]["name"], "abbreviation": registry[row["id"]]["code"]}
               for row in global_rows if row["isPeriodWinner"]]
    return json_value({"registry": list(sorted(registry.values(), key=lambda item: item["name"])), "selected": sorted(selected_agents(cache, settings)),
                       "periodWinner": winners[0] if len(winners) == 1 else None, "periodWinners": winners,
                       "winnerAvailable": batch.history_loaded, **bounds(batch.period),
                       "historyLoaded": batch.history_loaded,
                       "metrics": cards, "rows": rows, "note": f"{len(chosen)} Techniker · SYSTEM-Abschlüsse: {system} · Unbekannte Abschlüsse: {unknown}" if batch.history_loaded else history_note,
                       "rankingNote": history_note if not batch.history_loaded else f"Meiste Abschlüsse im Zeitraum: {leaders} · {most} Tickets" if most else "Keine menschlichen Abschlüsse für die Auswahl vorhanden.",
                       "chart": {"title": "Geschlossene Tickets nach Techniker", "kind": "bar", "labels": [row["label"] for row in rows], "datasets": [{"label": "Geschlossene Tickets", "values": [row["Geschlossen"] for row in rows], "color": "#32D5FF"}]},
                       "table": table(details, page=page)})


def overview(cache, settings):
    management = cache.management()
    metrics = management.metrics
    top = [metric("Performance Score", "–", "Ausgewählter Zeitraum"),
           metric("Neue Tickets", metrics["Neue Tickets"], "Ausgewählter Zeitraum"),
           metric("Geschlossene Tickets", metrics["Geschlossene Tickets"], "Ausgewählter Zeitraum"),
           metric("Abschlussquote", metrics["Abschlussverhältnis (geschlossen / neu)"], "Geschlossen / neu"),
           metric("Aktuell offen", metrics["Offene Tickets"], "Aktueller Bestand")]
    operational_names = ("Wartende Tickets", "Überfällige Warte-Tickets", "Überfällig + gesperrt", "Offene Tickets >30 Tage")
    operational = [metric(name, metrics.get(name, "–"), "Aktueller Bestand", "danger" if name in operational_names[1:3] and metrics.get(name, "0") != "0" else "default") for name in operational_names]
    services = [metric(name, metrics[name], "Ausgewählter Zeitraum" if "Median" in name else "Aktueller Bestand") for name in ("Median Reaktionszeit", "Median Lösungszeit", "Eskalationsquote")]
    semantic = overview_comparisons(cache)
    for cards in (top, operational, services):
        for index, item in enumerate(cards):
            name = item["label"]
            if name in semantic:
                unit = "minutes" if "Reaktionszeit" in name or "Lösungszeit" in name else "percent" if "quote" in name.lower() else "count"
                cards[index] = compared_metric(name, item["value"], semantic[name], unit, tone=item["tone"])
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
    action = details.loc[details["Timer"].eq("Überfällig")].copy() if "Timer" in details else details.copy()
    action.attrs = details.attrs.copy()
    action = action[[column for column in ("Ticket#", "Titel", "Besitzer", "Timer", "Sperre") if column in action]]
    selected_score = cache.selected_performance()
    top[0] = compared_metric("Performance Score", "–", selected_score, "percent")
    top[0]["note"] = "Ausgewählter Zeitraum · unveränderte Score-Formel"
    breakdown = [{"label": item["label"],
                  "before": history_value(item["before"] * (100 if item["unit"] == "share" else 1), "percent" if item["unit"] == "share" else item["unit"]),
                  "after": history_value(item["after"] * (100 if item["unit"] == "share" else 1), "percent" if item["unit"] == "share" else item["unit"]),
                  "score": f'{format_value(item["score"])} %'} for item in selected_score["components"]]
    is_current = snapshot_context(cache.batch)["snapshotIsNow"]
    if not is_current:
        agent_chart["labels"] = []
        agent_chart["datasets"][0]["values"] = []
        action = action.iloc[:0]
    registry = identities(cache, settings)
    winners = [{**row, "displayName": registry[row["id"]]["name"], "abbreviation": registry[row["id"]]["code"]}
               for row in agents.metrics(cache.batch, sorted(registry)) if row["isPeriodWinner"]]
    return json_value({"metrics": top, "operational": operational, "services": services,
                       "comparisons": semantic, **bounds(cache.batch.period), "volume": volume,
                       "periodWinner": winners[0] if len(winners) == 1 else None, "periodWinners": winners,
                       "winnerAvailable": cache.batch.history_loaded,
                       "agentChart": agent_chart, "action": table(action, page=0, size=5),
                       "waitingNote": " · ".join(f"{name}: {metrics.get(name, '–')}" for name in ("Aktive Timer", "Ohne Timer", "Timer unbekannt", "Automatisches Schliessen vorgemerkt")) if is_current else "Historische operative Ticketdetails sind nicht verfügbar.",
                       "score": {**selected_score, "issue": selected_score["issue"] or "100 % = keine Verschlechterung; keine SLA-Bewertung.",
                                 "status": score_status(selected_score["value"])[0] if selected_score["value"] is not None else "Vergleich fehlt",
                                 "areas": [{"label": name, "value": value} for name, value in selected_score["areas"].items()], "breakdown": breakdown,
                                 "history": {"title": "Performance im Verlauf", "kind": "line", "labels": [point["end"] for point in selected_score["history"]], "datasets": [{"label": "Trendindex", "values": [point["value"] for point in selected_score["history"]], "color": "#8B6CFF"}]}}})


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
