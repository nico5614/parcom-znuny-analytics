# ParCom Znuny Analytics

## Beschreibung

Native Windows-Anwendung für die Service-KPIs von **PBX** und **PBX Intern**, entwickelt für ParCom Systems AG. Version **1.0** verbindet den bisherigen Excel-Import mit lesendem Znuny-Zugriff, einer dunklen Oberfläche und gemeinsam berechneten Dashboards und PDF-Berichten.

**Freigabestatus:** `codex/version-1-0` enthält einen Prüfbuild. Echte Znuny-Anmeldung und Abnahme auf einem sauberen Windows-System sind noch offen. Es gibt daher noch keine Produktionsfreigabe `v1.0.0` auf `main`. Siehe [VALIDATION.md](VALIDATION.md).

## Funktionen

- Maximierter Start mit persönlicher Anmeldung oder **Offline fortfahren**; native Windows-Fenstersteuerung.
- Navigation **Übersicht**, **KPIs**, **Import**, **Berichte** sowie **Info** und **Abmelden**.
- Skalierbarer Dark Mode, kurze Seiten-, Zahlen-, Diagramm- und Score-Animationen. **Animationen reduzieren** unter Info bleibt nach Neustart gespeichert.
- HTTPS-Abfragen im Hintergrund; Fehler lassen lokale Auswertungen verfügbar.
- Zeiträume 7/30 Tage, 3/6/12 Monate oder benutzerdefiniert, maximal zwölf Kalendermonate. Nach Anmeldung werden 30 Tage geladen; weitere Abfragen erfolgen über **Aktualisieren**.
- Excel-Mehrfachimport, dauerhafte Kopien, SHA-256-Duplikatprüfung, Bestandsübersicht und bestätigtes Löschen lokaler Datensätze.
- Gemeinsame Berechnungen für Excel, Live-Daten, Dashboard und PDF. Unabhängige Berichtsauswahl ohne vorherigen Dashboard-Aufruf.
- Management-Übersicht mit Ticketvolumen, Backlog, Eskalationen, Servicezeiten und transparentem Performance Score.

## Unterstützte KPIs

| KPI | Auswertung | Zeitbezug |
| --- | --- | --- |
| 1 | Neue Tickets, Tagesverteilung und Tagesdurchschnitt | Zeitraum |
| 2 | Geschlossene Tickets, Tagesverteilung und Tagesdurchschnitt | Zeitraum |
| 3 | Offene Tickets inklusive wartender Tickets und Altersverteilung | Aktueller Snapshot |
| 4 | Erstantwort-Eskalationen, Donut mit Anzahl und Quote, Nachverfolgung | Aktueller Snapshot |
| 5 | Reaktionszeit: Median, Durchschnitt, Verteilung, langsamste Tickets | Geschlossene Tickets im Zeitraum |
| 6 | Lösungszeit: Median, Durchschnitt, Verteilung, längste Zeiten | Geschlossene Tickets im Zeitraum |
| 7 | Wartende Tickets, Alter und Nachverfolgung | Aktueller Snapshot |

Intern werden Minuten verwendet; die Anzeige formatiert Tage, Stunden und Minuten einheitlich. **0 Minuten bleiben erhalten; fehlende Werte bleiben fehlend.** REST-`Age` wird von Sekunden in volle Minuten umgerechnet. Unlesbare Werte werden gemeldet. Alterstabellen sind absteigend sortiert, Ticketnummern kopierbar.

Die Altersklassen verwenden exakte Grenzen bei 7, 14 und 30 Tagen. Bis 14 Tage bleiben neutral, über 14 bis 30 Tage amber, über 30 Tage rot. Dies sind Aufmerksamkeitshinweise, keine SLA-Ziele. Bei Zeitkennzahlen markiert das 75. Perzentil mit linearer Interpolation auffällige Werte; bei unterschiedlichen Werten erscheinen Höchstwerte rot und fett. Konstante Verteilungen erhalten keine farblichen Ausreisser. Tagesdurchschnitte berücksichtigen alle Kalendertage des abgebildeten Diagrammzeitraums, auch Tage ohne Tickets.

