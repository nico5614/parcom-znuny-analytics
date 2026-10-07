"""Compact team and individual activity dashboard."""

import json
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox,
                               QPushButton, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem)

from .agents import SEED_AGENTS, identity, code, metrics
from .analytics import format_duration
from .theme import dark_figure
from .ui import Card, label, table_view, set_table, open_ticket


class AgentsPage(QScrollArea):
    def __init__(self, cache, settings):
        super().__init__()
        self.cache, self.settings = cache, settings
        self.registry = {key:identity(key) for key in SEED_AGENTS if key != "1"}
        try:
            self.registry.update(json.loads(settings.value("agent_registry", "{}")))
            self.selected = set(json.loads(settings.value("team_selection", json.dumps(list(self.registry)))))
        except (ValueError, TypeError):
            self.selected = set(self.registry)
        self.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("page")
        self.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(16)
        header = QHBoxLayout()
        header.addWidget(label("Agenten", "title"))
        header.addStretch()
        self.selector = QComboBox()
        self.selector.setMinimumWidth(210)
        self.selector.setAccessibleName("Techniker auswählen")
        self.selector.currentIndexChanged.connect(self.render)
        header.addWidget(self.selector)
        manage = QPushButton("Team verwalten")
        manage.setObjectName("secondary")
        manage.clicked.connect(self.manage_team)
        header.addWidget(manage)
        layout.addLayout(header)
        self.note = label("Noch kein Datenstand geladen", "muted")
        layout.addWidget(self.note)
        grid = QGridLayout()
        grid.setSpacing(16)
        self.values = {}
        for position, name in enumerate(("Aktuell im Besitz", "Davon gesperrt", "Geschlossen", "Erstantworten", "Median Reaktionszeit")):
            card = Card()
            box = QVBoxLayout(card)
            box.setContentsMargins(20, 20, 20, 20)
            box.addWidget(label(name, "muted"))
            value = label("–", "metric")
            value.setStyleSheet("font-size: 44px;")
            box.addWidget(value)
            self.values[name] = value
            grid.addWidget(card, position//3, position%3)
        layout.addLayout(grid)
        chart = Card()
        box = QVBoxLayout(chart)
        box.addWidget(label("Geschlossene Tickets nach Techniker", "section"))
        self.ranking_note = label("", "muted")
        box.addWidget(self.ranking_note)
        self.figure = Figure(figsize=(10,2),dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(200)
        box.addWidget(self.canvas)
        layout.addWidget(chart)
        details = Card()
        box = QVBoxLayout(details)
        box.addWidget(label("Aktivität und aktueller Besitz", "section"))
        self.table = table_view()
        self.table.setMinimumHeight(190)
        self.table.clicked.connect(lambda index:open_ticket(self.table.model(),index))
        box.addWidget(self.table)
        layout.addWidget(details)
        self.refresh()

    def refresh(self):
        batch = self.cache.batch
        if batch:
            for item in batch.identities:
                if item["id"] != "1":
                    self.registry[item["id"]] = item
            self.settings.setValue("agent_registry", json.dumps(self.registry, ensure_ascii=False))
            # First real load fixes the initial selection; newly discovered IDs stay opt-in.
            if not self.settings.contains("team_selection"):
                self.settings.setValue("team_selection",json.dumps(sorted(self.selected)))
        previous = self.selector.currentData()
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItem("Gesamtes Team", None)
        for key in sorted(self.selected, key=lambda item:self.registry.get(item,{}).get("name",item)):
            self.selector.addItem(self.registry.get(key,{}).get("name",f"ID {key}"), key)
        self.selector.setCurrentIndex(max(0,self.selector.findData(previous)))
        self.selector.blockSignals(False)
        self.render()

    def manage_team(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Team verwalten")
        dialog.resize(440,520)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Techniker für die Teamauswertung auswählen", "section"))
        listing = QListWidget()
        for key,item in sorted(self.registry.items(), key=lambda pair:pair[1]["name"]):
            entry = QListWidgetItem(f"{item['name']} · {item['code']}")
            entry.setData(Qt.ItemDataRole.UserRole,key)
            entry.setFlags(entry.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Checked if key in self.selected else Qt.CheckState.Unchecked)
            listing.addItem(entry)
        layout.addWidget(listing)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.selected = {listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(listing.count()) if listing.item(i).checkState()==Qt.CheckState.Checked}
            self.settings.setValue("team_selection",json.dumps(sorted(self.selected)))
            self.refresh()

    def render(self):
        batch = self.cache.batch
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        if not batch:
            self.note.setText("Noch kein Datenstand geladen")
            self.ranking_note.setText("")
            for value in self.values.values():
                value.setText("–")
            axis.text(.5,.5,"Noch keine Aktivität geladen",ha="center",transform=axis.transAxes)
            axis.set_axis_off()
            set_table(self.table,pd.DataFrame())
        else:
            selected = {self.selector.currentData()} if self.selector.currentData() else self.selected
            rows = metrics(batch,selected)
            for name,value in self.values.items():
                if name != "Median Reaktionszeit":
                    value.setText(str(sum(row[name] for row in rows)))
            activity = pd.DataFrame(batch.agents)
            current = activity.loc[activity["period"].eq("current")] if not activity.empty else activity
            response = current.loc[current["ResponseByID"].isin(selected)] if not current.empty else current
            from .analytics import numeric_values
            median = numeric_values(response["response_minutes"]).median() if not response.empty else None
            self.values["Median Reaktionszeit"].setText(format_duration(median))
            system = int(current["ClosedByID"].eq("1").sum()) if not current.empty else 0
            unknown = int(batch.frames[2]["ClosedByID"].isna().sum())
            self.note.setText(f"{batch.period.label} · {len(selected)} Techniker · SYSTEM-Abschlüsse: {system} · Unbekannte Abschlüsse: {unknown}")
            rows.sort(key=lambda row:(-row["Geschlossen"], row["Techniker"]))
            most = max((row["Geschlossen"] for row in rows),default=0)
            leaders = " / ".join(row["Techniker"] for row in rows if row["Geschlossen"] == most)
            self.ranking_note.setText(f"Meiste Abschlüsse im Zeitraum: {leaders} · {most} Tickets" if most
                                      else "Keine menschlichen Abschlüsse für die Auswahl vorhanden")
            if rows:
                bars=axis.bar([row["Techniker"] for row in rows],[row["Geschlossen"] for row in rows],color="#32D5FF",width=.55)
                axis.bar_label(bars,padding=4,color="#F4F7FA")
                axis.margins(y=.25)
                from matplotlib.ticker import MaxNLocator
                axis.yaxis.set_major_locator(MaxNLocator(integer=True,nbins=4))
            else:
                axis.text(.5,.5,"Unter «Team verwalten» Techniker auswählen",ha="center",transform=axis.transAxes)
            axis.spines[["top","right","left","bottom"]].set_visible(False)
            owned = batch.frames[3].loc[batch.frames[3]["OwnerID"].map(str).isin(selected)].copy()
            events = current.loc[current["ClosedByID"].isin(selected)|current["ResponseByID"].isin(selected)].copy() if not current.empty else current
            combined = pd.concat([owned,events],ignore_index=True).groupby("TicketID",sort=False,dropna=False).first().reset_index()
            for source,target in (("OwnerID","Besitzer"),("ClosedByID","Geschlossen durch"),("ResponseByID","Erste Antwort")):
                combined[target] = combined[source].map(code) if source in combined else "–"
            columns=["Ticket#","Titel","Typ","Status","Besitzer","Sperre","Geschlossen durch","Erste Antwort"]
            details=combined.reindex(columns=columns)
            details.attrs["ticket_ids"] = dict(zip(combined["Ticket#"].map(str),combined["TicketID"].map(str))) if "TicketID" in combined else {}
            set_table(self.table,details)
        self.figure.subplots_adjust(left=.05,right=.98,top=.9,bottom=.20)
        dark_figure(self.figure)
        self.canvas.draw()
