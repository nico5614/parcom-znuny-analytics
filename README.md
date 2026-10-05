# ParCom Znuny Analytics

## Beschreibung

Windows-Desktopanwendung zur lokalen Auswertung von Service-KPIs der PBX-Abteilung aus Znuny-Excel-Exporten. Der funktionsfähige Prototyp nutzt eine native PySide6-Oberfläche mit eingebetteten Matplotlib-Diagrammen.

## Funktionen

- Ein skalierbares Hauptfenster mit **Start**, **Upload**, **Dashboard**, **Service Desk** und **Download**; Standardgrösse 1280 × 800, Mindestgrösse 1050 × 650.
- Mehrfachimport von `.xlsx`-Dateien mit Prüfung von Dateiname, Exportdatum, Uhrzeit, Zeitzone und Arbeitsmappe.
- Dauerhafte lokale Kopien und SHA-256-Duplikatprüfung. Ein identischer Inhalt mit derselben KPI und demselben Exportzeitpunkt wird nicht erneut importiert. Ein neuer Exportzeitpunkt bleibt als eigener Datenstand erhalten, auch wenn sich die Ticketliste nicht geändert hat.
- Automatische Auswahl des neuesten Exports je KPI und Berichtsmonat beziehungsweise des neuesten Snapshots.
- Kennzahlen, Diagramme und Detailtabellen für alle sieben KPIs. Beim Start ist keine KPI vorausgewählt.
- Trendbasierter Service Desk Performance Score mit transparenter Berechnung, Teilbereichen, Monatsverlauf und Erklärung der Veränderungen.
- PDF-Export der aktuellen Auswertung über einen Speichern-Dialog: KPI, Zeitraum, Kennzahlen, Diagramm, Erstellungszeitpunkt und vollständige Detailtabelle; lange Tabellen werden auf mehrere Seiten verteilt.
- Verständliche Leerzustände und Fehlermeldungen sowie lokale, rotierende Protokolldateien.

## Unterstützte KPIs

| KPI | Auswertung | Zeitraum |
| --- | --- | --- |
| 1 | Neue Tickets mit Tagesverteilung | Monat |
| 2 | Geschlossene Tickets mit Tagesverteilung | Monat |
| 3 | Offene Tickets, Alter und Altersgrenzen | Snapshot |
| 4 | Offene Tickets nach Erstantwort-Eskalation; Nachverfolgung eskalierter Tickets | Snapshot |
| 5 | Reaktionszeit: Anzahl, Durchschnitt, Median, Nullwerte und Verteilung | Monat |
| 6 | Lösungszeit: Anzahl, Durchschnitt, Median, Nullwerte und Verteilung | Monat |
| 7 | Wartende Tickets, Alter und Altersgrenzen | Snapshot |

Der Berichtsmonat ist der **vorherige Kalendermonat des Exportdatums**, auch beim Jahreswechsel. Ein Export vom 29.09.2026 gehört zu August 2026. Snapshot-KPIs zeigen den Datenstand mit Datum und Uhrzeit aus dem Dateinamen und haben keine Monatsauswahl.

Die Anwendung verwendet die erste Tabelle der Arbeitsmappe, entfernt Leerzeichen an den Spaltennamen und benötigt keine feste Spaltenreihenfolge. Die Znuny-Abfrage muss bereits die jeweilige PBX-Ticketmenge liefern; die Anwendung filtert diese nicht nochmals nach Queue, Status oder Kalendermonat.

Dateinamen müssen diesem Muster entsprechen; der beschreibende Teil darf variieren:

```text
KPI_7___PBX__Wartende_Tickets_Created_2026-09-29_10-52_TimeZone_Europe_Zurich.xlsx
```

Zeitzonen werden als IANA-Zonen interpretiert, beispielsweise `Europe_Zurich` als `Europe/Zurich`. Die Abhängigkeit `tzdata` stellt diese Informationen auch unter Windows bereit.

Benötigte Spalten:

