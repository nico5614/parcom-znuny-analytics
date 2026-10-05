# ParCom Znuny Analytics

## Beschreibung

Windows-Desktopanwendung zur lokalen Auswertung von Service-KPIs der PBX-Abteilung aus Znuny-Excel-Exporten. Der funktionsfähige Prototyp nutzt eine native PySide6-Oberfläche mit eingebetteten Matplotlib-Diagrammen.

## Funktionen

- Ein skalierbares Hauptfenster mit **Start**, **Upload**, **Dashboard**, **Service Desk** und **Download**; Standardgrösse 1280 × 800, Mindestgrösse 1050 × 650.
- Mehrfachimport von `.xlsx`-Dateien mit Prüfung von Dateiname, Exportdatum, Uhrzeit, Zeitzone und Arbeitsmappe.
- Dauerhafte lokale Kopien und SHA-256-Duplikatprüfung. Ein identischer Inhalt mit derselben KPI und demselben Exportzeitpunkt wird nicht erneut importiert. Ein neuer Exportzeitpunkt bleibt als eigener Datenstand erhalten, auch wenn sich die Ticketliste nicht geändert hat.
- Automatische Auswahl des neuesten Exports je KPI und Berichtsmonat beziehungsweise des neuesten Snapshots; ältere Berichtsmonate und Snapshots bleiben auswählbar.
- Kennzahlen, Diagramme und Detailtabellen für alle sieben KPIs. Beim Start ist keine KPI vorausgewählt.
- Trendbasierter Service Desk Performance Score mit transparenter Berechnung, Teilbereichen, Monatsverlauf und Erklärung der Veränderungen.
- Unabhängige Berichtsauswahl unter **Download**, einschliesslich älterer Berichtsmonate und Snapshots. Dashboard und Service Desk müssen vorher nicht geöffnet werden.
- PDF-Berichte mit denselben Kennzahlen, Diagrammen, Vergleichswerten und Tabellenmarkierungen wie im Dashboard; vollständige Detailtabellen werden bei Bedarf auf mehrere Seiten verteilt.
- Aggregierter Service-Desk-PDF-Bericht mit Management-Kennzahlen, bestehendem Performance Score, Verläufen und transparenter Datenbasis; ohne Ticketdetails oder Kundendaten.
- Anklickbare Ticketnummern werden in die Zwischenablage kopiert; eine kurze Meldung bestätigt das Kopieren.
- Verständliche Leerzustände und Fehlermeldungen sowie lokale, rotierende Protokolldateien.

## Unterstützte KPIs

| KPI | Auswertung | Zeitraum |
| --- | --- | --- |
| 1 | Tagesbalken mit Durchschnittslinie und beschrifteten Höchstwerten; orange Mengenkennzahl ohne Warnbewertung | Monat |
| 2 | Tagesbalken mit Durchschnittslinie und beschrifteten Höchstwerten; neutrale Mengenbewertung | Monat |
| 3 | Altersklassen mit Amber/Rot für ältere Tickets; dezente Zeilenmarkierungen und älteste Tickets fett | Snapshot |
| 4 | Donut mit Eskalationsquote und Anzahl; eskalierte Tickets dezent rot | Snapshot |
| 5 | Histogramm mit Median und Durchschnitt; menschenlesbare Zeiten; Perzentil-/Höchstwertmarkierung | Monat |
| 6 | Histogramm mit Median und Durchschnitt; menschenlesbare Zeiten; Perzentil-/Höchstwertmarkierung | Monat |
| 7 | Altersklassen, markierte alte Tickets und fett hervorgehobene älteste Tickets | Snapshot |

Der Berichtsmonat ist der **vorherige Kalendermonat des Exportdatums**, auch beim Jahreswechsel. Ein Export vom 29.09.2026 gehört zu August 2026. Snapshot-KPIs zeigen den tatsächlichen Datenstand mit Datum und Uhrzeit aus dem Dateinamen. Sie haben eine Datenstandsauswahl anstelle einer Monatsauswahl.

Das Einzel-KPI-Dashboard zeigt einen Verlauf bis zum ausgewählten Monat beziehungsweise Snapshot sowie den Vergleich zum unmittelbar vorherigen vorhandenen Datenstand. Für KPI 5/6 steht der Median im Vordergrund; der Durchschnitt wird ergänzend dargestellt. Bei Bestands-KPIs wird auch die Anzahl der Tickets über 30 Tage gezeigt. Ein einzelner Datenstand erzeugt keine behauptete Entwicklung. Nicht lesbare oder wegen ihrer Zeitzone nicht vergleichbare historische Dateien werden als Lücken gemeldet. Die bestehenden Regeln des Service-Desk-Scores bleiben davon getrennt unverändert.

Der Tagesdurchschnitt von KPI 1/2 berücksichtigt alle Kalendertage des im Diagramm abgebildeten Zeitraums, einschliesslich Tagen ohne Tickets. Tage über dem Durchschnitt und Höchstwerte verwenden dunklere Orangetöne. Die Altersklassen «0–7 / 8–14 / 15–30 / >30 Tage» verwenden weiterhin die exakten Grenzen bei 7, 14 und 30 Tagen; beispielsweise gehört 7 Tage plus 1 Minute zur zweiten Klasse. Amber markiert über 14 bis 30 Tage, Rot über 30 Tage. Dies sind Aufmerksamkeitshinweise, keine erfundenen SLA-Grenzen.