Eskalationen bedeuten ausschliesslich `FirstResponseTimeEscalation == 1`; die Quote bezieht sich auf alle Tickets in KPI 4. Fehlende Felder werden als unbekannt gemeldet, nicht auf 0 gesetzt. Bei fehlenden Feldern ist die Quote nur für die vorhandenen Informationen aussagekräftig.

## Znuny-Anmeldung und Live-Daten

Festes Ziel:

```text
https://znuny.parcom.ch/otrs/nph-genericinterface.pl/Webservice/GenericTicketConnectorREST
```

Erlaubt sind nur `SessionCreate`, `SessionDelete`, `TicketSearch` und `TicketGet` mit `Extended=1`. Keine Ticket-Schreiboperationen, Datenbankverbindung oder Automatisierung der Znuny-Weboberfläche. Die Queues stehen zentral in `znuny.py`.

REST-Mapping: `POST /Session`, `DELETE /Session/<ID>`, `POST /Ticket/Search`, `GET /Ticket/<TicketID>`. TicketGet verwendet eine Anfrage pro Ticket-ID. Windows-Zertifikate werden über truststore eingebunden. TLS-Zertifikatsprüfung bleibt aktiv; Umleitungen werden nicht verfolgt. Persönliche Znuny-Berechtigungen gelten weiterhin.

Benutzername und Passwort werden nicht gespeichert. Das Passwortfeld wird beim Absenden geleert; die Session-ID bleibt ausschliesslich im Arbeitsspeicher. Abmelden, Benutzerwechsel, Wechsel zu Offline und normales Schliessen versuchen `SessionDelete`. Bei Prozessabbruch oder unerreichbarem Server ist die serverseitige Bereinigung nicht garantiert.

Grün bedeutet gültige Sitzung und letzte Anfrage erfolgreich, Gelb laufende Verbindung/Aktualisierung, Rot keine nutzbare Verbindung. Anmeldefehler, abgelaufene Sitzung und Netzwerkfehler haben unterschiedliche Meldungen. Über **Verbinden** beziehungsweise **Neu verbinden** ist eine erneute Anmeldung möglich.

Normale Requests verwenden 5 Sekunden Verbindungs- und 30 Sekunden Lese-Timeout, Logout 1 beziehungsweise 2 Sekunden. Keine automatischen Endlosversuche. TicketGet liest Gruppen von höchstens 50 IDs. Erreicht eine Suche 10’000 Treffer, wird der Lauf mit Hinweis abgebrochen, statt unvollständige Zahlen zu übernehmen. Fehler erhalten den vorherigen Cache.

Zeitfilter gelten für erstellte beziehungsweise geschlossene Tickets. KPI 3/4/7 zeigen immer den aktuellen Bestand. Eine heute gestellte August-Abfrage erzeugt keinen rückwirkenden August-Snapshot.

## Excel-Import

Unter **Import** eine oder mehrere `.xlsx`-Dateien auswählen. Dateiname, Zeitstempel, Zeitzone und Arbeitsmappe werden geprüft. Verwendet wird die erste Tabelle; Spaltennamen werden getrimmt, ihre Reihenfolge ist beliebig. Beispiel:

```text
KPI_7___PBX__Wartende_Tickets_Created_2026-09-29_10-52_TimeZone_Europe_Zurich.xlsx
```

Für KPI 1/2/5/6 ist der Berichtsmonat der Kalendermonat vor dem Exportdatum. Je KPI/Monat wird zunächst der neueste Export gewählt; ältere Monate bleiben auswählbar. KPI 3/4/7 verwenden Snapshots, deren ältere Datenstände ebenfalls auswählbar bleiben. Excel-Dateien müssen bereits die passende Ticketmenge enthalten; sie werden nicht nachträglich wie eine REST-Suche gefiltert.