| KPI | Spalten |
| --- | --- |
| 1 | `Ticket#`, `Titel`, `Erstellt`, `Status` |
| 2 | `Ticket#`, `Titel`, `Schließzeit`, `Status` |
| 3, 7 | `Ticket#`, `Alter`, `Titel`; optional: `Status`, `Priorität` |
| 4 | `Ticket#`, `Titel`, `Alter`, `Status`, `Priorität`, `FirstResponseTimeEscalation`, `FirstResponseTimeDestinationDate` |
| 5 | `Ticket#`, `Titel`, `Erstantwortzeit in Minuten` |
| 6 | `Ticket#`, `Titel`, `Lösungszeit in Minuten` |

Altersangaben wie `31 m`, `2 h 45 m` und `446 d 18 h` werden in Minuten umgerechnet. «Älter als» ist eine strikte Grenze: Genau sieben Tage zählen nicht zu «älter als 7 Tage». Nicht lesbare Alters- oder Datumswerte werden sichtbar ausgewiesen. Fehlende, negative oder unendliche Minutenwerte werden ausgeschlossen und gemeldet; **0 Minuten bleiben enthalten**. Eskalationswerte müssen 0 oder 1 sein; 1 bedeutet eskaliert. Tabellen mit Zeitkennzahlen sind absteigend sortiert; Alterstabellen zeigen die ältesten Tickets zuerst.

Bei KPI 3 und 7 sind `Status` und `Priorität` zusätzliche Tabellenangaben. Fehlen diese Spalten, funktionieren Kennzahlen und Altersdiagramm weiterhin. Die fehlenden Angaben erscheinen als «–» in der Tabelle; Dashboard und PDF weisen darauf hin. Status und Priorität werden nicht aus anderen Feldern abgeleitet.

## Service Desk Performance

Das Register **Service Desk** bewertet die Entwicklung vergleichbarer Datenstände. **100 % bedeutet keine Verschlechterung gegenüber dem Vergleichsmonat.** Der Score misst weder absolute Servicequalität noch SLA-Erfüllung. Auch ein unverändert hoher Ticketbestand kann 100 % ergeben. Ein steigender Score kann auch eine verlangsamte Verschlechterung bedeuten; die konkreten Veränderungen zeigen die Vorher-/Nachher-Werte. Es gibt keine erfundenen SLA-Zielwerte.

Ein vollständiger Datenstand besteht aus allen sieben KPIs eines **Exportmonats**:

- KPI 1, 2, 5 und 6 liefern den jeweiligen Vormonat als Berichtszeitraum; pro KPI wird der neueste Export verwendet.
- KPI 3, 4 und 7 müssen gemeinsam für den neuesten vorhandenen Snapshot-Tag des Exportmonats vorliegen. Je KPI zählt der neueste Export dieses Tages.
- Beispiel: Der Score für Oktober vergleicht die im Oktober exportierten September-Zeitkennzahlen und Oktober-Snapshots mit den entsprechenden Daten aus dem Exportmonat September. Exportzeitpunkte und Berichtszeiträume stehen unter **Berechnung und Datengrundlage**.
- Nur aufeinanderfolgende vollständige Exportmonate mit identischen Zeitzonen werden verglichen. Unterschiedliche Exporttage und Änderungen am Ticketmix können den Vergleich beeinflussen. Mehrere Exporte im selben Monat bilden keine zusätzliche Historie.

Ein einzelner vollständiger Datenstand erzeugt keinen Score. Zwei vergleichbare Monatsdatenstände ergeben den ersten Score; drei ergeben erstmals zwei Score-Punkte und eine Veränderung gegenüber dem Vormonat. Fehlende Monate werden im Diagramm nicht verbunden. Ein unvollständiger neuester Exportmonat wird als solcher angezeigt; ein älterer Score wird nicht als aktueller ausgegeben.

### Formel und Gewichtung

Alle verwendeten Teilkennzahlen werden bei sinkenden Werten günstiger bewertet:

```text
Teilscore = 100 %, wenn aktuell ≤ vorher
Teilscore = 100 × vorher / aktuell, wenn aktuell > vorher
Bereichsscore = Mittel seiner Teilscores
Gesamtscore = Mittel der fünf Bereichsscores
```

