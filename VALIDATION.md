# Prüfstand Version 1.0

Stand: **7. Oktober 2026** · Branch: `codex/version-1-0`.

**Quellcode-Prüfstand, keine Produktionsfreigabe.** Die persönliche Znuny-Anmeldung und der Abgleich der tatsächlichen Live-Daten fehlen weiterhin. Der aktuelle Quellcode wird nicht als fertig abgenommener Installer ausgegeben.

## Abgeschlossene Phasen

| Phase | Ergebnis | Gepushter Commit |
| --- | --- | --- |
| 1 – Windows-Bundle | Kontrollierter PATH, PyInstaller onedir, isolierter EXE-Starttest vor Inno Setup | `4cfbc57` |
| 2 – Dashboard und Timeline | Zendesk-inspirierte Übersicht, exakte Zeiträume, eigener Zeitraum und responsive Oberfläche | `71759ee` |
| 3 – Live-Daten | Zeitraumabgrenzung, aktuelle Eskalationen, Warte-Timer, Typen und Zeitzonen korrigiert | `4097a7f` |
| 4 – Agenten | Historische Closed-by-Zuordnung, First Responses, Codes, persistente Teamauswahl | `594c62c` |
| 5 – Aktualisierung und Export | Leichter Änderungstest, expliziter Refresh, Cache, Ladeanzeige, Details und PDF | `c15e82f` |

Phase 6 ist **teilweise geprüft und noch nicht freigegeben**. Die ursprüngliche Packaging-Lösung ist unverändert erhalten.

## Aktuelle Prüfungen

- Vollständige Testsuite: **213 Tests bestanden**, Python 3.14.8 / PySide6 6.11.2. REST-Zugriffe werden simuliert; echte Netzwerkzugriffe sind in pytest gesperrt.
- Login, vollständiger Hintergrund-Load, alle sieben Analysen, Cache-Neustart, Reconnect, Logout und Fehlerzustände sind mit synthetischen REST-Antworten geprüft.
- Änderungstest verwendet `TicketLastChangeTimeNewerDate` mit maximal einem Treffer. Er ersetzt keinen Cache. Tests prüfen auch den Hinweis und den Unterschied zwischen rollendem und festem Zeitraum.
- Agententests prüfen historische Abschlüsse, SYSTEM-Ausschluss, uneindeutige First Responses, unbekannte IDs und persistente Auswahl.
- Timeline-Tests prüfen Presets, Monatsenden, Intervalle, Grenzen und Rückkehr aus einem eigenen Zeitraum durch Ziehen der Griffe.
- Native Windows-Ansichten mit synthetischen Daten gestartet: Agenten, Übersicht, Eskalations-Donut und Ladeanzeige. Agenten und Übersicht bei 1050 × 650 ohne horizontalen Seiten-Überlauf geprüft; breite Detailtabellen sind separat scrollbar.
- Qt-PDF-Export geprüft: Einzelbericht mit 17 Detailspalten über mehrere Spaltengruppen, Management-Bericht mit Quelle, Zeitraum, Datenstand, Kennzahlen, Diagrammen und Vergleichen. Alle sieben Seiten des korrigierten Management-Beispiels visuell geprüft. Management-PDF enthält keine Ticketnummern/Titel.
- Veraltete Erstantwort-Beschriftung im allgemeinen Eskalationsdiagramm korrigiert. Umbrüche mit nahezu leeren Folgeseiten im Management-Beispiel beseitigt.
- Regulärer Quellenstart über `pythonw.exe start.py`: Fenster **ParCom Znuny Analytics** läuft und reagiert. Keine persönliche Anmeldung durchgeführt.
- Ein Gesamttestlauf zeigte eine native Qt-Zugriffsverletzung; die betroffenen Tests bestanden isoliert. Testfenster werden seitdem nach jedem UI-Test im GUI-Thread explizit entfernt. Die beiden anschliessenden vollständigen Läufe bestanden (213 Tests, zuletzt 35,57 Sekunden).

Testdaten und visuelle Prüfartefakte liegen ausschliesslich im ignorierten Bereich `.validation`; temporäre Speicher der nativen Sichtprüfung werden automatisch entfernt. Keine echten Kundenexporte wurden für Tests eingecheckt.

## Packaging und Installer

Der isolierte Bundle-Check bestand bereits in Phase 1: Windows-GUI-EXE, frischer Anwendungsspeicher, keine Python-Umgebung auf PATH. **Dieser frühere Binärstand enthält nicht die späteren Änderungen der Phasen 2–5.** Daraus wird keine Aussage über einen aktuellen finalen Build abgeleitet.

Die abschliessende EXE-/Installer-Erstellung und der tatsächliche Installer-Smoke-Test sind noch offen. Gemäss Auftrag erfolgt vor dem finalen Packaging die echte Anmeldung und Live-Abnahme. Bestehende ältere Dateien unter `dist/review` oder `dist/release` sind keine freigegebene aktuelle Version. Eine bereits vorhandene Installation unter `C:\Dev\ParCom Znuny Analytics` wurde nicht überschrieben oder deinstalliert.

Vorgesehene Ausgaben nach erfolgreicher Abnahme:

- `dist/ParCom_Znuny_Analytics/ParCom_Znuny_Analytics.exe` mit `_internal`.
- `dist/release/ParCom_Znuny_Analytics_Setup_1.0.0.exe`.
- `dist/release/SHA256SUMS.txt`.

Keine neue finale Prüfsumme wird für einen nicht gebauten Stand angegeben.

## Verbleibende Freigabeschritte

1. Persönliche Anmeldung direkt in der Anwendung; Live-Load und Zahlen mit Znuny abgleichen, einschliesslich Agentenhistorie, Timeline, Refresh, Ticketlink, PDF und Logout. Im Chat sind keine Zugangsdaten erforderlich.
2. Danach aktueller Build mit isoliertem Bundle-Check sowie echte Installation und Start der installierten Anwendung; Verknüpfungen, Apps-Eintrag, Deinstallation und Datenerhalt prüfen.
3. Windows-Test ohne Entwicklungsumgebung. Ein PATH-isolierter Test auf dem Entwicklungsrechner ersetzt keine saubere Windows-Umgebung.

Kein Code-Signing-Zertifikat vorhanden: Metadaten nennen Nico Köchli, Windows kann trotzdem einen unbekannten Herausgeber anzeigen.

## Veröffentlichung

`main` bleibt unverändert. Kein Tag `v1.0.0`, kein GitHub-Release, kein Force-Push und keine History-Umschreibung. Die Freigabe bleibt bis zum Abschluss der realen Prüfung offen. Ein Quellcode-Push stellt nicht automatisch einen Installer zum Download bereit.