| KPI | Benötigte Spalten |
| --- | --- |
| 1 | `Ticket#`, `Titel`, `Erstellt`, `Status` |
| 2 | `Ticket#`, `Titel`, `Schließzeit`, `Status` |
| 3, 7 | `Ticket#`, `Alter`, `Titel`; optional `Status`, `Priorität` |
| 4 | `Ticket#`, `Titel`, `Alter`, `Status`, `Priorität`, `FirstResponseTimeEscalation`, `FirstResponseTimeDestinationDate` |
| 5 | `Ticket#`, `Titel`, `Erstantwortzeit in Minuten` |
| 6 | `Ticket#`, `Titel`, `Lösungszeit in Minuten` |

Identischer Inhalt mit derselben KPI und demselben Exportzeitpunkt wird nicht erneut importiert. Ein neuer Exportzeitpunkt bleibt ein eigener Datenstand. Die Bestandsübersicht zeigt vorhandene und fehlende KPIs. Löschen entfernt nach Bestätigung nur die lokale Kopie und den Indexeintrag; die Originaldatei bleibt erhalten.

## Service Desk Performance und Historie

**100 % bedeutet keine Verschlechterung gegenüber dem Vergleichsmonat**, keine SLA-Erfüllung oder absolute Servicequalität. Auch ein unverändert hoher Bestand kann 100 % ergeben. Ein steigender Score kann eine verlangsamte Verschlechterung bedeuten. Vorher-/Nachher-Werte und Teilbereiche werden deshalb offengelegt. Keine erfundenen SLA-Ziele.

Die bestehende Formel bleibt unverändert:

```text
Teilscore = 100 %, wenn aktuell ≤ vorher
Teilscore = 100 × vorher / aktuell, wenn aktuell > vorher
Bereichsscore = Mittel seiner Teilscores
Gesamtscore = Mittel der fünf Bereichsscores
```

| Bereich | Grundlage | Gewicht |
| --- | --- | --- |
| Backlog | Anzahl offener Tickets und Anteil über 30 Tage | je 10 % |
| Eskalationen | Erstantwort-Eskalationsquote | 20 % |
| Reaktionszeit | Median einschliesslich Nullwerte | 20 % |
| Lösungszeit | Median einschliesslich Nullwerte | 20 % |
| Wartende Tickets | Anzahl und Anteil über 30 Tage | je 10 % |

Von 0 auf 0 ergibt 100 %, von 0 auf einen positiven Wert 0 %. Verbesserungen sind bei 100 % gedeckelt und gleichen Verschlechterungen anderer Teilkennzahlen nicht aus. KPI 1/2 sind Kontext ohne Score-Gewicht. Abschlussverhältnis und Ticketdifferenz werden nur für denselben Zeitraum berechnet; bei null neuen Tickets ist das Verhältnis unbestimmt. Ticketdifferenz bedeutet geschlossen minus neu.

Alle sieben KPIs müssen vorliegen. Eine Score-Periode entspricht dem Erfassungs-/Exportmonat: monatliche KPIs beziehen sich auf dessen vollständigen Vormonat, Snapshot-KPIs auf den tatsächlichen neuesten gemeinsamen Snapshot-Tag. Verglichen werden nur vollständige aufeinanderfolgende Monate mit derselben Zeitzone. Zwei Perioden liefern den ersten Score, drei erstmals eine Veränderung zum vorherigen Score. Lücken werden nicht verbunden; ein unvollständiger neuester Stand wird nicht durch einen älteren Score verdeckt. Unbekannte Alters-/Zeitwerte verhindern einen scheinpräzisen Score. Ein leerer Bestand ist 0; eine leere Zeitmessung hat keinen Median.

Live-Verläufe enthalten nur tatsächlich erhobene Snapshots. Monatliche Verlaufswerte entstehen nur für vollständig abgefragte Kalendermonate. Teilmonate werden nicht als vollständige Monatsvergleiche ausgegeben. Excel- und Live-Historien bleiben nach Quelle getrennt. Alte Live-Stände enthalten nur Aggregate, Ticketdetails ausschliesslich der letzte erfolgreiche Lauf.

Score und Veränderung werden auf eine Dezimalstelle gerundet. Ab 90 % **Sehr gut**, ab 75 % **Gut**, ab 60 % **Aufmerksamkeit erforderlich**, darunter **Kritisch**. Unterschiedliche Snapshot-Tage und Änderungen am Ticketmix können Vergleiche beeinflussen; die Datengrundlage bleibt sichtbar.