Von 0 auf 0 und von einem positiven Wert auf 0 ergibt 100 %; von 0 auf einen positiven Wert ergibt 0 %. Verbesserungen sind bei 100 % gedeckelt und gleichen Verschlechterungen anderer Teilkennzahlen nicht aus. Beispiel: Steigt eine Zeit von 60 auf 120 Minuten, beträgt ihr Teilscore 50 %. Bleibt sie gleich oder sinkt, beträgt er 100 %.

| Bereich | Grundlage | Gewicht am Gesamtscore |
| --- | --- | --- |
| Backlog | Anzahl offener Tickets und Anteil über 30 Tage (KPI 3) | je 10 %, zusammen 20 % |
| Eskalationen | Anteil `FirstResponseTimeEscalation == 1` an KPI 4 | 20 % |
| Reaktionszeit | Median der Minutenwerte aus KPI 5 | 20 % |
| Lösungszeit | Median der Minutenwerte aus KPI 6 | 20 % |
| Wartende Tickets | Anzahl und Anteil über 30 Tage (KPI 7) | je 10 %, zusammen 20 % |

Die bereits im KPI-Dashboard verwendete Altersgruppe über 30 Tage ist eine Vergleichsgrösse, **kein SLA-Ziel**. KPI 3 enthält auch wartende Tickets. KPI 1 und 2 liefern ausschliesslich Kontext: neue Tickets, geschlossene Tickets und Abschlussverhältnis (`geschlossen / neu`). Bei null neuen Tickets bleibt das Verhältnis unbestimmt. Diese Kontextwerte beeinflussen den Score nicht.

Null-Minuten-Werte bleiben enthalten. Fehlende Dateien oder benötigte Spalten sowie ungültige Alters-, Eskalations- oder Minutenwerte verhindern den Score für die betreffende Periode. Leere Bestandslisten ergeben Anzahl und Anteil 0; eine leere Zeitmessung ergibt keinen Median und daher keinen Score. Es werden keine fehlenden Bereiche durch andere ersetzt.

Der Gesamtscore und die Veränderung werden auf eine Dezimalstelle gerundet. 0,0 Prozentpunkte gelten als unverändert. Die Statusfarben beziehen sich auf den dargestellten **Trendindex**: ab 90 % grün / «Sehr gut», ab 75 % gelb / «Gut», ab 60 % orange / «Aufmerksamkeit erforderlich», darunter rot / «Kritisch». Die Aufschlüsselung zeigt jeden Vorher-/Nachher-Wert, seine Entwicklung und seinen Teilscore.

Die Historie wird lokal aus den importierten Dateien rekonstruiert und bleibt nach einem Neustart erhalten. Der bestehende PDF-Export unter **Download** bezieht sich weiterhin auf die ausgewählte Einzel-KPI unter **Dashboard**.

## Entwicklungsumgebung

- Windows 10/11 mit Python **3.12 oder neuer**
- PySide6, pandas, openpyxl, Matplotlib, tzdata
- pytest für automatisierte Tests; QtTest und QtPdf sind in PySide6 enthalten

In PowerShell im Projektordner:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Es werden keine Datenbank, kein Webserver und keine Qt-Designer-Dateien verwendet. Die Anwendung benötigt nach Installation der Abhängigkeiten keine Internetverbindung.

## Anwendung starten

```powershell
.\.venv\Scripts\python.exe start.py
```

Alternativ:

```powershell
.\.venv\Scripts\python.exe -m parcom_analytics
```

1. Unter **Upload** einen oder mehrere Znuny-Exporte auswählen.
2. Unter **Dashboard** die KPI und bei Monats-KPIs den verfügbaren Berichtsmonat auswählen.
3. Unter **Service Desk** bei ausreichender Historie den Performance Score und seine Herleitung prüfen.
4. Unter **Download** die ausgewählte Einzel-KPI mit **Als PDF exportieren** speichern.

Ein zweiter gleichzeitiger Anwendungsstart wird verhindert, damit sich Schreibzugriffe auf den Dateiindex nicht überschneiden. Während eines Imports bleibt die Oberfläche bedienbar; die Anwendung kann nach Abschluss des Imports geschlossen werden.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Die Tests verwenden ausschliesslich synthetische DataFrames und temporär erzeugte Excel-Dateien. Sie prüfen Dateinamen, Zeitzonen, Monatswechsel, Altersparser, Duplikate, Dateikopien, Neustart-Persistenz, beschädigte Indizes, Spaltenprüfungen und alle KPI-Berechnungen.

