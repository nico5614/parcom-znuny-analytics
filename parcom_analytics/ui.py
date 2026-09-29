"""The four-page native Qt desktop interface."""

import logging
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLayout, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QTableView, QVBoxLayout, QWidget,
)

from . import APP_NAME, VERSION
from .analytics import Analysis, DataError, KPI_DESCRIPTIONS, KPI_TITLES, analyze, format_value
from .charts import draw_chart
from .pdf_export import export_pdf
from .storage import ImportResult, LocalStore, MONTHLY_KPIS, month_label, period_label, read_workbook

LOGGER = logging.getLogger(__name__)
ASSETS = Path(__file__).resolve().parent.parent / "assets"
STYLE = """
QWidget { color: #29343e; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QWidget#shell, QWidget#page { background: #f2f4f6; }
QFrame#header { background: white; border-bottom: 1px solid #e0e5e9; }
QFrame#card { background: white; border: 1px solid #e0e5e9; border-radius: 12px; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 18px; font-weight: 600; }
QLabel#title { font-size: 25px; font-weight: 600; }
QLabel#section { font-size: 14px; font-weight: 600; }
QLabel#muted { color: #65727d; }
QLabel#eyebrow { color: #a95518; font-size: 11px; font-weight: 600; }
QLabel#metric { color: #285c63; font-size: 26px; font-weight: 600; }
QLabel#warning { background: #fff3e8; color: #86480f; border-radius: 6px; padding: 8px; }
QPushButton { background: #e87926; color: white; border: none; border-radius: 7px;
              padding: 11px 18px; font-weight: 600; }
QPushButton:hover { background: #d4681c; }
QPushButton:focus { border: 2px solid #285c63; }
QPushButton:disabled { background: #e4e8eb; color: #8a959e; }
QPushButton#nav { background: transparent; color: #65727d; padding: 10px 18px; }
QPushButton#nav:hover { background: #f5f6f7; }
QPushButton#nav:checked { background: #fff0e3; color: #ae5615; }
QComboBox { background: white; border: 1px solid #d4dce2; border-radius: 7px; padding: 10px; }
QComboBox:focus { border: 1px solid #e87926; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: url(__ARROW__); width: 12px; height: 8px; }
QComboBox QAbstractItemView { background: white; color: #29343e; selection-background-color: #fff0e3;
                             selection-color: #29343e; padding: 4px; }
QTableView { background: white; alternate-background-color: #f7f9fa; border: none;
             gridline-color: #edf0f2; selection-background-color: #fff0e3; selection-color: #29343e; }
QHeaderView::section { background: #f4f6f8; color: #52616b; padding: 8px;
                       border: none; border-bottom: 1px solid #e4e8eb; font-weight: 600; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #f2f4f6; width: 10px; }
QScrollBar::handle:vertical { background: #cbd3d9; min-height: 25px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
""".replace("__ARROW__", (ASSETS / "chevron.svg").as_posix())


def label(text: str, role: str = "", wrap: bool = True) -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(role)
    widget.setWordWrap(wrap)
    return widget


class Card(QFrame):
    def __init__(self, watermark: bool = False):
        super().__init__()
        self.setObjectName("card")
        self.watermark = QPixmap(str(ASSETS / "parcom_logo.png")) if watermark else QPixmap()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.watermark.isNull():
            painter = QPainter(self)
            painter.setOpacity(0.035)
            image = self.watermark.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(self.width() - image.width() - 16, self.height() - image.height() - 16, image)


class FrameModel(QAbstractTableModel):
    def __init__(self, frame: pd.DataFrame):
        super().__init__()
        self.frame = frame.reset_index(drop=True)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return format_value(self.frame.iat[index.row(), index.column()])
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            field = str(self.frame.columns[section])
            return "Erstantwort fällig am" if field == "FirstResponseTimeDestinationDate" else field
        return None