## Berichte und PDF

Unter **Berichte** unabhängig vom Dashboard eine KPI oder **Service Desk – Gesamtübersicht** wählen. Die Quelle wird oben gewählt. Lokale Berichtsmonate/Snapshots beziehungsweise der zuletzt geladene Live-Zeitraum stehen entsprechend zur Verfügung.

Einzelberichte enthalten Kennzahlen, finales Diagramm ohne Animation, Quelle, Zeitraum/Datenstand, Verlauf, Vergleich, Details und Erstellungszeitpunkt. Management-Berichte benötigen sieben gültige KPI-Auswertungen und enthalten **keine Ticketnummern, Titel oder personenbezogenen Ticketdetails**. Fehlende Score-Historie wird ausdrücklich ausgewiesen. Export über Qt und Speichern-Dialog; bestehende PDFs werden erst nach erfolgreicher Erstellung ersetzt.

## Installation und Anwendung starten

Nach Freigabe genügt **ParCom_Znuny_Analytics_Setup_1.0.0.exe**. Python, Qt und Bibliotheken werden mitgeliefert; die Installation benötigt keine Internetverbindung. Live-Daten benötigen danach Zugang zu Znuny.

Der dunkle Installer bietet Installationspfad, aktuellen Benutzer beziehungsweise alle Benutzer mit Administratorrechten und eine optionale Desktop-Verknüpfung. Standardziel ist der Windows-Programmordner unter `ParCom\ParCom Znuny Analytics`. Startmenü und Windows-Apps-Eintrag werden angelegt. Start über die Verknüpfung oder `ParCom_Znuny_Analytics.exe` im Installationsordner, ohne Konsolenfenster.

PyInstaller verwendet **onedir**: Die Anwendungs-EXE benötigt ihren benachbarten `_internal`-Ordner. Zur Verteilung den vollständigen Installer verwenden. Deinstallation über Windows **Installierte Apps** oder Startmenü; Daten unter `%LOCALAPPDATA%` bleiben für eine Neuinstallation erhalten.

**Signierung:** Dateimetadaten nennen Nico Köchli als Herausgeber. Der Prüfbuild ist nicht digital signiert. Windows kann «Unbekannter Herausgeber» oder eine SmartScreen-Warnung anzeigen. Metadaten ersetzen kein Code-Signing-Zertifikat.

## Entwicklungsumgebung

