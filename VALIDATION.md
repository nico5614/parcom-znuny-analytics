# Prüfstand Version 1.0.0 – Integration

Stand: **8. Oktober 2026** · Branch: **codex/integration**.

**Automatisierter Integrationsstand und lokales Installationspaket geprüft; keine Produktionsfreigabe.** Die echte Znuny-Abnahme, ein frischer Windows-Rechner und der physische DPI-Wechsel bleiben offen. Main, Tag und GitHub Release wurden nicht verändert.

## Integrierte Stände

| Bestandteil | SHA |
| --- | --- |
| Unveränderte Basis codex/version-1-0 | `5e993d0826b389cdccee51e7f6e1d460c5e22838` |
| Performance integriert | `b393882f97b93e3a464d34abcb7bb90f8b1c3951` |
| Frontend integriert | `0d8083c673acca37f6949d3d9ba18b7e2847e956` |
| Installer-Checkpoint | `c141b63` |
| README-/Screenshot-Checkpoint | `5f7cd8de5a346bc3a34e81f3065bfe9f6f0c70bf` |
| Main unverändert | `f25d853550fba6f86ef8bdc7e4bde3da9118fce8` |

Der abschliessende Validierungscommit ist der Commit mit dieser Dokumentänderung (`git log -1 --format=%H -- VALIDATION.md`). Vollständige Phasen- und Fortsetzungsnotizen: [INTEGRATION.md](INTEGRATION.md).

## Automatisierte Ergebnisse

| Prüfung | Ergebnis |
| --- | --- |
| Vollständige Python-Suite | **282 bestanden**, 47,01 s |
| Frontend / Vitest | **14 bestanden**, 5 Testdateien |
| TypeScript und Vite-Produktion | Bestanden |
| Playwright-Navigation und Fehlerzustände | **8 bestanden**, 25,4 s |
| Separate Dokumentationsaufnahme | **1 bestanden**, 5,3 s |
| README-Dateilinks / anonyme Screenshot-Identitäten | Bestanden |
| Frontend-Build gegen eingefrorene Assets | Alle Dateien SHA256-identisch |

Geprüfte Umgebung: Python 3.14.8, PySide6 6.11.2, pywebview 6.2.1, PyInstaller 6.22.3, pnpm 11.25.0, Inno Setup 7.1.0 und vorhandene Windows-WebView2-Laufzeit. Python-REST-Tests verwenden synthetische Antworten und ersetzen keine Live-Verbindung.

Die integrierten Regressionen prüfen insbesondere: transaktionale Cache-Persistenz vor Fortschreiben des Synchronisationszeitpunkts, Delta-Refresh, History-Nachladen erst bei Bedarf, Wiederverwendung von History und fehlende Historie als unbekannt statt Null. Wiederholte Navigation verursacht keine zusätzlichen REST-Ticketabfragen.

Die Browserprüfungen umfassen Anmeldung/Fehlerunterscheidung, Offline-Datenstand, alle Analysen, Timeline/Custom-Zeitraum/Snap, Typfilter, Agenten/Team, Ticketdetails, Export, Info, Logout sowie Navigation bei laufenden Anfragen. Größen: 1920×1080, 1050×650 und simulierte 125 % / 150 %. Diese Prüfungen verwenden kontrollierte IPC-Testdaten.

## Native Anwendung und PDF

Der integrierte Quellcode und die eingefrorene EXE wurden mit tatsächlichem WebView2 gestartet. Lokale React-Assets und die Bestätigung eines Python-Bridge-Ereignisses durch React wurden geprüft. Alle sieben Analyseadapter und Agentenadapter bestanden.

Im Quellcode-, EXE- und installierten Anwendungstest gelangen jeweils die beiden echten PDF-Flüsse: Management-Übersicht und Reaktionszeitanalyse. Qt-Module und Qt-DLLs waren im WebView-Hauptprozess vor und nach dem Export **nicht geladen**. PDF-Erzeugung erfolgt im separaten Worker. Die EXE-Prüfungen liefen mit Windows-Systempfaden ohne Python/Node auf PATH.

Eine native Anmeldung mit persönlichen Znuny-Zugangsdaten wurde nicht durchgeführt. Die automatisierte WebView-Probe bestätigt Start, Renderer, Bridge und Export, nicht die fachliche Richtigkeit realer Serverdaten.

## Aktuelle Artefakte

| Artefakt | Lokaler Pfad |
| --- | --- |
| Desktop-EXE | `dist/web/ParCom_Analytics_Web/ParCom Znuny Analytics.exe` |
| PDF-Worker | `dist/web/ParCom_Analytics_Web/pdf_worker/ParCom_PDF_Worker.exe` |
| Installer | `dist/release/ParCom_Znuny_Analytics_Setup_1.0.0.exe` |
| Prüfsummen | `dist/release/SHA256SUMS.txt` |

Die EXE benötigt die angrenzenden Laufzeitordner. Der Installer enthält die gesamte Verteilung. Kein Python/Node für Endbenutzer erforderlich; WebView2 Evergreen muss vorhanden sein. Version 1.0.0, Herausgeber Nico Köchli. Unsigned, keine öffentliche Veröffentlichung.

- EXE SHA256: `b6ed67499240ef61233d971cfa5ee1b0b8b7fa17ae138171ccb0f57fc0f61b6a`
- Installer SHA256: `d6b85d960e7888849bc46774bffaa25a15fd9ee82e137871c8b5fd56854157fa`
- Installergröße: 100.737.943 Bytes.

