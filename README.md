# ParCom Znuny Analytics

Native Windows-Anwendung für den Service Desk von **ParCom Systems AG**. Version **1.0** (technisch **1.0.0**), entwickelt von **Nico Köchli**. Die Anwendung liest Znuny-Tickets aus **PBX** und **PBX Intern** und zeigt Kennzahlen, Trends und Agentenauswertungen.

**Stand:** `codex/version-1-0`, noch keine Produktionsfreigabe. Echte Znuny-Anmeldung und Abgleich mit dem Server sind noch nicht abgenommen. Ältere Installer enthalten nicht alle aktuellen Änderungen. Siehe [VALIDATION.md](VALIDATION.md).

## Installation und Start

Nach Freigabe wird `ParCom_Znuny_Analytics_Setup_1.0.0.exe` die vollständige Anwendung installieren; Benutzer benötigen kein Python. Der vorbereitete Installer unterstützt Pfadwahl, aktuellen Benutzer oder alle Benutzer mit Administratorrechten, Startmenü, optionale Desktop-Verknüpfung und Deinstallation unter Erhalt lokaler Anwendungsdaten.

Ein Git-Push veröffentlicht noch keinen Installer. Der aktuelle Entwicklungsstand wird bis zur Freigabe aus dem Quellcode gestartet. Das bereitgestellte Logo dient als Anwendungslogo und Windows-Icon.

## Anmeldung und Verbindung

Mit dem persönlichen Znuny-Konto anmelden. Festes Ziel:

```text
https://znuny.parcom.ch/otrs/nph-genericinterface.pl/Webservice/GenericTicketConnectorREST
```

Nach Anmeldung wird die letzte Woche geladen. **Offline fortfahren** öffnet den letzten lokalen Datenstand. Ohne Cache erscheint **Noch kein Datenstand geladen**. Grün bedeutet funktionierende Verbindung, Gelb laufender Verbindungs-/Ladevorgang, Rot keine nutzbare Verbindung. Bei Fehlern bleibt der vorherige Cache verfügbar.

## Hauptfunktionen

- **Übersicht:** Ticketvolumen, Abschlussverhältnis, offener Bestand, Servicezeiten, Eskalationen, Warte-Timer und Teamabschlüsse.
- **Analysen:** neue, geschlossene, offene und wartende Tickets, aktuelle Eskalationen, Reaktions- und Lösungszeiten; Diagramme, Typfilter und Detailtabellen.
- **Agenten:** zugewiesene und davon gesperrte Tickets, historische Abschlüsse, First Responses und Median der Reaktionszeit.
- **Export:** Einzelanalysen oder aggregierte Service-Desk-Übersicht als PDF.
- **Info:** Anwendung, Datenschutz, Entwickler und Darstellungseinstellungen.

Live-Eskalationen stammen aus der aktuellen serverseitigen Eskalationssuche. Wartende Tickets sind `pending reminder`; automatisch zu schliessende Tickets werden separat ausgewiesen. Aktive, fehlende und überfällige Timer werden unterschieden. **Überfällig und gesperrt** wird hervorgehoben. Unbekannte Werte bleiben unbekannt; Nullminuten werden nicht entfernt.

Ticketdetails zeigen Status, Typ, Queue, Zeitangaben, Besitzer als Agentencode, Sperre, Timer, Kundennummer und Eskalation. Kundennummer `00325` erscheint gemäss Vorgabe als **Kein Kunde zugewiesen**. Ein Klick auf die Ticketnummer öffnet Znuny ohne Session-ID im Link.

## Zeitraum und Aktualisierung

Die Timeline bietet **1T, 1W, 1M, 3M, 6M und 1J** sowie einen exakten Von-/Bis-Zeitraum. Zulässig sind ein Tag bis ein Kalenderjahr ohne zukünftiges Enddatum. Standardzeiträume enden bei «jetzt» und verschieben sich bei **Aktualisieren** mit. Ein eigener Zeitraum bleibt unverändert. Anzeigezeitzone: **Europe/Zurich**.

Neue und geschlossene Tickets verwenden den gewählten Zeitraum. Offene, eskalierte und wartende Tickets zeigen den aktuellen Bestand. Rückwirkende Abfragen erzeugen keine historischen Bestände. Vergleichszeiträume grenzen unmittelbar an und haben dieselbe verstrichene Dauer.

Alle zwei Minuten prüft eine kleine Suche über `TicketLastChangeTimeNewerDate` auf Änderungen. Bei Treffern erscheint **Neuer Datenstand verfügbar**. Erst ein ausdrücklicher Refresh ersetzt die angezeigten Daten. Netzwerkzugriffe laufen im Hintergrund.

Auf `codex/performance` verwendet der aktive Live-Loader maximal vier parallele Anfragen und einen Ticketcache. Ein Refresh lädt nur geänderte oder neu benötigte Ticketdaten nach; die serverseitigen Auswahlsuchen bleiben für korrekte Bestände und Eskalationen erhalten. Messungen und Integrationshinweise stehen in [PERFORMANCE.md](PERFORMANCE.md).

## Agentenauswertung

Abschlüsse werden aus der Ticket-Historie dem schliessenden Agenten zugeordnet. Aktueller Besitzer, `ChangeBy` und Sperre ersetzen diese Zuordnung nicht. First Responses verwenden passende Historienereignisse; nicht eindeutig zuordenbare Aktivitäten bleiben unbekannt. **SYSTEM** zählt nicht als menschlicher Agent.

Die Agentenhistorie wird auf dem Performance-Branch erst beim Öffnen von **Agenten** im Hintergrund geladen und je Ticketversion im Arbeitsspeicher wiederverwendet. Bis dahin sind Historienkennzahlen als noch nicht geladen gekennzeichnet. Fehlende Warte-Timer verwenden weiterhin den bestehenden gezielten Historien-Fallback.

