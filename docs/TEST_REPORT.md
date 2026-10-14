# Prüfbericht · Aranđelovac Live 1.2.1

Stand: 14.10.2026. Geprüftes Laufzeitziel: Home Assistant Core 2026.10.1, Python 3.14.2.

## Ausgeführte Prüfungen

| Ebene | Ergebnis |
|---|---|
| Ursprüngliche EDS-/Transport-/Coordinator-Prüfungen | 109 Tests erfolgreich |
| Zusätzliche Quellen-, Datums-, Status- und Budgetprüfungen | 44 Tests erfolgreich |
| Gesamte Offline-Python-Suite | 153 Tests erfolgreich |
| Reale HA-Core-Tests | 12 Tests erfolgreich |
| Chromium-Karte | 88 Assertions erfolgreich, keine JavaScript-Fehler |
| Bildschirmbreiten | 320, 440 und 736 px, jeweils helles und dunkles Theme |
| Struktur/Syntax | Python compileall, JavaScript node --check, JSON, Versionsabgleich und Paketstruktur erfolgreich |
| Live-Quellen | Alle sechs Provider verfügbar; Details in live-verification.json |

Die zusätzlichen Quellentests verwenden reduzierte synthetische Beispiele entsprechend den untersuchten öffentlichen Strukturen. Die vollständigen Originalantworten neuer Artikel sind keine öffentlichen Repository-Fixtures. Die bestehenden EDS-Fixtures wurden aus dem früheren Paket übernommen.

## HA-Core-Prüfungen

Die Prüfungen verwenden den echten HA Core und seine offiziellen Test-Fixtures, keine nachgebaute Entity Registry. Upstream-HTTP wird für reproduzierbare Laufzeittests ersetzt; ein separater Live-Test prüft die tatsächlichen Quellen.

Geprüft: UI-/Import-Flow, sechs getrennte Einträge, Nachrüsten fehlender Quellen bei vorhandenem EDS, doppelte Konfiguration, Sensorplattform und zwölf Entitäten, echte Registry-Unique-IDs, Fehler nach Erfolg, Diagnose bei unavailable, Reload/Unload, Quellenisolation, Options Flow, tatsächliche HTTP-Auslieferung der Karten-Datei sowie Registrierung des Frontendmoduls.

Der echte Laufzeittest zeigte, dass HA bei unavailable normale Extra-Attribute ausblendet. Deshalb ergänzt Version 1.2.0 pro Quelle einen stets lesbaren Diagnose-Sensor. Der Hauptsensor behält echte HA-Verfügbarkeit. Die Karte wird auch gegen genau diesen Fehlerzustand getestet.

## Browser-Prüfungen

Getestet mit Chromium: Darstellung in zwei Themes und drei Breiten, aufklappbare Bereiche, Erhalt geöffneter Kacheln bei Zustandsupdates, der Titel Veranstaltungen & News, Quellenzählung, Quellenausfall, Diagnose bei fehlenden Hauptsensorattributen und Escaping fremder Texte/URLs. Bei keiner geprüften Breite tritt horizontales Überlaufen auf.

Im isolierten Browser sind HA-eigene Icons Platzhalter; im laufenden HA stellt ha-icon die Symbole bereit. Die Karte selbst benötigt keine externen JavaScript-Bibliotheken.

Für 1.2.1 wurde der Startup-Fehler mit der echten `@webcomponents/scoped-custom-element-registry`-Polyfill-Version 0.0.10 reproduziert: Die unveränderte 1.2.0-Karte ist nach dem Registry-Wechsel nicht mehr über `customElements.get` auffindbar. Der neue Regressionstest scheitert damit beim Warten auf die Karte. Mit der Korrektur bestehen drei Ladereihenfolgen (vor dem Polyfill, nach dem Polyfill vor dem HA-Element, nach dem HA-Element), Konstruktion gegen die aktive HTMLElement-Klasse und doppeltes Laden als Modul/Ressource. Die 88 Assertions beinhalten diese neun neuen Prüfungen. Die Polyfill-Abhängigkeit wird ausschliesslich im Browsertest verwendet, nicht im ausgelieferten Kartenmodul.

## Nach Installation noch ausstehend

Die Abnahme auf Nenads tatsächlichem HA-System und Smartphone steht aus. Zu prüfen sind HACS-Download, HA-Neustart, sechs Quellenstatus, bestehendes Dashboard-Theme und App-Cache. Es wurde keine Verbindung zu seiner produktiven HA-Instanz hergestellt und dort nichts geändert.

RSS-Ausschnitte bleiben begrenzt; Bildbeiträge werden nicht per OCR gelesen. Kein Artikelstatus ersetzt eine Messung der Versorgung im Haus. Diese fachlichen Grenzen werden in Karte und README ausdrücklich ausgewiesen.