Der in Phase 11 neu erzeugte Frontend-Build ist bytegleich mit den Assets in diesem Bundle. Seit dem Paketbau wurden ausschliesslich Dokumentations- und Testhilfen geändert.

## Installer und Uninstaller

`scripts/check_installer.ps1` kompiliert die gleiche Konfiguration und den gleichen Inhalt mit einer separaten AppId. Dadurch bleiben die vorhandene Installation und deren Registrierung unangetastet. Tatsächlich bestanden:

1. Fehlende WebView2-Laufzeit simuliert: Installation stoppt vor Dateikopie und Registrierung, deutscher Hinweis auf Microsoft-Download.
2. Installation für aktuellen Benutzer in gewählten Testpfad.
3. Desktop- und Startmenü-Verknüpfungen zeigen auf die richtige EXE; Apps-Eintrag enthält Version und Herausgeber.
4. Erneute Installation entfernt absichtlich eingesetzte veraltete Runtime-Dateien und die alte EXE; fremde Datei und lokale Anwendungsdaten bleiben erhalten.
5. Installierte EXE startet, beide PDFs werden erzeugt; kein Qt im Host.
6. Deinstallation entfernt verwaltete Dateien, Verknüpfungen und Apps-Eintrag.
7. LocalAppData und nicht verwaltete Datei bleiben erhalten; eigene Testmarkierungen danach entfernt.
8. Registrierung der bestehenden Benutzerinstallation unverändert.

Der erste Test prüfte vor Abschluss des Inno-Hilfsprozesses. Die Prüfung wartet nun begrenzt auf dessen Bereinigung; der vollständige zweite Durchlauf bestand. Der reale WebView2-Registry-Eintrag wurde nicht verändert. Erkennung folgt der [Microsoft-Dokumentation](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution).

**Grenzen:** Kein Upgrade/Uninstall der vorhandenen produktiven Installation, kein Test auf frischem Windows, keine All-Users-Abnahme und keine tatsächliche Runtime-Neuinstallation. Die isolierte AppId prüft die Installer-Logik ohne Eingriff in die bestehende Benutzerinstallation.

## Performance

Synthetische Messungen des integrierten Performance-Branches, 40 Tickets / 20 ms künstliche Anfragelatenz:

| Szenario | Vorher | Optimiert |
| --- | ---: | ---: |
| Erstladung | 1,870 s | 0,469 s |
| Unveränderter Refresh | 1,853 s | 0,207 s |
| Vier geänderte Tickets | 1,856 s | 0,230 s |

HTTP-Verbindungswiederverwendung, maximal vier gleichzeitige Anfragen, Deduplizierung, Ticketcache, Delta-Refresh und verzögerte History sind integriert. Diese Werte sind **keine realen Znuny-Messungen**. TicketSearch-/TicketGet-/History-Laufzeiten und tatsächliche Produktionslast sind weiterhin offen. Details: [PERFORMANCE.md](PERFORMANCE.md).

## Dokumentation und Hygiene

Die deutsche README beschreibt den integrierten Stand, enthält zehn verifizierte Stack-Badges und sechs visuell geprüfte Screenshots mit 1600 px Breite (insgesamt ca. 1,05 MB). Aufnahmen zeigen den tatsächlichen React-Produktionsbuild in Edge mit anonymen synthetischen Python-Daten. Keine echten Anmeldedaten, Kundeninhalte oder persönlichen Agentenidentitäten sind abgebildet. Es wurde keine Produktionslogik für die Aufnahmen verändert.

Der obsolete Remote-Branch `antigravity/version-1-0` war exakt gleich der unveränderten Basis und wurde nach Prüfung gelöscht; lokal war er bereits abwesend. Eigene temporäre Testinstallationen, Marker und entbehrliche Testdateien wurden entfernt. Prüfprotokolle bleiben ignoriert erhalten. Kein XLSX/PDF/Cache/Settings-/Environment-Datensatz wurde eingecheckt. Der alte PySide-Fallback bleibt bis zur vollständigen Live-Abnahme erhalten.

## Lokale Prüfnachweise

- `.validation/integration-final-python.log`
- `.validation/integration-source.json`
- `.validation/web-bundle-1a5ea5491baf4f68a5a00b93dccf3288.json`
- `.validation/installer-5e5e5c487fd945f2a5bfdf01d5198493/result.json`
- `.validation/installer-build.log`

Diese ignorierten Dateien sind lokale Nachweise, keine öffentlich verfügbaren Repository-Dateien.

## Offene Freigabeschritte

1. Persönliche Anmeldung direkt in der Anwendung und fachlicher Vergleich mit Znuny: PBX/PBX Intern, Typen/Unclassified, Status, Kunde 00325, Agentenhistorie, Ticketdetails/Links, Refresh, PDF und Logout. Keine Zugangsdaten im Chat nötig.
2. Reale REST-Zeitmessung für Erstladung, unveränderten und gegebenenfalls geänderten Refresh.
3. Frische Windows-Umgebung und tatsächlicher DPI-Wechsel; All-Users-Installation und WebView2-Voraussetzung dort abnehmen.
4. Lizenzfreigabe und vollständige Drittkomponentenhinweise vor externer Produktionsveröffentlichung klären; derzeit keine eigene LICENSE-Datei. Der Build ist weiterhin nicht signiert.

**Phase 12 bleibt gesperrt:** Kein Main-Merge, kein Tag v1.0.0 und kein GitHub Release. Ein Push auf codex/integration liefert Quellcode und Dokumentation; er veröffentlicht keinen Installer-Download. Nach Vorliegen der fehlenden Abnahme gezielt hier fortsetzen, abgeschlossene Integration nicht wiederholen.