Qt-Integrationstests prüfen Navigation, konstante Fenstergrösse, Leerzustände, Import über den Upload-Button, Monats- und Snapshot-Auswertungen, PDF-Freigabe sowie ein- und mehrseitige PDF-Inhalte. Sie laufen ohne sichtbares Testfenster; native Dateidialoge werden dabei durch temporäre Testpfade ersetzt.

Score-Tests prüfen Formel und Gewichtung, Nullwerte, Statusgrenzen, historische Vergleichbarkeit, Jahreswechsel, Lücken, ungültige Daten, die Auswahl neuester Exporte und den fehlenden Einfluss von KPI 1/2. Der Service-Desk-Integrationstest importiert drei synthetische Monatsdatenstände, prüft die automatische Aktualisierung, den Verlauf, beide Fenstergrössen und die Wiederherstellung nach einem Neustart.

## Datenspeicherung

Die Anwendung erstellt automatisch:

```text
%LOCALAPPDATA%\ParCom\ZnunyAnalytics\
├── data\
│   ├── kpi_1\
│   ├── kpi_2\
│   ├── kpi_3\
│   ├── kpi_4\
│   ├── kpi_5\
│   ├── kpi_6\
│   └── kpi_7\
├── exports\
├── logs\
│   └── app.log
└── index.json
```

Die Originaldatei wird kopiert und darf danach aus dem Downloadordner entfernt werden. `index.json` enthält Originalname, lokalen Namen und relativen Speicherpfad, SHA-256, KPI, Exportzeitpunkt mit UTC-Abweichung, Zeitzone und gegebenenfalls Berichtsmonat. Der Index wird atomar ersetzt.

Ein beschädigter Index wird unter `index.corrupt-<Zeitpunkt>.json` gesichert; die Anwendung zeigt einen Hinweis und legt einen neuen Index an. Vorhandene Arbeitsmappen bleiben erhalten. Zur Wiederaufnahme können sie mit einem gültigen Znuny-Dateinamen erneut importiert werden. Ein fehlender lokaler Dateispeicher wird im Dashboard gemeldet.

## Datenschutz

Alle Ticketdaten werden ausschliesslich lokal verarbeitet. Die Anwendung überträgt keine Daten an externe Dienste. Die Protokolle enthalten technische Statusinformationen, KPI-Nummern und gekürzte Hashwerte, keine vollständigen Ticketinhalte.

**Echte Znuny-Exporte und Kundendaten dürfen niemals auf GitHub eingecheckt werden.** `.gitignore` schliesst Excel-Dateien, erzeugte PDFs, lokale Datenordner, Protokolle und Testartefakte aus. Für Tests dürfen nur synthetische Daten verwendet werden.

## Projektstruktur

```text
assets/app_logo.png              Anwendungslogo, Fenstersymbol und dezentes Wasserzeichen
parcom_analytics/
    __main__.py                 Anwendungsstart, Protokollierung und Instanzsperre
    storage.py                  Dateinamen, Excel-Import und JSON-Persistenz
    analytics.py                Unabhängige KPI-Berechnungen
    service_desk.py             Periodenvergleich und transparenter Performance Score
    service_desk_ui.py          Service-Desk-Register, Verlauf und Datengrundlage
    charts.py                   Matplotlib-Diagramme
    ui.py                       Native Qt-Seiten und Tabellen
    pdf_export.py               Paginierter PDF-Export mit Qt
tests/                          Fach- und Integrationstests
start.py                        Einfacher Startpunkt
requirements.txt                Python-Abhängigkeiten
```

## Version

**0.1.0-prototype**, Entwicklungsbranch `develop/prototype`.

Dieser Stand ist zur fachlichen und visuellen Prüfung vorgesehen. Installer, Signierung, automatische Updates und Produktionsveröffentlichung sind nicht Bestandteil dieses Prototyps.

## Entwickler

Entwickelt von **Nico Köchli** für **ParCom Systems AG**.