def table_view() -> QTableView:
    table = QTableView()
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(33)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setWordWrap(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def set_table(table: QTableView, frame: pd.DataFrame) -> None:
    old_model = table.model()
    model = FrameModel(frame)
    model.setParent(table)
    table.setModel(model)
    if old_model:
        old_model.deleteLater()
    for index, field in enumerate(frame.columns):
        table.setColumnWidth(index, 280 if field in {"Titel", "Datei"} else 160)
    if "Titel" in frame.columns:
        table.horizontalHeader().setSectionResizeMode(list(frame.columns).index("Titel"), QHeaderView.ResizeMode.Stretch)


class ImportWorker(QThread):
    imported = Signal(object)

    def __init__(self, store: LocalStore, paths: list[Path], parent):
        super().__init__(parent)
        self.store, self.paths = store, paths

    def run(self):
        for path in self.paths:
            try:
                result = self.store.import_file(path)
            except Exception as error:
                LOGGER.error("Import storage failure: %s", type(error).__name__)
                result = ImportResult(path.name, "Import fehlgeschlagen – Speicherzugriff prüfen")
            self.imported.emit(result)


class MainWindow(QMainWindow):
    def __init__(self, store: LocalStore):
        super().__init__()
        self.store = store
        self.analysis: Analysis | None = None
        self.current_period = ""
        self.worker: ImportWorker | None = None
        self.import_rows: list[list[str]] = []
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(ASSETS / "parcom_logo.png")))
        self.resize(1280, 800)
        self.setMinimumSize(1050, 650)
        self.setStyleSheet(STYLE)
        shell = QWidget()
        shell.setObjectName("shell")
        self.setCentralWidget(shell)
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(78)
        head = QHBoxLayout(header)
        head.setContentsMargins(28, 12, 28, 12)
        icon = QLabel()
        icon.setFixedSize(42, 42)
        icon.setStyleSheet("background:#29343e;border-radius:8px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(QPixmap(str(ASSETS / "parcom_logo.png")).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                                                 Qt.TransformationMode.SmoothTransformation))
        head.addWidget(icon)
        head.addSpacing(6)
        head.addWidget(label(APP_NAME, "brand", False))
        head.addStretch()
        self.nav_buttons = []
        for index, name in enumerate(["Start", "Upload", "Dashboard", "Download"]):
            button = QPushButton(name)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, page=index: self.navigate(page))
            head.addWidget(button)
            self.nav_buttons.append(button)
        outer.addWidget(header)
        if self.store.warning:
            outer.addWidget(label(self.store.warning, "warning"))
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self._build_start()
        self._build_upload()
        self._build_dashboard()
        self._build_download()
        footer = QHBoxLayout()
        footer.setContentsMargins(28, 8, 28, 12)
        footer.addWidget(label("●  Lokale Datenverarbeitung", "muted", False))
        footer.addStretch()
        footer.addWidget(label(f"ParCom Systems AG  ·  Version {VERSION}", "muted", False))
        outer.addLayout(footer)
        self.refresh_dashboard()
        self.navigate(0)

    def _compact_page(self, watermark=False) -> QVBoxLayout:
        page = QWidget()
        page.setObjectName("page")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 18)
        card = Card(watermark)
        card.setMaximumWidth(700)
        card.setMinimumWidth(550)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content = QVBoxLayout(card)
        content.setContentsMargins(32, 26, 32, 26)
        content.setSpacing(14)
        layout.addStretch()
        layout.addWidget(card, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)
        return content

    def _build_start(self):
        layout = self._compact_page(watermark=True)
        layout.addWidget(label("SERVICE-KPIS · PBX", "eyebrow"))
        layout.addWidget(label(APP_NAME, "title"))
        layout.addWidget(label("Auswertung und Visualisierung von Service-KPIs aus Znuny.", "muted"))
        sections = [
            ("Über die Anwendung", "ParCom Znuny Analytics dient zur strukturierten Auswertung von KPI-Exporten aus Znuny. Die Anwendung verarbeitet lokal gespeicherte Excel-Dateien und stellt die Ergebnisse übersichtlich im Dashboard dar."),
            ("So funktioniert es", "1. Znuny-Excel-Dateien unter «Upload» importieren.\n2. KPI und Zeitraum im «Dashboard» auswählen.\n3. Die aktuelle Auswertung unter «Download» als PDF exportieren."),
            ("Datenschutz", "Alle importierten Daten werden ausschliesslich lokal auf diesem Computer verarbeitet. Es erfolgt keine Übertragung an externe Dienste."),
            ("Entwicklung", "Entwickelt von Nico Köchli für ParCom Systems AG."),
        ]
        for heading, text in sections:
            layout.addWidget(label(heading, "section"))
            layout.addWidget(label(text, "muted"))
        layout.addWidget(label(f"Version {VERSION}", "muted"))

    def _build_upload(self):
        layout = self._compact_page()
        layout.addWidget(label("LOKALE EXCEL-EXPORTE", "eyebrow"))
        layout.addWidget(label("Daten importieren", "title"))
        layout.addWidget(label("Wählen Sie einen oder mehrere Znuny-Exporte (.xlsx). KPI und Datenstand werden automatisch aus dem Dateinamen erkannt.", "muted"))
        self.upload_button = QPushButton("Excel-Dateien auswählen")
        self.upload_button.clicked.connect(self.choose_files)
        layout.addWidget(self.upload_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.upload_summary = label("Die Dateien werden dauerhaft auf diesem Computer gespeichert.", "muted")
        layout.addWidget(self.upload_summary)
        self.upload_table = table_view()
        self.upload_table.setMinimumHeight(190)
        self.upload_table.setMaximumHeight(260)
        layout.addWidget(self.upload_table)
        self._refresh_import_table()

    def _build_dashboard(self):
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 8)
        layout.setSpacing(12)
        controls = QHBoxLayout()
        controls.addWidget(label("Dashboard", "title"))
        controls.addStretch()
        self.kpi_combo = QComboBox()
        self.kpi_combo.setAccessibleName("KPI auswählen")
        self.kpi_combo.setMinimumWidth(445)
        self.kpi_combo.addItem("KPI auswählen...", None)
        for kpi, title in KPI_TITLES.items():
            self.kpi_combo.addItem(title, kpi)
        controls.addWidget(self.kpi_combo)
        self.month_combo = QComboBox()
        self.month_combo.setAccessibleName("Berichtsmonat")
        self.month_combo.setMinimumWidth(170)
        controls.addWidget(self.month_combo)
        layout.addLayout(controls)
        self.dashboard_stack = QStackedWidget()
        layout.addWidget(self.dashboard_stack, 1)
        empty = Card()
        empty_layout = QVBoxLayout(empty)
        empty_layout.addStretch()
        self.empty_title = label("", "title")
        self.empty_body = label("", "muted")
        for widget in [self.empty_title, self.empty_body]:
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(widget)
        empty_layout.addStretch()
        self.dashboard_stack.addWidget(empty)
        content = QWidget()
        content.setObjectName("page")
        content_layout = QVBoxLayout(content)
        content_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        self.dashboard_title = label("", "section")
        self.description = label("", "muted")
        self.period = label("", "eyebrow")
        content_layout.addWidget(self.dashboard_title)
        content_layout.addWidget(self.description)
        content_layout.addWidget(self.period)
        self.metrics_layout = QHBoxLayout()
        self.metrics_layout.setSpacing(10)
        content_layout.addLayout(self.metrics_layout)
        chart_card = Card()
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(8, 0, 8, 0)
        self.figure = Figure(figsize=(10, 2.5), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(190)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart_layout.addWidget(self.canvas)
        content_layout.addWidget(chart_card, 3)
        self.data_note = label("", "muted")
        content_layout.addWidget(self.data_note)
        table_card = Card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 12, 14, 8)
        self.table_title = label("", "section")
        table_layout.addWidget(self.table_title)
        self.detail_table = table_view()
        self.detail_table.setMinimumHeight(115)
        table_layout.addWidget(self.detail_table, 1)
        content_layout.addWidget(table_card, 2)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.dashboard_stack.addWidget(scroll)
        self.stack.addWidget(page)
        self.kpi_combo.currentIndexChanged.connect(self.kpi_changed)
        self.month_combo.currentIndexChanged.connect(self.refresh_dashboard)

    def _build_download(self):
        layout = self._compact_page()
        layout.addWidget(label("PDF-BERICHT", "eyebrow"))
        layout.addWidget(label("Auswertung exportieren", "title"))
        layout.addWidget(label("Exportieren Sie die aktuelle Dashboard-Ansicht mit Kennzahlen, Diagramm und vollständiger Detailtabelle.", "muted"))
        layout.addSpacing(8)
        layout.addWidget(label("Aktuelle KPI", "section"))
        self.download_kpi = label("–", "muted")
        layout.addWidget(self.download_kpi)
        layout.addWidget(label("Zeitraum / Datenstand", "section"))
        self.download_period = label("–", "muted")
        layout.addWidget(self.download_period)
        self.download_note = label("", "muted")
        layout.addWidget(self.download_note)
        self.pdf_button = QPushButton("Als PDF exportieren")
        self.pdf_button.clicked.connect(self.save_pdf)
        layout.addWidget(self.pdf_button, 0, Qt.AlignmentFlag.AlignLeft)

    def navigate(self, index: int):
        self.stack.setCurrentIndex(index)
        for position, button in enumerate(self.nav_buttons):
            button.setChecked(position == index)

    def choose_files(self):
        filenames, _ = QFileDialog.getOpenFileNames(self, "Znuny-Excel-Dateien auswählen", "", "Excel-Dateien (*.xlsx)")
        if filenames:
            self.import_files([Path(filename) for filename in filenames])

    def import_files(self, paths: list[Path]):
        if self.worker is not None:
            return
        self.import_rows = []
        self._refresh_import_table()
        self.upload_button.setEnabled(False)
        self.upload_summary.setText(f"{len(paths)} Dateien werden geprüft und importiert …")
        self.worker = ImportWorker(self.store, paths, self)
        self.worker.imported.connect(self._import_completed)
        self.worker.finished.connect(self._imports_finished)
        self.worker.start()

    def _import_completed(self, result: ImportResult):
        metadata = result.metadata
        self.import_rows.append([result.filename, f"KPI {metadata.kpi_number}" if metadata else "–",
                                 period_label(metadata) if metadata else "–", result.status])
        self._refresh_import_table()

    def _refresh_import_table(self):
        frame = pd.DataFrame(self.import_rows, columns=["Datei", "KPI", "Datenstand / Zeitraum", "Status"])
        set_table(self.upload_table, frame)
        self.upload_table.setColumnWidth(0, 175)
        self.upload_table.setColumnWidth(1, 65)
        self.upload_table.setColumnWidth(2, 175)
        self.upload_table.setColumnWidth(3, 175)

    def _imports_finished(self):
        worker = self.worker
        self.worker = None
        if worker:
            worker.deleteLater()
        self.upload_button.setEnabled(True)
        imported = sum(row[3] == "Importiert" for row in self.import_rows)
        duplicates = sum(row[3] == "Bereits importiert" for row in self.import_rows)
        errors = len(self.import_rows) - imported - duplicates
        self.upload_summary.setText(f"{imported} importiert · {duplicates} bereits vorhanden · {errors} nicht importiert")
        self.kpi_changed()

    def kpi_changed(self):
        kpi = self.kpi_combo.currentData()
        previous = self.month_combo.currentData()
        self.month_combo.blockSignals(True)
        self.month_combo.clear()
        for month in self.store.months(kpi):
            self.month_combo.addItem(month_label(month), month)
        existing = self.month_combo.findData(previous)
        if existing >= 0:
            self.month_combo.setCurrentIndex(existing)
        self.month_combo.blockSignals(False)
        self.month_combo.setVisible(kpi in MONTHLY_KPIS)
        self.refresh_dashboard()

    def _empty(self, title: str, body: str = ""):
        self.empty_title.setText(title)
        self.empty_body.setText(body)
        self.dashboard_stack.setCurrentIndex(0)

    def refresh_dashboard(self):
        self.analysis = None
        self.current_period = ""
        kpi = self.kpi_combo.currentData()
        self.month_combo.setVisible(kpi in MONTHLY_KPIS)
        if not self.store.records:
            self._empty("Keine Dateien hochgeladen", "Importieren Sie zuerst Znuny-Excel-Dateien unter «Upload».")
        elif not kpi:
            self._empty("Keine KPI ausgewählt", "Wählen Sie oben eine KPI aus, um die Auswertung anzuzeigen.")
        elif not any(record.kpi_number == kpi for record in self.store.records):
            self._empty("Keine Datei für diese KPI vorhanden.")
        else:
            record = self.store.latest(kpi, self.month_combo.currentData())
            if record is None:
                self._empty("Für den ausgewählten Monat ist keine Datei vorhanden.")
            else:
                try:
                    analysis = analyze(kpi, read_workbook(self.store.root / record.stored_path))
                    self._render_analysis(analysis, period_label(record))
                except DataError as error:
                    LOGGER.warning("KPI %s: required columns or values missing", kpi)
                    self._empty("Auswertung nicht möglich", str(error))
                except Exception as error:
                    LOGGER.error("Dashboard KPI %s failed: %s", kpi, type(error).__name__)
                    self._empty("Auswertung nicht möglich", "Die gespeicherte Excel-Datei konnte nicht ausgewertet werden. Bitte importieren Sie die Datei erneut.")
        self._refresh_download()

    def _render_analysis(self, analysis: Analysis, period: str):
        self.dashboard_title.setText(KPI_TITLES[analysis.kpi])
        self.description.setText(KPI_DESCRIPTIONS[analysis.kpi])
        self.period.setText(period)
        while self.metrics_layout.count():
            previous_card = self.metrics_layout.takeAt(0).widget()
            previous_card.hide()
            previous_card.deleteLater()
        for heading, value in analysis.metrics.items():
            card = Card()
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 12, 16, 12)
            box.addWidget(label(heading, "muted"))
            box.addWidget(label(format_value(value), "metric"))
            self.metrics_layout.addWidget(card, 1)
        draw_chart(self.figure, analysis)
        self.canvas.draw()
        self.data_note.setText(analysis.note)
        self.data_note.setVisible(bool(analysis.note))
        self.table_title.setText(f"{analysis.table_title} · {len(analysis.details)} Tickets")
        set_table(self.detail_table, analysis.details)
        self.dashboard_stack.setCurrentIndex(1)
        self.analysis, self.current_period = analysis, period

    def _refresh_download(self):
        self.pdf_button.setEnabled(self.analysis is not None)
        self.download_kpi.setText(KPI_TITLES[self.analysis.kpi] if self.analysis else "–")
        self.download_period.setText(self.current_period or "–")
        self.download_note.setText("Die zur Ansicht gehörende Tabelle wird vollständig und bei Bedarf auf mehreren Seiten exportiert."
                                   if self.analysis else "Es ist keine auswertbare Dashboard-Ansicht vorhanden.")

    def save_pdf(self):
        if self.analysis is None:
            return
        default = self.store.root / "exports" / f"ParCom_KPI_{self.analysis.kpi}.pdf"
        filename, _ = QFileDialog.getSaveFileName(self, "Auswertung als PDF speichern", str(default), "PDF-Dateien (*.pdf)")
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")
        try:
            export_pdf(path, self.analysis, self.current_period, self.figure)
            LOGGER.info("PDF exported for KPI %s", self.analysis.kpi)
            QMessageBox.information(self, "PDF exportiert", "Die Auswertung wurde erfolgreich als PDF gespeichert.")
        except Exception as error:
            LOGGER.error("PDF export failed: %s", type(error).__name__)
            QMessageBox.warning(self, "PDF-Export fehlgeschlagen", "Die PDF-Datei konnte nicht gespeichert werden. Prüfen Sie den Speicherort und schliessen Sie eine eventuell geöffnete PDF-Datei.")

    def closeEvent(self, event):
        if self.worker is not None:
            QMessageBox.information(self, "Import läuft", "Bitte warten Sie, bis der Dateiimport abgeschlossen ist.")
            event.ignore()
        else:
            event.accept()
