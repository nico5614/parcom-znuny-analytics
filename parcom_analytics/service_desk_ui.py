"""Native Service Desk overview with an auditable trend score."""

from datetime import datetime
import logging

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QHeaderView, QLayout, QProgressBar,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .service_desk import (
    HISTORY_MESSAGE, METRICS, Report, build_report, score_status,
)
from .analytics import format_duration
from .charts import draw_score_history
from .storage import LocalStore, month_label, reporting_month
from .ui import Card, label, set_table, table_view

LOGGER = logging.getLogger(__name__)
METHOD = (
    "Fünf Bereiche zählen zu je 20 %. Backlog und wartende Tickets bestehen jeweils zur Hälfte aus "
    "Ticketanzahl und Anteil der Tickets über 30 Tage (je 10 % des Gesamtscores). Eskalationen verwenden "
    "den Anteil der Erstantwort-Eskalationen an allen Tickets in KPI 4. Reaktions- und Lösungszeit "
    "verwenden jeweils den Median der Minutenwerte, einschliesslich 0 Minuten.\n\n"
    "Bei allen sieben Teilkennzahlen ist ein niedrigerer Wert günstiger. Teilscore = 100 %, wenn aktuell ≤ vorher; "
    "sonst 100 × vorher / aktuell. Von 0 auf einen positiven Wert ergibt 0 %, von 0 auf 0 ergibt 100 %. "
    "Ein Bereich ist das arithmetische Mittel seiner Teilscores; der Gesamtscore ist das Mittel der fünf Bereiche. "
    "Verbesserungen sind bei 100 % gedeckelt und gleichen Verschlechterungen in anderen Kennzahlen nicht aus. "
    "Ergebnis und Veränderung werden auf eine Dezimalstelle gerundet; 0,0 Prozentpunkte gelten als unverändert.\n\n"
    "Die Statusfarben bewerten ausschliesslich diesen Trendindex: ab 90 % Sehr gut, ab 75 % Gut, "
    "ab 60 % Aufmerksamkeit erforderlich, darunter Kritisch. 100 % bedeutet keine Verschlechterung "
    "gegenüber dem Vergleichsmonat – auch ein unverändert hoher Bestand kann 100 % ergeben. "
    "Es werden keine SLA-Erfüllung und keine absolute Servicequalität gemessen. "
    "Ein steigender Score kann auch eine verlangsamte Verschlechterung bedeuten; die konkreten Veränderungen "
    "zeigen die Vorher-/Nachher-Werte. Die Altersgruppe "
    "über 30 Tage ist eine Vergleichsgrösse, kein SLA-Ziel. KPI 3 enthält auch wartende Tickets. "
    "Neue und geschlossene Tickets (KPI 1/2) sind ausschliesslich Kontext und haben kein Score-Gewicht.\n\n"
    "Eine Periode entspricht dem Exportmonat: KPI 1/2/5/6 beziehen sich auf dessen Vormonat; "
    "KPI 3/4/7 auf den neuesten Snapshot-Tag innerhalb des Exportmonats. Alle drei Snapshots müssen für "
    "diesen Tag vorliegen. Je KPI wird der neueste passende Export verwendet. Nur vollständige Datenstände "
    "aufeinanderfolgender Exportmonate mit derselben Zeitzone werden verglichen. Weitere Exporte im selben "
    "Monat ersetzen den Stand und erzeugen keinen zusätzlichen Verlaufspunkt. Unterschiedliche Exporttage "
    "zwischen Monaten und Änderungen am Ticketmix können den Vergleich beeinflussen.\n\n"
    "Fehlende Dateien, benötigte Spalten oder ungültige Alters-/Minutenwerte verhindern den Score. "
    "Leere Bestandslisten ergeben Anzahl und Anteil 0; leere Zeitmessungen ergeben keinen Score. "
    "Lücken im Verlauf werden nicht verbunden. Der aktuelle Stand ist immer der neueste Exportmonat, "
    "auch wenn er noch unvollständig ist. Die Datengrundlage unten zeigt alle verwendeten Exporte."
)


def number(value: float) -> str:
    return f"{value:,.1f}".replace(",", "’").replace(".", ",")


def metric_text(key: str, value: float) -> str:
    unit = METRICS[key][2]
    if unit == "share":
        return f"{number(value * 100)} %"
    if unit == "minutes":
        return format_duration(value)
    return f"{int(value):,}".replace(",", "’")


