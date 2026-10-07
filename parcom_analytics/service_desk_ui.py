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

from .analytics import format_duration, DataError

from .charts import draw_score_history, draw_management

from .reports import load_management_report

from .storage import LocalStore, month_label, reporting_month, period_label

from .ui import Card, label, set_table, table_view

from .theme import dark_figure, DARK_SCORE_COLORS

from .animations import ScoreRing



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

        self.live_cache = None

        self.animator = None

        self.report = Report([], [], "")

        self.setWidgetResizable(True)

        content = QWidget()

        content.setObjectName("page")

        self.setWidget(content)

        layout = QVBoxLayout(content)

        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        layout.setContentsMargins(28, 20, 28, 12)

        layout.setSpacing(12)

        layout.addWidget(label("Übersicht", "section"))



        self.hero = Card()

        hero = QHBoxLayout(self.hero)

        hero.setContentsMargins(16, 12, 16, 12)

        hero.setSpacing(32)

        summary = QVBoxLayout()

        summary.setSpacing(8)

        summary.addWidget(label("Performance Score", "muted"))

        self.score_label = label("–", wrap=False)

        self.score_label.setAccessibleName("Aktueller Performance Score")

        self.score_ring = ScoreRing()

        self.score_ring.setFixedSize(104, 104)

        ring_layout = QVBoxLayout(self.score_ring)

        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ring_layout.addWidget(self.score_label)

        summary.addWidget(self.score_ring)

        self.status_label = label("", "muted")

        summary.addWidget(self.status_label)

        self.change_label = label("", "muted")

        summary.addWidget(self.change_label)

        self.previous_label = label("", "muted")

        self.previous_label.hide()



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

        self.breakdown_card = Card()

        QVBoxLayout(self.breakdown_card).addLayout(breakdown)

        self.top_grid = QGridLayout()

        self.top_grid.setSpacing(16)

        self.top_cards = [self.hero]
        self.top_grid.addWidget(self.hero, 0, 0)

        for column in range(5):

            self.top_grid.setColumnStretch(column, 1)

        layout.addLayout(self.top_grid)

        self.overview_tiles = {}
        self.agent_selection = set()

        for column, name in enumerate(("Neue Tickets", "Geschlossene Tickets", "Abschlussverhältnis (geschlossen / neu)", "Offene Tickets"), 1):

            card, value, note = self._tile(name.replace("Abschlussverhältnis (geschlossen / neu)", "Abschlussquote"))

            self.top_cards.append(card)
            self.top_grid.addWidget(card, 0, column)

            self.overview_tiles[name] = (value, note)

        self.management_card = Card()

        management = QVBoxLayout(self.management_card)

        management.setContentsMargins(20, 12, 20, 12)

        self.management_basis = label("", "muted")

        management.addWidget(self.management_basis)

        self.middle = QGridLayout()

        self.middle.setSpacing(16)

        self.management_figure = Figure(figsize=(9, 2.3), dpi=100)

        self.management_canvas = FigureCanvasQTAgg(self.management_figure)

        self.management_canvas.setMinimumHeight(205)

        self.middle.addWidget(self.management_canvas, 0, 0, 2, 3)

        for row, name in enumerate(("Median Reaktionszeit", "Median Lösungszeit")):

            card, value, note = self._tile(name)

            value.setStyleSheet("font-size: 30px; color: #F4F7FA;")

            self.middle.addWidget(card, row, 3)

            self.overview_tiles[name] = (value, note)

        card, value, note = self._tile("Eskalationsquote")

        self.middle.addWidget(card, 0, 4, 2, 1)

        self.overview_tiles["Eskalationsquote"] = (value, note)

        self.middle.setColumnStretch(0, 2)

        self.middle.setColumnStretch(1, 2)

        self.middle.setColumnStretch(2, 2)

        self.middle.setColumnStretch(3, 2)

        self.middle.setColumnStretch(4, 2)

        management.addLayout(self.middle)

        layout.addWidget(self.management_card)

        self.operations = QGridLayout()
        self.operation_cards = []

        self.operations.setSpacing(16)

        for column, name in enumerate(("Wartende Tickets", "Überfällige Warte-Tickets", "Überfällig + gesperrt", "Offene Tickets >30 Tage")):

            card, value, note = self._tile(name)

            self.operations.addWidget(card, 0, column)
            self.operation_cards.append(card)

            self.operations.setColumnStretch(column, 1)

            self.overview_tiles[name] = (value, note)

        self.agent_card = Card()
        self.operation_cards.append(self.agent_card)
        agent_box = QVBoxLayout(self.agent_card)
        agent_box.setContentsMargins(12, 12, 12, 12)
        agent_box.addWidget(label("Abschlüsse · Team", "muted"))
        self.agent_figure = Figure(figsize=(2.3, 1.1), dpi=100)
        self.agent_canvas = FigureCanvasQTAgg(self.agent_figure)
        self.agent_canvas.setMinimumSize(100, 100)
        agent_box.addWidget(self.agent_canvas)
        self.operations.addWidget(self.agent_card, 0, 4)
        self.operations.setColumnStretch(4, 1)
        layout.addLayout(self.operations)

        self.action_note = label("Noch kein Datenstand geladen", "muted")

        layout.addWidget(self.action_note)

        self.detail_button = QPushButton("Performance · Verlauf und Aufschlüsselung")

        self.detail_button.setCheckable(True)

        self.detail_button.setObjectName("secondary")

        layout.addWidget(self.detail_button)

        self.detail_button.toggled.connect(self._show_details)

        layout.addWidget(self.breakdown_card)



        self.empty_card = Card()

        empty = QVBoxLayout(self.empty_card)

        empty.setContentsMargins(24, 24, 24, 24)

        empty.addWidget(label("Performance Score noch nicht verfügbar", "section"))

        self.empty_card.setToolTip(HISTORY_MESSAGE)

        self.issue_label = label("", "muted")

        empty.addWidget(self.issue_label)

        self.top_grid.addWidget(self.empty_card, 0, 0)


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

        self._show_details(False)

        self.method_button.toggled.connect(self._toggle_method)

        layout.addStretch()



    def _toggle_method(self, checked: bool):

        self.method_card.setVisible(checked)

        self.method_button.setText("Berechnung und Datengrundlage ausblenden" if checked

                                  else "Berechnung und Datengrundlage anzeigen")



    def refresh(self):

        if self.animator:

            self.animator.stop(self.management_canvas)

            self.animator.stop(self.canvas)

        try:

            management = self.live_cache.management() if self.live_cache else load_management_report(self.store)

            self.management_card.show()

            self.management_basis.setText("Znuny Live · " + self.live_cache.batch.period.label if self.live_cache else

                                          "Aktuellste lokale Exporte · Zeiträume je KPI unter «Berechnung und Datengrundlage»")

            for name, (value, note) in self.overview_tiles.items():

                value.setText(management.metrics.get(name, "–"))

                note.setText("Aktueller Bestand" if name in {"Offene Tickets", "Wartende Tickets", "Offene Tickets >30 Tage"} else "Ausgewählter Zeitraum")

            for name in ("Überfällige Warte-Tickets", "Überfällig + gesperrt"):
                value, note = self.overview_tiles[name]
                note.setText("Aktueller Bestand" if name in management.metrics else "Kein Timer-Datenstand")
                value.setStyleSheet("font-size: 44px; color: " + ("#FF5C6C" if int(management.metrics.get(name, "0")) else "#F4F7FA") + ";")

            self.action_note.setText("Bestand und Warte-Tickets beziehen sich auf den aktuellen Datenstand." +
                (f"  · Aktive Timer: {management.metrics['Aktive Timer']} · Ohne Timer: {management.metrics['Ohne Timer']} · Timer unbekannt: {management.metrics['Timer unbekannt']} · Auto-Schliessen: {management.metrics['Automatisches Schliessen vorgemerkt']}" if 'Aktive Timer' in management.metrics else ""))

            self._apply_live_context(management)
            self._draw_volume(management)

        except (DataError, OSError, ValueError, KeyError):

            self.management_card.hide()

            self.action_note.setText("Noch kein Datenstand geladen · Mit Znuny verbinden und aktualisieren.")

            for value, note in self.overview_tiles.values():

                value.setText("–")

                note.setText("Keine Daten")

        try:

            self.report = self.live_cache.performance() if self.live_cache else build_report(self.store)

        except Exception as error:

            LOGGER.error("Service Desk calculation failed: %s", type(error).__name__)

            self.report = Report([], [], "Die Service-Desk-Auswertung konnte nicht berechnet werden. Bitte prüfen Sie die lokalen Dateien.")

        report, score = self.report, self.report.current

        self.hero.setVisible(score is not None)

        self.empty_card.setVisible(score is None)

        self.changes_card.setVisible(score is not None and self.detail_button.isChecked())

        self.history_card.setVisible(bool(report.scores) and self.detail_button.isChecked())

        self.issue_label.setText("Vergleich noch nicht verfügbar" if report.issue else "")

        self.empty_card.setToolTip(report.issue or HISTORY_MESSAGE)

        self.period_label.setText(f"Aktueller Exportmonat: {month_label(report.periods[-1].month)}" if report.periods else "")

        self.period_label.setVisible(bool(report.periods) and self.detail_button.isChecked())

        self.context_label.setText("")

        self.context_label.hide()

        if score:

            status, color = score_status(score.value)

            color = DARK_SCORE_COLORS[color]

            self.score_label.setText(f"{number(score.value)} %")

            self.score_label.setStyleSheet("font-size: 24px; font-weight: 600; color: #F4F7FA;")

            self.score_ring.value = score.value

            self.score_ring.color = color

            if self.animator:

                self.animator.run(self.score_ring, self.score_ring.set_progress, 350)

            self.status_label.setText(status)

            self.status_label.setStyleSheet(f"color: {color};")

            self.previous_label.setText("Vormonat: noch kein berechenbarer Score")

            self.change_label.setText("Erster Vergleich")

            self.change_label.setStyleSheet("color: #a2afbe;")

            if report.previous_score:

                previous = report.previous_score.value

                delta = round(score.value - previous, 1)

                arrow, tone = ("↑", "#59bd8b") if delta > 0 else (("↓", "#e08181") if delta < 0 else ("→", "#a2afbe"))

                self.previous_label.setText(f"Vormonat: {number(previous)} %")

                self.change_label.setText(f"{arrow} {'+' if delta > 0 else ''}{number(delta)} Prozentpunkte")

                self.change_label.setStyleSheet(f"color: {tone};")

            for area, value in score.areas.items():

                text, bar = self.area_widgets[area]

                text.setText(f"{number(value)} %")

                bar.setValue(round(value * 10))

                bar.setStyleSheet("QProgressBar { background: #35404d; border: none; border-radius: 3px; }"

                                 f"QProgressBar::chunk {{ background: {DARK_SCORE_COLORS[score_status(round(value, 1))[1]]}; border-radius: 3px; }}")

            self.period_label.setText(f"Exportmonat {month_label(score.current.month)} · Vergleich: {month_label(score.previous.month)}")

            self.previous_heading.setText(month_label(score.previous.month))

            self.current_heading.setText(month_label(score.current.month))

            for key, cells in self.change_widgets.items():

                before, now = score.previous.values[key], score.current.values[key]

                cells[0].setText(metric_text(key, before))

                cells[1].setText(metric_text(key, now))

                text, color = ("↑ Verbessert", "#59bd8b") if now < before else (("↓ Verschlechtert", "#e08181") if now > before else ("→ Unverändert", "#a2afbe"))

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

                             period_label(record) if getattr(record, "period_start", None) else month_label(record.reporting_month) if record.reporting_month else "Snapshot", record.timezone])

        set_table(self.sources_table, pd.DataFrame(rows, columns=["Exportmonat", "KPI", "Exportzeitpunkt", "Berichtszeitraum", "Zeitzone"]))

        self.sources_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.period_issues.setText("\n".join(f"{month_label(period.month)}: {period.issue}" for period in report.periods if period.issue))



    def _draw_history(self):

        draw_score_history(self.figure, self.report)

        dark_figure(self.figure)

        self.history_note.setText("Exportmonate · Erster berechenbarer Score; für einen Verlauf werden weitere vollständige Monate benötigt."

                                  if len(self.report.scores) == 1 else "Exportmonate · Lücken kennzeichnen fehlende oder nicht vergleichbare Datenstände.")

        self.canvas.draw()

        if self.animator:

            self.animator.chart(self.canvas)



    def _show_details(self, checked):

        for widget in (self.breakdown_card, self.changes_card, self.history_card, self.period_label, self.method_button):

            widget.setVisible(checked)

        if not checked:

            self.method_card.hide()

            self.method_button.setChecked(False)



    def _tile(self, title):

        card = Card()

        box = QVBoxLayout(card)

        box.setContentsMargins(20, 16, 20, 16)

        box.setSpacing(8)

        box.addWidget(label(title, "muted"))

        value = label("–", "metric", False)

        value.setMinimumWidth(0)
        value.setStyleSheet("font-size: 44px; color: #F4F7FA;")

        box.addWidget(value)

        note = label("Keine Daten", "muted")

        box.addWidget(note)



        return card, value, note



    def _draw_volume(self, management):

        from .charts import style_axis

        from matplotlib.ticker import MaxNLocator

        self.management_figure.clear()

        axis = self.management_figure.add_subplot(111)

        for kpi, title, color in ((1, "Neu", "#32D5FF"), (2, "Geschlossen", "#8B6CFF")):

            series = management.kpis[kpi].analysis.chart

            if not series.empty:

                axis.plot(range(len(series)), series.values, color=color, linewidth=2, marker="o", markersize=3, label=title)

                axis.fill_between(range(len(series)), series.values, alpha=.08, color=color)

                step = max(1, len(series)//7)

                axis.set_xticks(list(range(0,len(series),step)), [str(series.index[i]) for i in range(0,len(series),step)])

        axis.set_title("Ticketentwicklung", loc="left", color="#F4F7FA", fontsize=14, pad=14)

        axis.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=4))

        style_axis(axis)

        if axis.lines:

            axis.legend(frameon=False, loc="upper right", ncol=2, labelcolor="#A6B2BF", fontsize=9)

        else:

            axis.text(.5,.5,"Keine Tickets im Zeitraum",transform=axis.transAxes, ha="center",color="#A6B2BF")

        self.management_figure.subplots_adjust(left=.06,right=.98,top=.83,bottom=.20)

        dark_figure(self.management_figure)

        self.management_canvas.draw()


    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "top_cards"):
            return
        columns = 5 if self.viewport().width() >= 1200 else 3
        for index, card in enumerate(self.top_cards):
            self.top_grid.addWidget(card, index // columns, index % columns)
        for index in range(5):
            self.top_grid.setColumnStretch(index, 1 if index < columns else 0)
        self.top_grid.addWidget(self.empty_card, 0, 0)
        for index, card in enumerate(self.operation_cards):
            self.operations.addWidget(card, index // columns, index % columns)
        for index in range(5):
            self.operations.setColumnStretch(index, 1 if index < columns else 0)

    def _apply_live_context(self, management):
        self.agent_figure.clear()
        axis = self.agent_figure.add_subplot(111)
        axis.set_axis_off()
        if self.live_cache and self.live_cache.batch:
            from .agents import metrics
            rows = sorted(metrics(self.live_cache.batch, self.agent_selection), key=lambda row:(-row["Geschlossen"],row["Techniker"]))[:5]
            if rows and any(row["Geschlossen"] for row in rows):
                axis.set_axis_on()
                bars=axis.barh([row["Techniker"] for row in rows],[row["Geschlossen"] for row in rows],color="#4C8DFF")
                axis.invert_yaxis()
                axis.bar_label(bars,padding=3,color="#A6B2BF",fontsize=8)
                axis.set_xticks([])
                axis.spines[["top","right","left","bottom"]].set_visible(False)
                axis.margins(x=.3)
            else:
                axis.text(.5,.5,"Keine Abschlüsse",ha="center",va="center",transform=axis.transAxes,color="#A6B2BF",fontsize=9)
            new_report, closed_report = management.kpis[1], management.kpis[2]
            for name, item, lower in (("Neue Tickets",new_report,True),("Geschlossene Tickets",closed_report,False)):
                if item.comparable and len(item.history)>1:
                    current = next(iter(item.analysis.metrics.values()))
                    previous = next(iter(item.history[-2].analysis.metrics.values()))
                    delta = current-previous
                    note = self.overview_tiles[name][1]
                    note.setText(f"{'↑' if delta>0 else '↓' if delta<0 else '→'} {delta:+d} zum Vorzeitraum")
                    note.setStyleSheet("color: " + ("#A6B2BF" if delta==0 or name=="Neue Tickets" else "#39E58C" if (delta<0)==lower else "#FF5C6C") + ";")
            total = next(iter(new_report.analysis.metrics.values()))
            closed = next(iter(closed_report.analysis.metrics.values()))
            ratio_value, ratio_note = self.overview_tiles["Abschlussverhältnis (geschlossen / neu)"]
            ratio_value.setText(f"{closed/total*100:.1f} %".replace(".",",") if total else "–")
            ratio_note.setText("Keine neuen Tickets" if not total else "Geschlossen / neu")
            ratio_note.setStyleSheet("color: " + ("#A6B2BF" if not total else "#39E58C" if closed>=total else "#FFB84D") + ";")
        else:
            axis.text(.5,.5,"Kein Live-Datenstand",ha="center",va="center",transform=axis.transAxes,color="#A6B2BF",fontsize=9)
        self.agent_figure.subplots_adjust(left=.22,right=.95,top=.98,bottom=.05)
        dark_figure(self.agent_figure)
        self.agent_canvas.draw()
