"""The native Qt desktop interface."""

import logging
import re
from datetime import datetime
from dataclasses import replace
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, QSettings, Qt, QThread, QTimer, Signal, QUrl
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLayout, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QTableView, QVBoxLayout, QWidget, QLineEdit, QDateEdit, QProgressBar, QCheckBox,
)

from . import APP_NAME, DISPLAY_VERSION, PUBLISHER
from .analytics import Analysis, analyze, DataError, KPI_DESCRIPTIONS, KPI_TITLES, detail_value, field_label, metric_items
from .charts import draw_chart, draw_history
from .pdf_export import export_management_pdf, export_pdf
from .reports import (KpiReport, ManagementReport, available_records, comparison_label, comparison_rows,
                      default_report_filename, load_management_report, load_report)
from .storage import ImportResult, LocalStore, MONTHLY_KPIS, month_label, period_label
from .connection import ConnectionController
from .live_cache import LiveCache
from .live_data import DateRange
from .timeline import Timeline
from .animations import Animator
from .analytics import format_duration, format_value

LOGGER = logging.getLogger(__name__)
from .theme import ASSETS, APP_LOGO, APP_ICON, STYLE, DARK_ROW_COLORS, dark_figure



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
        self.watermark = QPixmap(str(APP_LOGO)) if watermark else QPixmap()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.watermark.isNull():
            painter = QPainter(self)
            painter.setOpacity(0.08)
            image = self.watermark.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(self.width() - image.width() - 16, self.height() - image.height() - 16, image)


class FrameModel(QAbstractTableModel):
    def __init__(self, frame: pd.DataFrame, analysis: Analysis | None = None):
        super().__init__()
        self.frame = frame.reset_index(drop=True)
        self.analysis = analysis

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        column = str(self.frame.columns[index.column()])
        value = self.frame.iat[index.row(), index.column()]
        if role == Qt.ItemDataRole.ToolTipRole and column == "Ticket#":
            return "Ticket in Znuny öffnen" if self.frame.attrs.get("ticket_ids") else "Klicken, um die Ticketnummer zu kopieren"
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return detail_value(column, value)
        if role == Qt.ItemDataRole.ForegroundRole and column == "Ticket#":
            return QColor("#8dc9cb")
        if role == Qt.ItemDataRole.FontRole:
            font = QFont()
            font.setUnderline(column == "Ticket#")
            font.setBold(bool(self.analysis and index.row() in self.analysis.maximum_rows))
            return font
        if role == Qt.ItemDataRole.BackgroundRole and self.analysis and self.analysis.row_highlights:
            color = DARK_ROW_COLORS.get(self.analysis.row_highlights[index.row()])
            return QColor(color) if color else None
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            field = str(self.frame.columns[section])
            return field_label(field)
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


def open_ticket(model, index):
    if not index.isValid() or model.frame.columns[index.column()] != "Ticket#":
        return False
    ticket_id = model.frame.attrs.get("ticket_ids", {}).get(str(model.frame.iloc[index.row()]["Ticket#"]))
    if ticket_id and re.fullmatch(r"\d+", str(ticket_id)):
        return QDesktopServices.openUrl(QUrl("https://znuny.parcom.ch/otrs/index.pl?Action=AgentTicketZoom;TicketID="+str(ticket_id)))
    return False