Für KPI 5/6 wird das 75. Perzentil aus den gültigen Minutenwerten des gewählten Datensatzes mit linearer Interpolation berechnet. Werte darüber werden amber markiert; die höchsten Werte bei einer nicht konstanten Verteilung rot. Alle Höchstwerte sind fett. Bei ausschliesslich gleichen Werten gibt es keine farbliche Ausreissermarkierung. Nullwerte bleiben enthalten. Die Regeln und das konkrete Perzentil stehen direkt über der Tabelle und im PDF.

Eine gemeinsame Zeitformatierung wird in Kennzahlen, Tabellen, Diagrammen, Vergleichen, Service Desk und PDFs verwendet: beispielsweise `83 → 1 h 23 min`, `1823 → 1 d 6 h 23 min`, `5874 → 4 d 1 h 54 min`. Bruchteile einer Minute werden auf eine Dezimalstelle gerundet angezeigt. Berechnungen verwenden weiterhin numerische Minutenwerte.

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

Die Historie wird lokal aus den importierten Dateien rekonstruiert und bleibt nach einem Neustart erhalten. Der PDF-Export wird unabhängig unter **Download** ausgewählt.

## Berichtszentrale und PDF-Export

Unter **Download** zuerst eine KPI oder **Service Desk – Gesamtübersicht** auswählen. Für Monats-KPIs erscheinen nur vorhandene Berichtsmonate, für Snapshot-KPIs nur vorhandene Datenstände. Der neueste Eintrag ist standardmässig ausgewählt; ältere Einträge bleiben verfügbar. Die Auswahl im Dashboard beeinflusst diese Auswahl nicht.

Einzel-KPI-Berichte enthalten die ausgewählte Auswertung, die verbesserten Diagramme, historische Entwicklung bis zum gewählten Datenstand, den Vergleich zum vorherigen verfügbaren Datenstand und sämtliche Ticketdetails mit denselben Hervorhebungen. Berechnungen und Formatierung werden mit der Oberfläche geteilt. Der Dateiname enthält KPI und Berichtsmonat beziehungsweise Snapshot-Zeitpunkt, etwa `KPI_5_Reaktionszeit_2026-09.pdf`.

**Service Desk – Gesamtübersicht** benötigt gültige aktuelle Datensätze für alle sieben KPIs. Fehlt eine KPI oder ein benötigter Alters-/Zeitwert, bleibt der Export deaktiviert. Ein vollständiger einzelner Datenstand genügt für den Management-Bericht; der Performance Score bleibt ohne ausreichende Historie ausdrücklich nicht verfügbar. Die Score-Formel wird nicht verändert.

Der Management-Bericht verwendet die jeweils aktuellste vorhandene Datei je KPI. Er enthält neue und geschlossene Tickets, offene und wartende Tickets einschliesslich Beständen über 30 Tage, Eskalationsquote, Zeitmediane, Vergleichswerte und Verläufe. Abschlussverhältnis und Ticketdifferenz werden nur bei übereinstimmenden Berichtsmonaten von KPI 1 und 2 angegeben; bei null neuen Tickets ist das Verhältnis nicht berechenbar. Ticketdifferenz bedeutet geschlossene minus neue Tickets. Die Datenbasis nennt für jede KPI Berichtszeitraum, Exportzeitpunkt und Zeitzone; der Score nennt seinen eigenen Vergleichszeitraum.

Der Service-Desk-Bericht enthält **keine Ticketnummern, Titel, Kundendaten oder personenbezogenen Ticketdetails**. Er erhält den Standardnamen `Service_Desk_<Erstellungsdatum>.pdf`. Alle Berichte werden mit Qt über den bestehenden Speichern-Dialog erzeugt. Es wird keine zusätzliche Bibliothek benötigt.

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
4. Unter **Download** unabhängig die gewünschte Auswertung und den Zeitraum auswählen und mit **Als PDF exportieren** speichern. Dieser Schritt funktioniert auch direkt nach dem Upload oder einem Neustart.

Ein zweiter gleichzeitiger Anwendungsstart wird verhindert, damit sich Schreibzugriffe auf den Dateiindex nicht überschneiden. Während eines Imports bleibt die Oberfläche bedienbar; die Anwendung kann nach Abschluss des Imports geschlossen werden.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Die Tests verwenden ausschliesslich synthetische DataFrames und temporär erzeugte Excel-Dateien. Sie prüfen Dateinamen, Zeitzonen, Monatswechsel, Altersparser, Duplikate, Dateikopien, Neustart-Persistenz, beschädigte Indizes, Spaltenprüfungen und alle KPI-Berechnungen.

Qt-Integrationstests prüfen Navigation, konstante Fenstergrösse, Leerzustände, Import über den Upload-Button, Monats- und Snapshot-Auswertungen, PDF-Freigabe sowie ein- und mehrseitige PDF-Inhalte. Sie laufen ohne sichtbares Testfenster; native Dateidialoge werden dabei durch temporäre Testpfade ersetzt.

Zusätzliche Berichtstests prüfen Altersklassen und Markierungsgrenzen, gemeinsame Zeitformatierung, Perzentile und Höchstwerte, Tagesdurchschnitte, Donut-Quote, Referenzlinien, verfügbare Exportzeiträume, die unabhängige Download-Auswahl, Zwischenablage, Neustart und vollständige Management-Daten. PDF-Tests vergleichen die Werte mit der zentralen Analyse und prüfen, dass im Management-Bericht keine synthetischen Ticket-Identifikatoren oder Titel vorkommen.

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
    reports.py                  Gemeinsame Berichtsauswahl, Einzel-KPI-Verlauf und Management-Daten
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
