"""Paginated dashboard reports rendered by Qt's native PDF engine."""

from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure
from PySide6.QtCore import QMarginsF, QRectF, QSizeF, QUrl
from PySide6.QtGui import QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument

from . import APP_NAME
from .analytics import Analysis, KPI_TITLES, detail_value, field_label, format_value, metric_items
from .charts import ROW_COLORS, draw_history, draw_score_history, draw_management
from .reports import KpiReport, ManagementReport, comparison_label, comparison_rows
from .service_desk import HISTORY_MESSAGE, score_status
from .storage import month_label, period_label


def add_chart(document: QTextDocument, figure: Figure, name: str, height: int = 260) -> str:
    image_data = BytesIO()
    figure.savefig(image_data, format="png", dpi=160, facecolor="white")
    chart_image = QImage.fromData(image_data.getvalue())
    document.addResource(QTextDocument.ResourceType.ImageResource, QUrl(f"chart:{name}"), chart_image)
    return f'<p><img src="chart:{name}" width="960" height="{height}"></p>'


def table_html(frame: pd.DataFrame, analysis: Analysis | None = None) -> str:
    headers = "".join(f'<th align="left" bgcolor="#edf1f3">{escape(field_label(str(column)))}</th>' for column in frame.columns)
    rows = []
    for index, row in enumerate(frame.itertuples(index=False, name=None)):
        bold = bool(analysis and index in analysis.maximum_rows)
        cells = "".join(f'<td>{"<b>" if bold else ""}{escape(detail_value(str(column), value))}{"</b>" if bold else ""}</td>'
                        for column, value in zip(frame.columns, row))
        background = "#f7f8f9" if index % 2 else "#ffffff"
        if analysis and analysis.row_highlights:
            background = ROW_COLORS.get(analysis.row_highlights[index], background)
        rows.append(f'<tr bgcolor="{background}">{cells}</tr>')
    if not rows:
        rows.append(f'<tr><td colspan="{len(frame.columns)}">Keine Einträge vorhanden.</td></tr>')
    return (f'<table width="100%" cellspacing="0" cellpadding="5" border="0"><thead><tr>{headers}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def metrics_html(items: list[tuple[str, str]], columns: int = 4) -> str:
    columns = min(columns, len(items))
    rows = []
    for start in range(0, len(items), columns):
        cells = []
        for name, value in items[start:start+columns]:
            size = 17 if len(value) < 22 else 11
            cells.append(f'<td width="{100//columns}%" bgcolor="#f3f5f6"><span style="font-size:{size}pt;color:#285c63">'
                         f'{escape(value)}</span><br>{escape(name)}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    return '<table width="100%" cellspacing="6" cellpadding="8">' + ''.join(rows) + '</table>'


def document_header(title: str, period: str = "") -> str:
    generated = datetime.now().astimezone().strftime("%d.%m.%Y – %H:%M Uhr (%Z)")
    return ('<style>h1{font-size:19pt;color:#29343e}h2{font-size:12pt;color:#29343e}'
            'p{color:#52616b}th,td{padding:5px}table{border-collapse:collapse}</style>'
            f'<p style="color:#e87926"><b>{APP_NAME}</b></p><h1>{escape(title)}</h1>'
            f'<p>{escape(period)}</p><p>Erstellt am {escape(generated)}</p>')


def export_pdf(path: Path, analysis: Analysis, period: str, figure: Figure, report: KpiReport | None = None) -> None:
    document = QTextDocument()
    document.setDefaultFont(QFont("Segoe UI", 9))
    title = KPI_TITLES[analysis.kpi].split(" – ",1)[-1]
    body = document_header(title, period)
    if report:
        stamp = datetime.fromisoformat(report.record.export_timestamp).strftime("%d.%m.%Y – %H:%M Uhr")
        body += f'<p>Datenquelle: {escape(report.source)} · Datenstand: {stamp} ({escape(report.record.timezone)})</p>'
    body += metrics_html(metric_items(analysis)) + add_chart(document, figure, "current")
    body += f'<p>{escape(analysis.note)}</p>'
    if report:
        body += '<h2 style="page-break-before:always">Historische Entwicklung</h2>'
        history = Figure(figsize=(10, 2.5), dpi=100)
        draw_history(history, report)
        body += add_chart(document, history, "history", 240)
        body += f'<p>{escape(report.history_note)}</p><p>{escape(comparison_label(report))}</p>'
        body += table_html(comparison_rows(report))
    page_break = ' style="page-break-before:always"' if report else ''
    body += f'<h2{page_break}>{escape(analysis.table_title)} · {len(analysis.details)} Tickets</h2>'
    body += f'<p>{escape(analysis.highlight_note)}</p>'
    if len(analysis.details.columns) > 9:
        # Repeat the ticket identifier across column groups instead of clipping a wide table.
        base = [column for column in ("Ticket#", "Titel") if column in analysis.details]
        rest = [column for column in analysis.details if column not in base]
        for start in range(0,len(rest),5):
            if start:
                body += '<h2 style="page-break-before:always">Ticketdetails · weitere Angaben</h2>'
            body += table_html(analysis.details[base+rest[start:start+5]],analysis)
    else:
        body += table_html(analysis.details, analysis)
    document.setHtml(body)
    write_document(path, title, document)


def export_management_pdf(path: Path, report: ManagementReport) -> None:
    document = QTextDocument()
    document.setDefaultFont(QFont("Segoe UI", 9))
    title = "Service Desk – Gesamtübersicht"
    body = document_header(title, period_label(report.kpis[1].record))
    stamp = max(item.record.export_timestamp for item in report.kpis.values())
    body += f'<p>Datenquelle: {escape(report.kpis[1].source)} · Datenstand: {datetime.fromisoformat(stamp):%d.%m.%Y %H:%M} · Europe/Zurich</p>'
    performance, score = report.performance, report.performance.current
    if score:
        status, color = score_status(score.value)
        body += f'<h2>Service Desk Performance</h2><p style="font-size:25pt;color:{color}"><b>{format_value(score.value)} %</b> · {status}</p>'
    else:
        body += f'<h2>Performance Score noch nicht verfügbar</h2><p>{HISTORY_MESSAGE}</p><p>{escape(performance.issue)}</p>'
    body += '<p>Basierend auf der Entwicklung der Service-KPIs. 100 % bedeutet keine Verschlechterung, keine SLA-Erfüllung. '
    body += 'Neue und geschlossene Tickets sind ausschliesslich Kontext. Positive Ticketdifferenz: mehr geschlossen als neu eingegangen.</p>'
    body += metrics_html(list(report.metrics.items()), 3)
    for kpi, item in report.kpis.items():
        if item.analysis.references.get("invalid_values"):
            body += f'<p>KPI {kpi}: {escape(item.analysis.note)}</p>'
    body += '<h2 style="page-break-before:always">Service Desk auf einen Blick</h2>'
    summary = Figure(figsize=(10, 4.6), dpi=100)
    draw_management(summary, report)
    body += add_chart(document, summary, "management", 480)
    body += '<h2 style="page-break-before:always">Datenbasis und Performance</h2>'
    sources = [[KPI_TITLES[kpi].split(" – ",1)[-1], period_label(item.record), datetime.fromisoformat(item.record.export_timestamp).strftime("%d.%m.%Y %H:%M"), item.record.timezone, item.source]
               for kpi, item in report.kpis.items()]
    body += table_html(pd.DataFrame(sources, columns=["KPI", "Berichtszeitraum / Datenstand", "Exportzeitpunkt", "Zeitzone", "Datenquelle"]))
    body += '<p>Monats-KPIs und Snapshots können unterschiedliche Zeitbezüge haben. Abschlussverhältnis und Ticketdifferenz werden nur für denselben Berichtsmonat berechnet.</p>'
    if score:
        if score.current.period_start:
            selected = f'{datetime.fromisoformat(score.current.period_start):%d.%m.%Y %H:%M} – {datetime.fromisoformat(score.current.period_end):%d.%m.%Y %H:%M}'
            previous = f'{datetime.fromisoformat(score.previous.period_start):%d.%m.%Y %H:%M} – {datetime.fromisoformat(score.previous.period_end):%d.%m.%Y %H:%M}'
            body += f'<p>Score: ausgewählter Zeitraum {selected} · Vergleich: {previous}. '
        else:
            body += f'<p>Score: Exportmonat {month_label(score.current.month)} · Vergleich: {month_label(score.previous.month)}. '
        if performance.previous_score:
            delta = score.value-performance.previous_score.value
            body += f'{"Vorheriger Zeitraum" if score.current.period_start else "Vormonat"}: {format_value(performance.previous_score.value)} % · Veränderung: {"+" if delta > 0 else ""}{format_value(delta)} Prozentpunkte.'
        body += '</p>'
        body += table_html(pd.DataFrame([[name, f"{format_value(float(value))} %", "20 %"] for name, value in score.areas.items()],
                                       columns=["Teilbereich", "Score", "Gewicht"]))
        body += '<p>Teilscore: 100 %, wenn aktuell ≤ vorher, sonst 100 × vorher / aktuell. Backlog und wartende Tickets: jeweils Mittel aus Anzahl und Anteil über 30 Tage. '
        body += 'Eskalationen: Quote; Zeiten: Median. Gesamtscore: Mittel der fünf Bereiche. Verbesserungen sind bei 100 % gedeckelt.</p>'
    for position, (kpi, item) in enumerate(report.kpis.items()):
        page_break = ' style="page-break-before:always"' if position % 2 == 0 else ''
        body += f'<h2{page_break}>{escape(KPI_TITLES[kpi].split(" – ",1)[-1])} · Verlauf</h2>'
        figure = Figure(figsize=(10, 1.8), dpi=100)
        draw_history(figure, item)
        body += add_chart(document, figure, f"history-{kpi}", 125)
        body += f'<p>{escape(comparison_label(item))}</p>' + table_html(comparison_rows(item))
        if item.history_note:
            body += f'<p>{escape(item.history_note)}</p>'
    if performance.scores:
        body += '<h2>Service Desk Performance im Zeitverlauf</h2><p>' + ('Ausgewählte Intervalle' if performance.scores[-1].current.period_start else 'Exportmonate') + ' · nur vollständig vergleichbare Datenstände; Lücken werden nicht verbunden.</p>'
        figure = Figure(figsize=(10, 1.8), dpi=100)
        draw_score_history(figure, performance)
        body += add_chart(document, figure, "score", 165)
    document.setHtml(body)
    write_document(path, title, document)


def write_document(path: Path, title: str, document: QTextDocument) -> None:
    temporary = path.with_name(path.name + ".tmp")
    writer = None
    painter = QPainter()
    try:
        writer = QPdfWriter(str(temporary))
        writer.setResolution(96)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        writer.setPageMargins(QMarginsF(12, 12, 12, 12))
        writer.setTitle(title)
        writer.setCreator(APP_NAME)
        width, height = writer.width(), writer.height()
        document.setPageSize(QSizeF(width, height - 28))
        if not painter.begin(writer):
            raise OSError("PDF-Ausgabedatei kann nicht geöffnet werden.")
        for page in range(document.pageCount()):
            if page and not writer.newPage():
                raise OSError("PDF-Seite konnte nicht erstellt werden.")
            painter.save()
            painter.setClipRect(QRectF(0, 0, width, height - 28))
            painter.translate(0, -page * (height - 28))
            document.drawContents(painter, QRectF(0, page * (height - 28), width, height - 28))
            painter.restore()
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(0, height - 5, f"{APP_NAME}  ·  Seite {page + 1} / {document.pageCount()}")
        painter.end()
        del writer
        writer = None
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise OSError("PDF-Datei konnte nicht erstellt werden.")
        temporary.replace(path)
    finally:
        if painter.isActive():
            painter.end()
        if writer is not None:
            del writer
        temporary.unlink(missing_ok=True)