class ServiceDeskPage(QScrollArea):
    def __init__(self, store: LocalStore):
        super().__init__()
        self.store = store
        self.report = Report([], [], "")
        self.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("page")
        self.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(28, 20, 28, 12)
        layout.setSpacing(12)
        layout.addWidget(label("Service Desk", "title"))
        layout.addWidget(label("Basierend auf der Entwicklung der Service-KPIs", "muted"))

        self.hero = Card()
        hero = QHBoxLayout(self.hero)
        hero.setContentsMargins(24, 20, 24, 20)
        hero.setSpacing(32)
        summary = QVBoxLayout()
        summary.setSpacing(8)
        summary.addWidget(label("Service Desk Performance", "section"))
        self.score_label = label("–", wrap=False)
        self.score_label.setAccessibleName("Aktueller Performance Score")
        summary.addWidget(self.score_label)
        self.status_label = label("", "section")
        summary.addWidget(self.status_label)
        self.change_label = label("", "section")
        summary.addWidget(self.change_label)
        self.previous_label = label("", "muted")
        summary.addWidget(self.previous_label)
        summary.addStretch()
        hero.addLayout(summary, 1)
        breakdown = QVBoxLayout()
        breakdown.setSpacing(6)
        breakdown.addWidget(label("Teilbereiche · je 20 % Gewicht", "section"))
        self.area_widgets = {}
        for area in dict.fromkeys(spec[0] for spec in METRICS.values()):
            row = QHBoxLayout()
            row.addWidget(label(area, wrap=False))
            value = label("", "section", False)
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(value)
            breakdown.addLayout(row)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setAccessibleName(area)
            breakdown.addWidget(bar)
            self.area_widgets[area] = (value, bar)
        hero.addLayout(breakdown, 1)
        layout.addWidget(self.hero)

        self.empty_card = Card()
        empty = QVBoxLayout(self.empty_card)
        empty.setContentsMargins(24, 24, 24, 24)
        empty.addWidget(label("Performance Score noch nicht verfügbar", "title"))
        empty.addWidget(label(HISTORY_MESSAGE, "muted"))
        self.issue_label = label("", "warning")
        empty.addWidget(self.issue_label)
        layout.addWidget(self.empty_card)
        self.period_label = label("", "eyebrow")
        layout.addWidget(self.period_label)
        layout.addWidget(label("Trendindex: 100 % bedeutet keine Verschlechterung gegenüber dem Vergleichsmonat. "
                               "Der Score misst keine SLA-Erfüllung oder absolute Servicequalität.", "muted"))

        self.history_card = Card()
        history = QVBoxLayout(self.history_card)
        history.setContentsMargins(18, 14, 18, 8)
        history.addWidget(label("Performance im Zeitverlauf", "section"))
        self.history_note = label("", "muted")
        history.addWidget(self.history_note)
        self.figure = Figure(figsize=(10, 2), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(200)
        history.addWidget(self.canvas)
        layout.addWidget(self.history_card)

        self.changes_card = Card()
        changes = QVBoxLayout(self.changes_card)
        changes.setContentsMargins(20, 16, 20, 16)
        changes.addWidget(label("Was hat sich verändert?", "section"))
        self.changes_grid = QGridLayout()
        self.changes_grid.setHorizontalSpacing(20)
        self.changes_grid.setVerticalSpacing(10)
        self.previous_heading = label("Vorher", "muted", False)
        self.current_heading = label("Aktuell", "muted", False)
        for column, widget in enumerate([label("Teilkennzahl", "muted"), self.previous_heading,
                                         self.current_heading, label("Entwicklung", "muted"), label("Teilscore", "muted")]):
            self.changes_grid.addWidget(widget, 0, column)
        self.change_widgets = {}
        for row, (key, (_, title, _)) in enumerate(METRICS.items(), 1):
            self.changes_grid.addWidget(label(title), row, 0)
            cells = [label("", wrap=False) for _ in range(4)]
            for column, cell in enumerate(cells, 1):
                self.changes_grid.addWidget(cell, row, column)
            self.change_widgets[key] = cells
        self.changes_grid.setColumnStretch(0, 1)
        changes.addLayout(self.changes_grid)
        layout.addWidget(self.changes_card)

        self.context_label = label("", "muted")
        layout.addWidget(self.context_label)
        self.method_button = QPushButton("Berechnung und Datengrundlage anzeigen")
        self.method_button.setCheckable(True)
        layout.addWidget(self.method_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.method_card = Card()
        method = QVBoxLayout(self.method_card)
        method.setContentsMargins(22, 20, 22, 20)
        method.addWidget(label("So entsteht der Score", "section"))
        method.addWidget(label(METHOD, "muted"))
        method.addWidget(label("Verwendete Datenstände · Exportmonate", "section"))
        self.sources_table = table_view()
        self.sources_table.setMinimumHeight(280)
        method.addWidget(self.sources_table)
        self.period_issues = label("", "muted")
        method.addWidget(self.period_issues)
        layout.addWidget(self.method_card)
        self.method_card.hide()
        self.method_button.toggled.connect(self._toggle_method)
        layout.addStretch()

    def _toggle_method(self, checked: bool):
        self.method_card.setVisible(checked)
        self.method_button.setText("Berechnung und Datengrundlage ausblenden" if checked
                                  else "Berechnung und Datengrundlage anzeigen")

    def refresh(self):
        try:
            self.report = build_report(self.store)
        except Exception as error:
            LOGGER.error("Service Desk calculation failed: %s", type(error).__name__)
            self.report = Report([], [], "Die Service-Desk-Auswertung konnte nicht berechnet werden. Bitte prüfen Sie die lokalen Dateien.")
        report, score = self.report, self.report.current
        self.hero.setVisible(score is not None)
        self.empty_card.setVisible(score is None)
        self.changes_card.setVisible(score is not None)
        self.history_card.setVisible(bool(report.scores))
        self.issue_label.setText(report.issue)
        self.period_label.setText(f"Aktueller Exportmonat: {month_label(report.periods[-1].month)}" if report.periods else "")
        self.period_label.setVisible(bool(report.periods))
        self.context_label.setText("")
        self.context_label.setVisible(score is not None)
        if score:
            status, color = score_status(score.value)
            self.score_label.setText(f"{number(score.value)} %")
            self.score_label.setStyleSheet(f"font-size: 60px; font-weight: 600; color: {color};")
            self.status_label.setText(status)
            self.status_label.setStyleSheet(f"color: {color};")
            self.previous_label.setText("Vormonat: noch kein berechenbarer Score")
            self.change_label.setText("Erster berechenbarer Score")
            self.change_label.setStyleSheet("color: #65727d;")
            if report.previous_score:
                previous = report.previous_score.value
                delta = round(score.value - previous, 1)
                arrow, tone = ("↑", "#23784c") if delta > 0 else (("↓", "#bd3838") if delta < 0 else ("→", "#65727d"))
                self.previous_label.setText(f"Vormonat: {number(previous)} %")
                self.change_label.setText(f"{arrow} {'+' if delta > 0 else ''}{number(delta)} Prozentpunkte")
                self.change_label.setStyleSheet(f"color: {tone};")
            for area, value in score.areas.items():
                text, bar = self.area_widgets[area]
                text.setText(f"{number(value)} %")
                bar.setValue(round(value * 10))
                bar.setStyleSheet("QProgressBar { background: #edf0f2; border: none; border-radius: 3px; }"
                                 f"QProgressBar::chunk {{ background: {score_status(round(value, 1))[1]}; border-radius: 3px; }}")
            self.period_label.setText(f"Exportmonat {month_label(score.current.month)} · Vergleich: {month_label(score.previous.month)}")
            self.previous_heading.setText(month_label(score.previous.month))
            self.current_heading.setText(month_label(score.current.month))
            for key, cells in self.change_widgets.items():
                before, now = score.previous.values[key], score.current.values[key]
                cells[0].setText(metric_text(key, before))
                cells[1].setText(metric_text(key, now))
                text, color = ("↑ Verbessert", "#23784c") if now < before else (("↓ Verschlechtert", "#bd3838") if now > before else ("→ Unverändert", "#65727d"))
                cells[2].setText(text)
                cells[2].setStyleSheet(f"color: {color};")
                cells[3].setText(f"{number(score.components[key])} %")
            current = score.current
            ratio = f"{number(current.closed_count / current.new_count * 100)} %" if current.new_count else "nicht berechenbar (keine neuen Tickets)"
            month = reporting_month(datetime.fromisoformat(current.month + "-01"))
            self.context_label.setText(f"Arbeitsbelastung · {month_label(month)}: {current.new_count} neue Tickets · "
                                       f"{current.closed_count} geschlossene Tickets · Abschlussverhältnis: {ratio}. "
                                       "KPI 1 und 2 dienen nur als Kontext; kein Einfluss auf den Score.")
        self._draw_history()
        rows = []
        for period in reversed(report.periods):
            for kpi, record in sorted(period.records.items()):
                stamp = datetime.fromisoformat(record.export_timestamp)
                rows.append([month_label(period.month), f"KPI {kpi}", stamp.strftime("%d.%m.%Y %H:%M"),
                             month_label(record.reporting_month) if record.reporting_month else "Snapshot", record.timezone])
        set_table(self.sources_table, pd.DataFrame(rows, columns=["Exportmonat", "KPI", "Exportzeitpunkt", "Berichtszeitraum", "Zeitzone"]))
        self.sources_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.period_issues.setText("\n".join(f"{month_label(period.month)}: {period.issue}" for period in report.periods if period.issue))

    def _draw_history(self):
        draw_score_history(self.figure, self.report)
        self.history_note.setText("Exportmonate · Erster berechenbarer Score; für einen Verlauf werden weitere vollständige Monate benötigt."
                                  if len(self.report.scores) == 1 else "Exportmonate · Lücken kennzeichnen fehlende oder nicht vergleichbare Datenstände.")
        self.canvas.draw()