Windows x64, Python **3.14.8** stable, PySide6 **6.11.2**, PyInstaller **6.22.3**, Inno Setup **7.1.0**. Exakte Python-Pakete: `requirements-lock.txt`. Allgemeine Abhängigkeiten: `requirements.txt`; Build-Einstieg: `requirements-build.txt`.

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv314\Scripts\python.exe start.py
```

## Tests und Windows-Build

```powershell
New-Item -ItemType Directory -Path .validation -Force
.\.venv314\Scripts\python.exe -m pytest -q -o cache_dir=.validation/cache
.\scripts\build_windows.ps1
```

Inno Setup 7 muss installiert sein; einen abweichenden Compilerpfad über `-IsccPath` angeben. Das Skript prüft Python 3.14 stable, führt alle Tests aus, erzeugt Windows-Ressourcen, PyInstaller-Anwendung und Installer. Ausgabe: `dist\release\ParCom_Znuny_Analytics_Setup_1.0.0.exe` und `SHA256SUMS.txt`. Der onedir-Build liegt in `dist\ParCom_Znuny_Analytics`. Beim Benutzer werden weder Python noch Pakete nachgeladen.

Tests verwenden synthetische Daten und temporäre Excel-Dateien. Echte Netzwerkzugriffe sind in pytest gesperrt; REST-Antworten werden simuliert. Geprüft werden Berechnungen, Import, Persistenz, Historie, Score, Fehlerfälle, Sitzungen, Hintergrundverarbeitung, Cache, Datenschutz, Qt-Oberfläche, Animationen und PDF-Inhalte. Das ersetzt keine echte Serverabnahme oder einen Test auf sauberem Windows.

## Datenspeicherung und Datenschutz

```text
%LOCALAPPDATA%\ParCom\ZnunyAnalytics\
├── data\kpi_1\ … kpi_7\   Excel-Kopien
├── exports\               Vorgeschlagener PDF-Speicherort
├── logs\app.log            Rotierende technische Protokolle
├── index.json              Excel-Index, Hash und Zeitbezug
├── live-cache.json         Letzter Live-Stand und historische Aggregate
└── settings.ini            Oberflächenpräferenzen
```

Originaldateien können nach Import entfernt werden. Index und Cache werden atomar geschrieben. Ein beschädigter Excel-Index wird als `index.corrupt-<Zeitpunkt>.json` gesichert; Arbeitsmappen bleiben erhalten. Ein beschädigter Live-Cache wird gemeldet, ohne Excel-Daten zu verändern. Unter Import kann der Live-Cache samt Historie nach Bestätigung gelöscht werden.

Der letzte Live-Stand speichert nur benötigte Felder: Ticketnummer/-ID, Titel, Zeitangaben, Queue, Status, Priorität, Eskalations-/Zeitwerte. Keine Artikel, Nachrichten, Anhänge, Kundenkennungen, Passwörter oder Session-IDs. Historische Live-Einträge enthalten nur Aggregate. Excel-Kopien behalten die importierten Originalspalten. Der lokale Speicher verwendet Windows-Benutzerrechte, keine zusätzliche Verschlüsselung.

Live-Anfragen gehen ausschliesslich an den angegebenen Znuny-Server. Es gibt keine Telemetrie oder Übertragung von Ticketdaten an weitere Dienste. Logs enthalten technische Ereignisse und Fehlerklassen, keine Passwörter, Session-IDs, Benutzernamen oder vollständigen Ticketantworten.

**Echte Znuny-Exporte, Zugangsdaten und Kundendaten dürfen niemals auf GitHub eingecheckt werden.** Excel-Dateien, PDFs, lokale Daten, Logs, Build-Ausgaben und Testartefakte sind ausgeschlossen. Automatische Tests dürfen den echten Server nicht aufrufen.

## Projektstruktur

```text
assets/                     Vorhandenes Logo, Windows-Icon
parcom_analytics/
    __main__.py             Start, Instanzsperre, Logging
    storage.py              Excel, Dateinamen, Index, Löschen
    znuny.py                Lesender REST-Client
    connection.py           Qt-Hintergrundjobs, Sitzungen
    live_data.py            Datumsfilter, Normalisierung
    live_cache.py           Offline-Daten, aggregierte Historie
    analytics.py            Gemeinsame KPI-Berechnungen
    reports.py              Quellen, Vergleiche, Management-Daten
    service_desk.py         Score-Formel, Periodenvergleich
    ui.py                   Anmeldung, Navigation, Import, Berichte
    service_desk_ui.py      Management- und Performance-Ansicht
    charts.py               Matplotlib-Diagramme
    theme.py                Dark Mode, Asset-Auswahl
    animations.py           Abschaltbare Qt-Animationen
    pdf_export.py           Paginierte Qt-PDFs
tests/                      Synthetische Fach- und Integrationstests
packaging/                  PyInstaller-Konfiguration
installer/                  Inno-Setup-Konfiguration
scripts/                    Build, Windows-Ressourcen
```

Das bereitgestellte Logo bleibt unverändert. `assets/app_icon.ico` enthält mehrere Windows-Grössen. Eine vorhandene dunkle Variante kann optional unter `assets/app_logo_dark.png` ergänzt werden; sonst gilt `assets/app_logo.png`. `assets/app_logo_light.png` ist als Ablage für eine helle Variante vorgesehen; aktuell gibt es keinen hellen UI-Modus.

## Version und Entwickler

Anzeige **1.0**, technische Version **1.0.0**, Windows-Dateiversion **1.0.0.0**. Entwickelt von **Nico Köchli** für **ParCom Systems AG**.
