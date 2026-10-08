"""Existing Qt PDF renderer isolated from the WebView host's event loop."""
import os
from pathlib import Path
import pickle
import sys


def main(request):
    from PySide6.QtWidgets import QApplication
    from matplotlib.figure import Figure
    from ..charts import draw_chart
    from ..pdf_export import export_management_pdf, export_pdf
    from ..reports import ManagementReport
    from ..storage import period_label
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    # This private file is created by this process; it never comes from JS or Znuny.
    with Path(request).open("rb") as stream:
        path, report = pickle.load(stream)
    if isinstance(report, ManagementReport):
        export_management_pdf(path, report)
    else:
        figure = Figure(figsize=(10, 3), dpi=100)
        draw_chart(figure, report.analysis)
        export_pdf(path, report.analysis, period_label(report.record), figure, report)
    app.quit()


if __name__ == "__main__":
    main(sys.argv[1])