Bekannte Kürzel werden verwendet; unbekannte Agenten erhalten ihre ID statt erfundener Kürzel. Team- und Agentenauswahl bleiben nach Neustart erhalten. Abgewählte Agenten verlieren keine Historie. Die Rangfolge zeigt Abschlüsse im Zeitraum und ist kein Qualitätsscore.

## Service Desk Performance

Der bestehende Score ist ein **Trendindex**, keine SLA-Erfüllung. **100 % bedeutet keine Verschlechterung gegenüber dem Vergleichsmonat**; auch ein unverändert hoher Backlog kann 100 % ergeben. Neue und geschlossene Tickets dienen als Kontext ohne Score-Gewicht.

Fünf Bereiche zählen jeweils 20 %: Backlog, Erstantwort-Eskalationsquote, mediane Reaktionszeit, mediane Lösungszeit und wartende Tickets. Backlog und wartende Tickets verwenden jeweils Anzahl und Anteil über 30 Tage. Pro Teilkennzahl gilt: bei aktuell ≤ vorher 100 %, sonst `100 × vorher / aktuell`. Von 0 auf 0 ergibt 100 %, von 0 auf einen positiven Wert 0 %. Verbesserungen sind bei 100 % gedeckelt. Die Erstantwort-Eskalation der unveränderten Formel unterscheidet sich von der allgemeinen Live-Eskalationsanalyse.

Erforderlich sind alle sieben Kennzahlen und vollständige aufeinanderfolgende Vergleichsmonate: vollständiger Vormonat für Monatskennzahlen sowie tatsächlich erhobene gemeinsame Snapshot-Tage. Eine Wochenabfrage genügt allein nicht. Ohne passende Historie oder bei unbestimmten Eingangswerten erscheint kein scheinpräziser Score. Details zeigen Formel, Teilbereiche, Datenbasis und Veränderungen.

## PDF-Export

Unter **Export** eine Auswertung wählen und über den Speichern-Dialog sichern. Einzelberichte übernehmen Kennzahlen, Diagramm, Vergleich und Ticketdetails; der Typfilter der Analyse gilt mit. Breite Tabellen werden auf lesbare Spaltengruppen verteilt. Die Management-Übersicht enthält Aggregate ohne Ticketnummern oder Titel. Zeitraum, Erstellungszeitpunkt, Quelle **Znuny Live** und Datenstand werden ausgewiesen.

## Datenspeicherung und Sicherheit

Lokaler Speicher: `%LOCALAPPDATA%\ParCom\ZnunyAnalytics\`.

- `live-cache.json`: letzter erfolgreicher Datenstand, abgeleitete Agentenaktivitäten und historische Aggregate.
- `settings.ini`: Oberflächen- und Agentenauswahl.
- `logs/app.log`: rotierende technische Protokolle.
- `exports/`: vorgeschlagener PDF-Speicherort.
- `data/` und `index.json`: bleiben für bestehende lokale Daten erhalten; die normale Oberfläche enthält keinen Import mehr.

Der letzte Stand enthält benötigte Ticketdetails, einschliesslich Titel, Kundenkennungen und Agentenreferenzen. Alte Live-Snapshots enthalten Aggregate. Keine zusätzliche lokale Verschlüsselung; Windows-Benutzerrechte schützen den Speicher. Keine Telemetrie, Datenbank oder Übertragung an andere Analysedienste.

Passwort und Session-ID werden weder gespeichert noch protokolliert. Die Session bleibt im Arbeitsspeicher; Abmelden und reguläres Schliessen versuchen `SessionDelete`. TLS-Prüfung bleibt aktiv, Windows-Zertifikate werden über `truststore` verwendet. Erlaubt sind Session-Operationen und lesende TicketSearch-, TicketGet- und TicketHistoryGet-Aufrufe. TicketGet liest eine ID pro Anfrage. Persönliche Berechtigungen gelten; abgeschnittene Suchergebnisse werden nicht als vollständig übernommen.

**Echte Znuny-Exporte, Zugangsdaten und Kundendaten dürfen niemals auf GitHub eingecheckt werden.** Tests verwenden synthetische Daten. Der Build ist nicht digital signiert; Herausgeber-Metadaten ersetzen kein Code-Signing-Zertifikat.

## Entwicklung und Tests

Windows x64, Python **3.14.8**, PySide6, pandas, openpyxl, matplotlib und pytest. Exakte Abhängigkeiten: `requirements-lock.txt`.

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv314\Scripts\python.exe start.py
.\.venv314\Scripts\python.exe -m pytest -q -o cache_dir=.validation/cache
```

Vorbereiteter Windows-Build mit PyInstaller **onedir** und Inno Setup 7:

```powershell
.\scripts\build_windows.ps1
```

Das Skript isoliert PATH von fremden Qt-/ICU-DLLs, führt Tests aus, baut die EXE und prüft deren Start ohne Python auf PATH. Erst danach entsteht der Installer. Ausgabe: `dist/release/` mit Setup und `SHA256SUMS.txt`. Die EXE benötigt ihren benachbarten `_internal`-Ordner; zur späteren Verteilung dient der vollständige Installer.

## Projektstruktur

`parcom_analytics/` enthält REST-Client, Cache, Auswertung, Timeline, Agenten, Qt-Oberfläche und PDF-Export. `tests/` enthält Fach-, REST-, UI- und PDF-Tests; `assets/` Logo und Icon. `scripts/`, `packaging/` und `installer/` enthalten die Windows-Buildkonfiguration.

## Version und Entwickler

**1.0 / 1.0.0** · **Nico Köchli** · **ParCom Systems AG**
