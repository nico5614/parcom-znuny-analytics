# Prüfstand Version 1.0

Stand: 6. Oktober 2026. Branch: `codex/version-1-0`.

**Prüfbuild, noch keine Produktionsfreigabe.**

## Implementiert

- Version 1.0 / 1.0.0 / Windows-Dateiversion 1.0.0.0, Herausgeber Nico Köchli.
- Lesender REST-Client für SessionCreate, SessionDelete, TicketSearch und TicketGet Extended=1; festes HTTPS-Ziel und PBX-Queues.
- Persönlicher Login, nichtpersistente Zugangsdaten, Hintergrundjobs, Verbindungsstatus, Reconnect und best-effort Logout beim Schliessen.
- Gemeinsame Excel-/Live-Berechnungen für KPI 1–7, inklusive Nullwerten, unbekannten Werten und Zeitraumbegrenzung.
- Offline-Cache, ausschliesslich aggregierte historische Live-Daten, keine erfundenen historischen Snapshots.
- Unveränderte Score-Formel, Management-Übersicht und unabhängige Berichte.
- Dark Mode, maximierter Start, skalierbare Layouts, abschaltbare Qt-Animationen, vorhandenes Logo und Windows-Icon.
- Qt-PDFs, datensparsamer Management-Bericht, lokale Datensatzverwaltung und Löschbestätigung.
- PyInstaller-onedir-Build und dunkler Inno-Setup-Installer mit Pfadwahl, optionalem Desktop-Symbol und Uninstaller ohne Löschung der Anwendungsdaten.

## Verifiziert

- Bestehender Ausgangsstand: 150 Tests bestanden; ursprüngliche Anwendung vor Änderungen gestartet.
- Erweiterte Testsuite: 200 Tests bestanden unter Python 3.14.8, einschliesslich REST-Mocks, Fehlerfällen, Sitzungsende, Cache-Schreibfehlern und Datenschutz.
- PySide6 6.11.2, PyInstaller 6.22.3, Inno Setup 7.1.0. Exakte Python-Abhängigkeiten in `requirements-lock.txt`.
- Native Qt-Anwendung unter Windows gestartet: maximierte Login-Seite, Navigation, Leerzustände, alle sieben KPIs, drei synthetische Monatsstände, Score und Persistenz.
- Layoutgrössen 1050 × 650, maximierte 1920er Arbeitsfläche und auf 2560 × 1440 vergrösserte Widgets geprüft. Der letzte Punkt ist kein Test auf einem physischen 2560er Monitor.
- Sieben KPI-PDFs und ein Management-PDF erzeugt und gerendert. Repräsentative Kennzahl-, Diagramm-, Verlaufs- und Tabellenseiten visuell geprüft; automatisierte Tests vergleichen Kennzahlen und prüfen den Ausschluss von Ticketdetails im Management-Bericht.
- Darstellungsfehler durch dauerhafte Qt-Opacity-Effekte behoben; Tabellen nach Animation erneut visuell geprüft.
- Korrigierte Exporte mit gleichem Zeitstempel verwenden konsistent den letzten Import; Regressionstest vorhanden.
- Unbekannte Eskalationsfelder werden separat dargestellt und verhindern einen scheinpräzisen Performance Score.
- Installer erfolgreich kompiliert. Dunkles Installerfenster mit Versionsanzeige und änderbarem Installationspfad wurde geöffnet und visuell geprüft.

## Noch nicht abgenommen

1. Echte persönliche Anmeldung an `znuny.parcom.ch`, tatsächliches REST-Mapping, Berechtigungen sowie Abgleich der Live-Zahlen mit Znuny. Es wurden keine persönlichen Zugangsdaten bereitgestellt; automatisierte Tests nutzen ausschliesslich synthetische Antworten.
2. Vollständiger interaktiver Installationslauf einschliesslich Desktop-/Startmenü-Verknüpfungen, Windows-Apps-Eintrag, Deinstallation und Neuinstallation. Die Computer-Use-Bedienung wurde vom Benutzer mit Escape beendet; danach keine weiteren Computer-Use-Aktionen.
3. Ausführung auf einem sauberen Windows-System ohne Entwicklungsumgebung. Ein Test auf diesem Entwicklungsrechner ersetzt das nicht.
4. Code Signing: Metadaten sind gesetzt, es wurde kein Zertifikat bereitgestellt. Windows kann einen unbekannten Herausgeber beziehungsweise SmartScreen anzeigen.

## Veröffentlichung

Der überprüfte Quellcode wird auf dem Entwicklungsbranch gesichert. `main` bleibt unverändert, es wird kein Tag `v1.0.0` und kein Produktionsrelease erstellt. Keine Branches werden gelöscht. Der Implementierungsauftrag erlaubt diese Schritte erst nach vollständiger realer und manueller Abnahme.

Der aktuelle lokale Prüf-Installer wird unter `dist/review/ParCom_Znuny_Analytics_Setup_1.0.0.exe` gebaut; die Prüfsumme steht daneben in `SHA256SUMS.txt`. Er enthält Python und Laufzeitbibliotheken. Die frühere Datei unter `dist/release` gehört zur begonnenen Installerprüfung und ist nicht der letzte Prüfstand.

Ein Code-Push lädt den Installer nicht automatisch als GitHub-Release-Asset hoch. Nach abgeschlossener Abnahme ist genau eine Setup-Datei zum Herunterladen und Installieren ausreichend.

## Paketsicherung vom 7. Oktober 2026

Der Build isoliert PATH von fremden Qt-/ICU-Bibliotheken. Ein automatischer Starttest der gepackten EXE mit leerem Anwendungsspeicher und ohne Python auf PATH muss vor Inno Setup bestehen. Dieser Test ist bestanden. Nach den ergänzten TLS-/REST-Korrekturen bestanden 27 gezielte Verbindungs- und Clienttests. Diese Quellcodekorrekturen werden beim abschliessenden Build eingebunden. Der neue Abschlussauftrag (Dashboard, Timeline, Datenkorrekturen und Agentenauswertung) ist noch in Bearbeitung; dieser Checkpoint ist keine Produktionsfreigabe.