def set_table(table: QTableView, frame: pd.DataFrame, analysis: Analysis | None = None) -> None:
    old_model = table.model()
    model = FrameModel(frame, analysis)
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
    def __init__(self, store: LocalStore, require_login=False):
        super().__init__()
        self.store = store
        self.production = require_login
        self.settings = QSettings(str(store.root / "settings.ini"), QSettings.Format.IniFormat)
        self.animator = Animator(self, reduced=bool(QApplication.instance().property("reduce_motion")) or
                                self.settings.value("reduce_motion", False, type=bool))
        self.previous_metrics = {}
        self.live_cache = LiveCache(store.root)
        self.live_reports = self.live_cache.reports()
        self.connection = ConnectionController(self, cache=self.live_cache)
        self.closing = False
        self.logout_complete = False
        self.offline_after_logout = False
        self.refresh_after_login = False
        self.analysis: Analysis | None = None
        self.current_report: KpiReport | None = None
        self.download_report: KpiReport | ManagementReport | None = None
        self.current_period = ""
        self.worker: ImportWorker | None = None
        self.import_rows: list[list[str]] = []
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.resize(1280, 800)
        self.setMinimumSize(1050, 650)
        self.setStyleSheet(STYLE)
        shell = QWidget()
        shell.setObjectName("shell")
        self.setCentralWidget(shell)
        horizontal = QHBoxLayout(shell)
        horizontal.setContentsMargins(0, 0, 0, 0)
        horizontal.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(216)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 24, 14, 20)
        side.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(QPixmap(str(APP_LOGO)).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation))
        side.addWidget(icon)
        side.addWidget(label("ParCom\nZnuny Analytics", "brand"))
        side.addWidget(label("SERVICE-ANALYSE", "eyebrow"))
        side.addSpacing(28)
        self.nav_buttons = []
        for index, name in enumerate(["Info", "Import", "Analysen", "Übersicht", "Export", "Agenten"]):
            button = QPushButton(name)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, page=index: self.navigate(page))
            self.nav_buttons.append(button)
        for index in (3, 2, 5, 4):
            side.addWidget(self.nav_buttons[index])
        side.addStretch()
        side.addWidget(self.nav_buttons[0])
        self.logout_button = QPushButton("Logout")
        self.logout_button.setObjectName("secondary")
        self.logout_button.clicked.connect(self.logout)
        side.addWidget(self.logout_button)
        horizontal.addWidget(sidebar)
        workspace = QWidget()
        outer = QVBoxLayout(workspace)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        horizontal.addWidget(workspace, 1)
        self._build_connection_controls(outer)
        if self.store.warning:
            outer.addWidget(label(self.store.warning, "warning"))
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self._build_start()
        self._build_upload()
        self._build_dashboard()
        from .service_desk_ui import ServiceDeskPage
        self.service_desk = ServiceDeskPage(store)
        self.service_desk.animator = self.animator
        self.stack.addWidget(self.service_desk)
        self._build_download()
        from .agents_ui import AgentsPage
        self.agent_page = AgentsPage(self.live_cache, self.settings)
        self.stack.addWidget(self.agent_page)
        footer = QHBoxLayout()
        footer.setContentsMargins(28, 8, 28, 12)
        self.connection_status = label("", "muted", False)
        footer.addWidget(self.connection_status)
        footer.addStretch()
        footer.addWidget(label(f"Version {DISPLAY_VERSION}", "muted", False))
        outer.addLayout(footer)
        self.refresh_dashboard()
        if require_login:
            self.source_combo.setCurrentIndex(1)
        self.navigate(3 if require_login else 0)
        self._build_login(shell, require_login)
        self.connection.stateChanged.connect(self._connection_state)
        self.connection.loggedIn.connect(self._login_succeeded)
        self.connection.loggedOut.connect(self._logged_out)
        self.connection.loaded.connect(self._live_loaded)
        self.connection.failed.connect(self._network_error)
        self.connection.busyChanged.connect(self._network_busy)

        self._connection_state("offline")

    @property
    def is_live(self):
        return self.source_combo.currentData() == "live"

    def _build_connection_controls(self, outer):
        controls = QHBoxLayout()
        controls.setContentsMargins(24, 12, 24, 0)
        self.source_combo = QComboBox()
        self.source_combo.addItem("Lokale Excel-Daten", "excel")
        self.source_combo.addItem("Znuny Live / letzter Datenstand", "live")
        self.source_combo.hide()
        self.range_combo = QComboBox()
        for text, value in [("1 Woche", "7d"), ("1 Monat", "30d"), ("3 Monate", "3m"), ("6 Monate", "6m"), ("1 Jahr", "12m"), ("Benutzerdefiniert", "custom")]:
            self.range_combo.addItem(text, value)
        self.range_combo.hide()
        self.from_date, self.to_date = QDateEdit(), QDateEdit()
        self.from_date.hide()
        self.to_date.hide()
        heading = QVBoxLayout()
        heading.addWidget(label("Service Desk", "title"))
        heading.addWidget(label("PBX · Znuny Analytics", "muted"))
        heading.addStretch()
        controls.addLayout(heading, 1)
        self.timeline = Timeline()
        self.timeline.setMaximumWidth(700)
        self.timeline.changed.connect(self.refresh_live)
        controls.addWidget(self.timeline, 3)
        actions = QVBoxLayout()
        self.refresh_button = QPushButton("↻ Aktualisieren")
        self.refresh_button.clicked.connect(self.refresh_live)
        self.connect_button = QPushButton("Verbinden")
        self.connect_button.setObjectName("secondary")
        self.connect_button.clicked.connect(self.show_login)
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.connect_button)
        controls.addLayout(actions)
        outer.addLayout(controls)
        self.loading = QProgressBar()
        self.loading.setRange(0, 0)
        self.loading.setFormat("Znuny-Daten werden geladen …")
        self.loading.hide()
        outer.addWidget(self.loading)
        self.network_note = label(self.live_cache.warning, "warning")
        self.network_note.setVisible(bool(self.live_cache.warning))
        outer.addWidget(self.network_note)
        self.source_combo.currentIndexChanged.connect(self._source_changed)

    def _build_login(self, shell, required):
        self.takeCentralWidget()
        self.gate = QStackedWidget()
        self.gate.addWidget(shell)
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.addStretch()
        card = Card()
        card.setMaximumWidth(480)
        form = QVBoxLayout(card)
        form.setContentsMargins(40, 36, 40, 36)
        form.setSpacing(16)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(APP_LOGO)).scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation))
        form.addWidget(logo)
        form.addWidget(label(APP_NAME, "brand"))
        form.addWidget(label("Mit Znuny verbinden", "title"))
        form.addWidget(label("Ihr persönlicher Zugang zum Service Desk.", "muted"))
        form.addWidget(label("Benutzername", "section"))
        self.username = QLineEdit()
        self.username.setAccessibleName("Benutzername")
        form.addWidget(self.username)
        form.addWidget(label("Passwort", "section"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setAccessibleName("Passwort")
        self.password.returnPressed.connect(self.login)
        form.addWidget(self.password)
        self.login_error = label("", "warning")
        self.login_error.hide()
        form.addWidget(self.login_error)
        self.login_button = QPushButton("Anmelden")
        self.login_button.clicked.connect(self.login)
        form.addWidget(self.login_button)
        form.addWidget(label("Znuny Server\nznuny.parcom.ch", "muted"))
        self.offline_button = QPushButton("Offline mit lokalen Daten fortfahren")
        self.offline_button.setObjectName("secondary")
        self.offline_button.clicked.connect(self.enter_offline)
        form.addWidget(self.offline_button)
        form.addWidget(label("Passwort und Sitzung werden nicht gespeichert.", "muted"))
        layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        login_footer = QHBoxLayout()
        self.login_status = label("", "muted")
        login_footer.addWidget(self.login_status)
        login_footer.addStretch()
        login_footer.addWidget(label(f"Version {DISPLAY_VERSION}", "muted"))
        layout.addLayout(login_footer)
        self.gate.addWidget(page)
        self.setCentralWidget(self.gate)
        self.gate.setCurrentIndex(1 if required else 0)

    def show_login(self):
        self.password.clear()
        self.login_error.hide()
        self.gate.setCurrentIndex(1)
        self.username.setFocus()

    def enter_offline(self):
        self.password.clear()
        self.username.clear()
        if self.connection.client._session_id or self.connection.worker:
            self.offline_after_logout = True
            self.logout()
            return
        self.gate.setCurrentIndex(0)
        self.navigate(3)

    def login(self):
        if self.connection.worker:
            return
        if not self.username.text().strip() or not self.password.text():
            self.login_error.setText("Bitte Benutzername und Passwort eingeben.")
            self.login_error.show()
            return
        password = self.password.text()
        self.password.clear()
        self.connection.login(self.username.text().strip(), password)
        password = None

    def _login_succeeded(self):
        self.logout_complete = False
        self.username.clear()
        self.login_error.hide()
        self.network_note.hide()
        self.gate.setCurrentIndex(0)
        self.animator.fade(self.gate.currentWidget())
        self.source_combo.setCurrentIndex(1)
        self.navigate(3)
        self.refresh_after_login = True

    def _connection_state(self, state):
        text, color = {"online": ("Verbunden mit Znuny", "#59bd8b"),
                       "connecting": ("Verbindung wird hergestellt …", "#d4b15f"),
                       "offline": ("Keine Verbindung zu Znuny – nur lokale Daten verfügbar", "#e08181")}[state]
        self.connection_status.setText("●  " + text)
        self.connection_status.setStyleSheet(f"color: {color};")
        if hasattr(self, "login_status"):
            self.login_status.setText("●  " + text)
            self.login_status.setStyleSheet(f"color: {color};")
        self.refresh_button.setEnabled(state == "online" and self.connection.worker is None and self.is_live)
        self.connect_button.setText("Neu verbinden" if state == "online" else "Verbinden")

    def _network_busy(self, busy):
        self.loading.setVisible(busy)
        self.login_button.setEnabled(not busy)
        self.login_button.setText("Anmeldung läuft …" if busy and self.gate.currentIndex() == 1 else "Anmelden")
        self.offline_button.setEnabled(not busy)
        self.connect_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy and self.connection.state == "online" and self.is_live)
        if not busy:
            if self.closing and self.logout_complete:
                QTimer.singleShot(0, self.close)
            elif self.refresh_after_login:
                self.refresh_after_login = False
                QTimer.singleShot(0, self.refresh_live)

    def _network_error(self, message):
        self.login_error.setText(message)
        self.login_error.show()
        self.network_note.setText(message + " Der letzte lokale Datenstand bleibt verfügbar.")
        self.network_note.show()

    def _range_changed(self):
        custom = self.is_live and self.range_combo.currentData() == "custom"
        self.from_date.setVisible(custom)
        self.to_date.setVisible(custom)

    def _source_changed(self):
        self.timeline.setVisible(self.is_live)
        self.refresh_button.setVisible(self.is_live)
        self._connection_state(self.connection.state)
        self.service_desk.live_cache = self.live_cache if self.is_live else None
        self.kpi_changed()
        self.refresh_download_choices()
        self.service_desk.refresh()

    def refresh_live(self):
        if self.connection.worker or self.connection.state != "online":
            return
        try:
            period = self.timeline.period()
            self.timeline.sync_controls()
        except DataError as error:
            self._network_error(str(error))
            return
        self.network_note.hide()
        self.connection.refresh(period)

    def _live_loaded(self, reports):
        self.live_reports = reports
        self.agent_page.refresh()
        self.kpi_changed()
        self.refresh_download_choices()
        self.service_desk.refresh()

    def logout(self):
        self.refresh_after_login = False
        self.password.clear()
        self.connection.logout()

    def _logged_out(self):
        self.logout_complete = True
        if not self.closing:
            if self.offline_after_logout:
                self.offline_after_logout = False
                self.gate.setCurrentIndex(0)
                self.navigate(3)
            else:
                self.show_login()

    def _compact_page(self, watermark=False, maximum_width=700) -> QVBoxLayout:
        page = QWidget()
        page.setObjectName("page")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 18)
        card = Card(watermark)
        card.setMaximumWidth(maximum_width)
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
            ("Über die Anwendung", "Analytics- und Reporting-Anwendung für Znuny. Live-Kennzahlen und lokale Excel-Daten für den Service Desk."),
            ("So funktioniert es", "1. Mit Znuny verbinden oder offline fortfahren.\n2. Datenquelle, KPI und Zeitraum auswählen.\n3. Unter «Berichte» die gewünschte Auswertung als PDF exportieren."),
            ("Datenschutz", "Daten werden lokal ausgewertet. Nur die Anmeldung und lesende Datenabfragen kommunizieren per HTTPS mit Znuny. Passwort und Sitzung werden nicht gespeichert."),
            ("Entwicklung", f"Entwickelt von {PUBLISHER}\nfür ParCom Systems AG\n\nHerausgeber: {PUBLISHER}"),
        ]
        for heading, text in sections:
            layout.addWidget(label(heading, "section"))
            layout.addWidget(label(text, "muted"))
        layout.addWidget(label(f"Version {DISPLAY_VERSION}", "muted"))
        self.reduce_motion = QCheckBox("Animationen reduzieren")
        self.reduce_motion.setChecked(self.animator.reduced)
        self.reduce_motion.toggled.connect(self._motion_changed)
        layout.addWidget(self.reduce_motion)

    def _motion_changed(self, checked):
        self.animator.finish_all()
        self.animator.reduced = checked
        self.settings.setValue("reduce_motion", checked)

    def _build_upload(self):
        layout = self._compact_page(maximum_width=1200)
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
        self.dataset_summary = label("", "eyebrow")
        layout.addWidget(self.dataset_summary)
        self.dataset_table = table_view()
        self.dataset_table.setMinimumHeight(200)
        self.dataset_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.dataset_table)
        self.delete_button = QPushButton("Ausgewählten Datensatz löschen")
        self.delete_button.setObjectName("secondary")
        self.delete_button.clicked.connect(self.delete_dataset)
        layout.addWidget(self.delete_button)
        self.clear_live_button = QPushButton("Lokalen Znuny-Datenstand und Live-Historie löschen")
        self.clear_live_button.setObjectName("secondary")
        self.clear_live_button.clicked.connect(self.clear_live_cache)
        layout.addWidget(self.clear_live_button)
        self.refresh_datasets()

    def refresh_datasets(self):
        self.dataset_records = sorted(self.store.records, key=lambda record: record.export_timestamp, reverse=True)
        rows = []
        for record in self.dataset_records:
            latest = self.store.latest(record.kpi_number, record.reporting_month)
            rows.append([f"KPI {record.kpi_number}", period_label(record), record.export_timestamp[:16].replace("T", " "),
                         "Ja" if record == latest else "", record.original_filename])
        set_table(self.dataset_table, pd.DataFrame(rows, columns=["KPI", "Zeitraum / Datenstand", "Exportzeit", "Neuester", "Datei"]))
        present = {record.kpi_number for record in self.store.records}
        self.dataset_summary.setText(f"Importierte KPIs: {len(present)} / 7 · " + ("Alle KPI-Daten vorhanden" if len(present) == 7 else
                                    "Fehlend: " + ", ".join(str(kpi) for kpi in range(1, 8) if kpi not in present)))
        self.delete_button.setEnabled(bool(rows) and self.worker is None)

    def delete_dataset(self):
        indexes = self.dataset_table.selectionModel().selectedRows()
        if not indexes or self.worker is not None:
            return
        record = self.dataset_records[indexes[0].row()]
        if QMessageBox.question(self, "Datensatz löschen", f"KPI {record.kpi_number} · {period_label(record)} löschen?\nNur die lokale Anwendungskopie wird entfernt; die Originaldatei bleibt erhalten.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete_record(record)
        except Exception as error:
            LOGGER.error("Dataset deletion failed: %s", type(error).__name__)
            QMessageBox.warning(self, "Löschen fehlgeschlagen", "Die lokale Datei konnte nicht entfernt werden.")
        self.refresh_datasets()
        self.kpi_changed()
        self.refresh_download_choices()
        self.service_desk.refresh()

    def clear_live_cache(self):
        if self.connection.worker:
            return
        if QMessageBox.question(self, "Znuny-Datenstand löschen", "Letzten lokalen Znuny-Datenstand und dessen aggregierte Historie löschen? Excel-Importe bleiben erhalten.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                self.live_cache.clear()
                self.live_reports = {}
                self._source_changed()
            except OSError:
                QMessageBox.warning(self, "Löschen fehlgeschlagen", "Der lokale Znuny-Datenstand konnte nicht entfernt werden.")

    def _build_dashboard(self):
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 8)
        layout.setSpacing(12)
        controls = QHBoxLayout()
        controls.addWidget(label("Analysen", "title"))
        controls.addStretch()
        self.kpi_combo = QComboBox()
        self.kpi_combo.setAccessibleName("KPI auswählen")
        self.kpi_combo.setMinimumWidth(270)
        self.kpi_combo.addItem("Analyse auswählen...", None)
        for kpi, title in KPI_TITLES.items():
            self.kpi_combo.addItem(title.split(" – ", 1)[-1], kpi)
        controls.addWidget(self.kpi_combo)
        self.month_combo = QComboBox()
        self.month_combo.setAccessibleName("Berichtsmonat")
        self.month_combo.setMinimumWidth(170)
        controls.addWidget(self.month_combo)
        self.snapshot_combo = QComboBox()
        self.snapshot_combo.setAccessibleName("Datenstand auswählen")
        self.snapshot_combo.setMinimumWidth(190)
        controls.addWidget(self.snapshot_combo)
        layout.addLayout(controls)
        filters = QHBoxLayout()
        filters.addWidget(label("Tickettyp", "muted", False))
        self.type_combo = QComboBox()
        self.type_combo.addItem("Alle Typen", None)
        self.type_combo.currentIndexChanged.connect(self.refresh_dashboard)
        filters.addWidget(self.type_combo)
        self.type_chart_button = QPushButton("Tickettypen anzeigen")
        self.type_chart_button.setObjectName("secondary")
        self.type_chart_button.setCheckable(True)
        self.type_chart_button.toggled.connect(self.refresh_dashboard)
        filters.addWidget(self.type_chart_button)
        filters.addStretch()
        layout.addLayout(filters)
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
        self.canvas.setMinimumHeight(260)
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
        self.highlight_note = label("", "muted")
        table_layout.addWidget(self.highlight_note)
        self.copy_note = label("", "eyebrow")
        self.copy_note.hide()
        table_layout.addWidget(self.copy_note)
        self.copy_timer = QTimer(self)
        self.copy_timer.setSingleShot(True)
        self.copy_timer.timeout.connect(self.copy_note.hide)
        self.detail_table = table_view()
        self.detail_table.setMinimumHeight(155)
        self.detail_table.clicked.connect(self.copy_ticket)
        table_layout.addWidget(self.detail_table, 1)
        content_layout.addWidget(table_card, 2)
        self.history_card = Card()
        history_layout = QVBoxLayout(self.history_card)
        history_layout.setContentsMargins(14, 12, 14, 12)
        history_layout.addWidget(label("Historische Entwicklung", "section"))
        self.history_note = label("", "muted")
        history_layout.addWidget(self.history_note)
        self.history_figure = Figure(figsize=(10, 2.3), dpi=100)
        self.history_canvas = FigureCanvasQTAgg(self.history_figure)
        self.history_canvas.setMinimumHeight(230)
        history_layout.addWidget(self.history_canvas)
        self.comparison_title = label("", "muted")
        history_layout.addWidget(self.comparison_title)
        self.comparison_table = table_view()
        self.comparison_table.setFixedHeight(105)
        history_layout.addWidget(self.comparison_table)
        content_layout.addWidget(self.history_card)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.dashboard_stack.addWidget(scroll)
        self.stack.addWidget(page)
        self.kpi_combo.currentIndexChanged.connect(self.kpi_changed)
        self.month_combo.currentIndexChanged.connect(self.refresh_dashboard)
        self.snapshot_combo.currentIndexChanged.connect(self.refresh_dashboard)

    def _build_download(self):
        layout = self._compact_page()
        layout.addWidget(label("PDF-BERICHT", "eyebrow"))
        layout.addWidget(label("Auswertung exportieren", "title"))
        layout.addWidget(label("Erstellen Sie einen PDF-Bericht aus den importierten Znuny-Daten.", "muted"))
        layout.addWidget(label("Auswertung", "section"))
        self.download_combo = QComboBox()
        self.download_combo.setAccessibleName("Auswertung für PDF auswählen")
        self.download_combo.addItem("Auswertung auswählen...", None)
        for kpi, title in KPI_TITLES.items():
            self.download_combo.addItem(title.split(" – ", 1)[-1].replace(" letzter Monat", ""), kpi)
        self.download_combo.addItem("Service Desk – Gesamtübersicht", "service_desk")
        layout.addWidget(self.download_combo)
        self.download_period_label = label("Berichtsmonat", "section")
        layout.addWidget(self.download_period_label)
        self.download_period_combo = QComboBox()
        self.download_period_combo.setAccessibleName("Berichtszeitraum für PDF auswählen")
        layout.addWidget(self.download_period_combo)
        self.download_basis = label("Aktuellste verfügbare KPI-Daten", "muted")
        layout.addWidget(self.download_basis)
        self.download_note = label("", "muted")
        layout.addWidget(self.download_note)
        self.pdf_button = QPushButton("Als PDF exportieren")
        self.pdf_button.clicked.connect(self.save_pdf)
        layout.addWidget(self.pdf_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.download_combo.currentIndexChanged.connect(self.refresh_download_choices)
        self.download_period_combo.currentIndexChanged.connect(self._refresh_download)
        self.refresh_download_choices()

    def navigate(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 3:
            self.service_desk.refresh()
        elif index == 4:
            self.refresh_download_choices()
        elif index == 5:
            self.agent_page.refresh()
        for position, button in enumerate(self.nav_buttons):
            button.setChecked(position == index)
        self.animator.fade(self.stack.currentWidget())

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
        self.delete_button.setEnabled(False)
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
        self.refresh_download_choices()
        self.refresh_datasets()
        if self.stack.currentIndex() == 3:
            self.service_desk.refresh()

    def kpi_changed(self):
        kpi = self.kpi_combo.currentData()
        previous_type = self.type_combo.currentData()
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        self.type_combo.addItem("Alle Typen", None)
        if self.is_live and self.live_cache.batch and kpi:
            for name in sorted(self.live_cache.batch.frames[kpi]["Typ"].dropna().astype(str).unique()):
                self.type_combo.addItem(name, name)
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(previous_type)))
        self.type_combo.blockSignals(False)
        self.type_combo.setVisible(self.is_live)
        self.type_chart_button.setVisible(self.is_live)
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
        self.snapshot_combo.blockSignals(True)
        previous_snapshot = self.snapshot_combo.currentData()
        self.snapshot_combo.clear()
        if kpi and kpi not in MONTHLY_KPIS:
            for record in available_records(self.store, kpi):
                self.snapshot_combo.addItem(period_label(record).removeprefix("Datenstand: "), record.stored_path)
        existing_snapshot = self.snapshot_combo.findData(previous_snapshot)
        if existing_snapshot >= 0:
            self.snapshot_combo.setCurrentIndex(existing_snapshot)
        self.snapshot_combo.blockSignals(False)
        self.refresh_dashboard()

    def _empty(self, title: str, body: str = ""):
        self.empty_title.setText(title)
        self.empty_body.setText(body)
        self.dashboard_stack.setCurrentIndex(0)

    def refresh_dashboard(self):
        self.analysis = None
        self.current_report = None
        self.current_period = ""
        kpi = self.kpi_combo.currentData()
        self.month_combo.setVisible(not self.is_live and kpi in MONTHLY_KPIS)
        self.snapshot_combo.setVisible(not self.is_live and bool(kpi and kpi not in MONTHLY_KPIS))
        if self.is_live:
            if not self.live_reports:
                self._empty("Noch kein Datenstand geladen", "Verbinden Sie sich mit Znuny und wählen Sie «Aktualisieren».")
            elif not kpi:
                self._empty("Keine KPI ausgewählt", "Wählen Sie oben eine KPI aus, um die Auswertung anzuzeigen.")
            else:
                report = self.selected_live_report(kpi)
                self._render_analysis(report.analysis, period_label(report.record), report)
                if self.type_chart_button.isChecked():
                    self.render_types(kpi)
            return
        if not self.store.records:
            self._empty("Keine Dateien hochgeladen", "Importieren Sie zuerst Znuny-Excel-Dateien unter «Import».")
        elif not kpi:
            self._empty("Keine KPI ausgewählt", "Wählen Sie oben eine KPI aus, um die Auswertung anzuzeigen.")
        elif not any(record.kpi_number == kpi for record in self.store.records):
            self._empty("Keine Datei für diese KPI vorhanden.")
        else:
            record = self.store.latest(kpi, self.month_combo.currentData()) if kpi in MONTHLY_KPIS else next(
                (item for item in available_records(self.store, kpi) if item.stored_path == self.snapshot_combo.currentData()), None)
            if record is None:
                self._empty("Für den ausgewählten Monat ist keine Datei vorhanden.")
            else:
                try:
                    report = load_report(self.store, record)
                    self._render_analysis(report.analysis, period_label(record), report)
                except DataError as error:
                    LOGGER.warning("KPI %s: required columns or values missing", kpi)
                    self._empty("Auswertung nicht möglich", str(error))
                except Exception as error:
                    LOGGER.error("Dashboard KPI %s failed: %s", kpi, type(error).__name__)
                    self._empty("Auswertung nicht möglich", "Die gespeicherte Excel-Datei konnte nicht ausgewertet werden. Bitte importieren Sie die Datei erneut.")

    def selected_live_report(self, kpi):
        from .live_metrics import analyze_live
        from .reports import HistoryPoint
        report = self.live_reports[kpi]
        selected = self.type_combo.currentData()
        if not selected:
            return report
        batch = self.live_cache.batch
        frame = batch.frames[kpi]
        analysis = analyze_live(kpi, frame.loc[frame["Typ"].eq(selected)], batch.period)
        history = [HistoryPoint(report.record, analysis)]
        if kpi in batch.previous:
            previous = batch.previous[kpi]
            history.insert(0, HistoryPoint(report.history[-2].record, analyze(kpi, previous.loc[previous["Typ"].eq(selected)])))
        return replace(report, analysis=analysis, history=history, comparable=len(history)>1,
                       history_note="Tickettyp: " + selected, source=report.source + " · Typ: " + selected)

    def render_types(self, kpi):
        frame = self.live_cache.batch.frames[kpi]
        selected = self.type_combo.currentData()
        if selected:
            frame = frame.loc[frame["Typ"].eq(selected)]
        counts = frame["Typ"].fillna("Typ unbekannt").value_counts().sort_index()
        self.animator.stop(self.canvas)
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        if len(counts):
            bars = axis.barh(counts.index, counts.values, color="#32D5FF")
            axis.bar_label(bars, padding=4, color="#F4F7FA")
            axis.spines[["top","right","left","bottom"]].set_visible(False)
            axis.margins(x=.2)
        else:
            axis.text(.5,.5,"Keine Tickets im Zeitraum",ha="center",transform=axis.transAxes)
        axis.set_title("Tickettypen · inklusive Unclassified", color="#F4F7FA", loc="left")
        self.figure.subplots_adjust(left=.20,right=.94,top=.85,bottom=.12)
        dark_figure(self.figure)
        self.canvas.draw()

    def _render_analysis(self, analysis: Analysis, period: str, report: KpiReport | None = None):
        self.animator.stop(self.canvas)
        self.animator.stop(self.history_canvas)
        self.dashboard_title.setText(KPI_TITLES[analysis.kpi].split(" – ", 1)[-1])
        self.description.setText(KPI_DESCRIPTIONS[analysis.kpi])
        self.period.setText(period)
        if report:
            self.period.setText(period + " · " + report.source)
            if self.is_live and analysis.kpi in MONTHLY_KPIS:
                stamp = datetime.fromisoformat(report.record.export_timestamp)
                self.period.setText(self.period.text() + f" · Datenstand: {stamp:%d.%m.%Y %H:%M} Uhr")
        while self.metrics_layout.count():
            previous_card = self.metrics_layout.takeAt(0).widget()
            previous_card.hide()
            previous_card.deleteLater()
        count_widgets = []
        for position, (heading, value) in enumerate(metric_items(analysis)):
            card = Card()
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 12, 16, 12)
            box.addWidget(label(heading, "muted"))
            metric_label = label(value, "metric")
            box.addWidget(metric_label)
            self.metrics_layout.addWidget(card, 1)
            raw_name = list(analysis.metrics)[position] if position < len(analysis.metrics) else None
            raw = analysis.metrics.get(raw_name)
            if isinstance(raw, (int, float)):
                key = (analysis.kpi, raw_name)
                formatter = format_duration if "(Min.)" in raw_name else (lambda number: format_value(round(number)))
                count_widgets.append((metric_label, self.previous_metrics.get(key, 0), raw, formatter))
                self.previous_metrics[key] = raw
        draw_chart(self.figure, analysis)
        dark_figure(self.figure)
        self.canvas.draw()
        self.data_note.setText(analysis.note)
        self.data_note.setVisible(bool(analysis.note))
        self.table_title.setText(f"{analysis.table_title} · {len(analysis.details)} Tickets")
        self.highlight_note.setText(analysis.highlight_note)
        self.highlight_note.setVisible(bool(analysis.highlight_note))
        self.copy_note.hide()
        set_table(self.detail_table, analysis.details, analysis)
        self.history_card.setVisible(report is not None)
        if report:
            draw_history(self.history_figure, report)
            dark_figure(self.history_figure)
            self.history_canvas.draw()
            self.history_note.setText(report.history_note)
            self.history_note.setVisible(bool(report.history_note))
            self.comparison_title.setText(comparison_label(report))
            set_table(self.comparison_table, comparison_rows(report))
            self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dashboard_stack.setCurrentIndex(1)
        for args in count_widgets:
            self.animator.count(*args)
        self.animator.chart(self.canvas)
        self.animator.chart(self.history_canvas)
        self.animator.fade(self.detail_table)
        self.analysis, self.current_period = analysis, period
        self.current_report = report

    def copy_ticket(self, index: QModelIndex):
        model = self.detail_table.model()
        if self.is_live:
            open_ticket(model,index)
            return
        if not index.isValid() or model.frame.columns[index.column()] != "Ticket#":
            return
        value = model.data(index)
        if value and value != "–":
            QApplication.clipboard().setText(value)
            self.copy_note.setText(f"Ticketnummer kopiert: {value}")
            self.copy_note.show()
            self.copy_timer.start(2500)

    def refresh_download_choices(self):
        kpi = self.download_combo.currentData()
        previous = self.download_period_combo.currentData()
        self.download_period_combo.blockSignals(True)
        self.download_period_combo.clear()
        if isinstance(kpi, int) and self.is_live and kpi in self.live_reports:
            self.download_period_combo.addItem(period_label(self.live_reports[kpi].record), "live")
        elif isinstance(kpi, int):
            for record in available_records(self.store, kpi):
                self.download_period_combo.addItem(period_label(record).removeprefix("Datenstand: "), record.stored_path)
        existing = self.download_period_combo.findData(previous)
        if existing >= 0:
            self.download_period_combo.setCurrentIndex(existing)
        self.download_period_combo.blockSignals(False)
        self.download_period_label.setText("Datenbasis" if kpi == "service_desk" else "Berichtsmonat" if kpi in MONTHLY_KPIS else "Datenstand")
        self.download_period_label.setVisible(kpi is not None)
        self.download_period_combo.setVisible(isinstance(kpi, int))
        self.download_basis.setVisible(kpi == "service_desk")
        self._refresh_download()

    def _refresh_download(self):
        self.download_report = None
        kpi = self.download_combo.currentData()
        note = "Wählen Sie eine Auswertung aus."
        try:
            if self.is_live:
                if kpi == "service_desk":
                    self.download_report = self.live_cache.management()
                elif isinstance(kpi, int):
                    self.download_report = self.live_reports.get(kpi)
                note = "Znuny-Datenstand · Bericht mit Kennzahlen, Diagrammen und Historie." if self.download_report else "Keine lokalen Znuny-Daten verfügbar."
            elif not self.store.records:
                note = "Keine Auswertungen verfügbar.\nImportieren Sie zuerst Znuny-Excel-Dateien unter «Import»."
            elif kpi == "service_desk":
                self.download_report = load_management_report(self.store)
                note = "PDF enthält:\n• Management-Kennzahlen\n• Performance Score, sofern verfügbar\n• Vergleichswerte und Trenddiagramme\n• Datenbasis\n\nAggregierter Bericht ohne Ticketdetails und Kundendaten."
            elif isinstance(kpi, int):
                record = next((item for item in available_records(self.store, kpi)
                               if item.stored_path == self.download_period_combo.currentData()), None)
                if record is None:
                    note = "Für diese KPI sind keine Daten vorhanden."
                else:
                    self.download_report = load_report(self.store, record)
                    note = "PDF enthält:\n• Zeitraum und Kennzahlen\n• Diagramm mit Referenzwerten\n• Historische Entwicklung und Vergleich\n• Vollständige Ticketdetails"
        except DataError as error:
            note = "Nicht verfügbar\n" + str(error)
        except Exception as error:
            LOGGER.error("Report selection failed: %s", type(error).__name__)
            note = "Die Auswertung konnte nicht geladen werden. Bitte prüfen Sie die lokal gespeicherten Dateien."
        self.download_note.setText(note)
        self.pdf_button.setEnabled(self.download_report is not None)

    def save_pdf(self):
        self._refresh_download()
        report = self.download_report
        if report is None:
            return
        default = self.store.root / "exports" / default_report_filename(report)
        filename, _ = QFileDialog.getSaveFileName(self, "Auswertung als PDF speichern", str(default), "PDF-Dateien (*.pdf)")
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")
        try:
            if isinstance(report, ManagementReport):
                export_management_pdf(path, report)
            else:
                figure = Figure(figsize=(10, 2.8), dpi=100)
                draw_chart(figure, report.analysis)
                export_pdf(path, report.analysis, period_label(report.record), figure, report)
            LOGGER.info("PDF exported: %s", "Service Desk" if isinstance(report, ManagementReport) else f"KPI {report.analysis.kpi}")
            QMessageBox.information(self, "PDF exportiert", "Die Auswertung wurde erfolgreich als PDF gespeichert.")
        except Exception as error:
            LOGGER.error("PDF export failed: %s", type(error).__name__)
            QMessageBox.warning(self, "PDF-Export fehlgeschlagen", "Die PDF-Datei konnte nicht gespeichert werden. Prüfen Sie den Speicherort und schliessen Sie eine eventuell geöffnete PDF-Datei.")

    def closeEvent(self, event):
        if self.worker is not None:
            QMessageBox.information(self, "Import läuft", "Bitte warten Sie, bis der Dateiimport abgeschlossen ist.")
            event.ignore()
        elif self.connection.worker or (self.connection.client._session_id and not self.logout_complete):
            event.ignore()
            if not self.closing:
                self.closing = True
                self.logout()
                self.network_note.setText("Anwendung wird geschlossen; Znuny-Sitzung wird beendet …")
                self.network_note.show()
        else:
            self.animator.finish_all()
            event.accept()
