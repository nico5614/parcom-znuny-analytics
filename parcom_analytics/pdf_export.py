"""Paginated dashboard reports rendered by Qt's native PDF engine."""

from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path

from matplotlib.figure import Figure
from PySide6.QtCore import QMarginsF, QRectF, QSizeF, QUrl
from PySide6.QtGui import QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument

from . import APP_NAME
from .analytics import Analysis, KPI_TITLES, format_value


def export_pdf(path: Path, analysis: Analysis, period: str, figure: Figure) -> None:
    temporary = path.with_name(path.name + ".tmp")
    image_data = BytesIO()
    figure.savefig(image_data, format="png", dpi=160, facecolor="white")
    chart_image = QImage.fromData(image_data.getvalue())
    document = QTextDocument()
    document.setDefaultFont(QFont("Segoe UI", 9))
    document.addResource(QTextDocument.ResourceType.ImageResource, QUrl("chart:current"), chart_image)
    metric_cells = "".join(
        f'<td style="background:#f3f5f6;padding:10px"><span style="font-size:19pt;color:#285c63">'
        f'{escape(format_value(value))}</span><br>{escape(label)}</td>' for label, value in analysis.metrics.items()
    )
    headers = "".join(
        f'<th align="left" bgcolor="#edf1f3">{escape("Erstantwort fällig am" if column == "FirstResponseTimeDestinationDate" else column)}</th>'
        for column in analysis.details.columns
    )
    rows = []
    for index, row in enumerate(analysis.details.itertuples(index=False, name=None)):
        cells = "".join(f"<td>{escape(format_value(value))}</td>" for value in row)
        rows.append(f'<tr bgcolor="{"#f7f8f9" if index % 2 else "#ffffff"}">{cells}</tr>')
    if not rows:
        rows.append(f'<tr><td colspan="{len(analysis.details.columns)}">Keine Tickets vorhanden.</td></tr>')
    generated = datetime.now().astimezone().strftime("%d.%m.%Y – %H:%M Uhr (%Z)")
    document.setHtml(
        '<style>h1{font-size:19pt;color:#29343e}h2{font-size:12pt;color:#29343e}'
        'p{color:#52616b}th,td{padding:6px}table{border-collapse:collapse}</style>'
        f'<p style="color:#e87926"><b>{APP_NAME}</b></p>'
        f'<h1>{escape(KPI_TITLES[analysis.kpi])}</h1><p>{escape(period)}</p>'
        f'<p>Erstellt am {escape(generated)}</p>'
        f'<table width="100%" cellspacing="6"><tr>{metric_cells}</tr></table>'
        '<p><img src="chart:current" width="960" height="235"></p>'
        f'<p>{escape(analysis.note)}</p><h2>{escape(analysis.table_title)} · {len(analysis.details)} Tickets</h2>'
        f'<table width="100%" cellspacing="0" cellpadding="5" border="0"><thead><tr>{headers}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )
    writer = None
    painter = QPainter()
    try:
        writer = QPdfWriter(str(temporary))
        writer.setResolution(96)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        writer.setPageMargins(QMarginsF(12, 12, 12, 12))
        writer.setTitle(KPI_TITLES[analysis.kpi])
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
