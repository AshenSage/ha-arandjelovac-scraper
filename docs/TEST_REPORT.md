# Prüfbericht · Aranđelovac Live 1.2.2

Stand: 14.10.2026. Geprüftes Laufzeitziel: Home Assistant Core 2026.10.1, Python 3.14.2.

## Ausgeführte Prüfungen

| Ebene | Ergebnis |
|---|---|
| Ursprüngliche EDS-/Transport-/Coordinator-Prüfungen | 109 Tests erfolgreich |
| Zusätzliche Quellen-, Datums-, Status-, Programm- und Budgetprüfungen | 50 Tests erfolgreich |
| Gesamte Offline-Python-Suite | 159 Tests erfolgreich |
| Reale HA-Core-Tests | 13 Tests erfolgreich |
| Chromium-Karte | 219 Assertions erfolgreich, keine JavaScript-Fehler |
| Bildschirmbreiten | 320, 440 und 736 px, jeweils helles, dunkles und grünes Theme |
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

Version 1.2.2 ergänzt die Prüfung aller verwendeten Icon-Namen gegen den tatsächlich mit HA 2026.10.1 ausgelieferten MDI-Katalog. `road-barrier` fehlt darin; das verwendete `road-variant` ist vorhanden. Neue Parserregressionen prüfen lateinische und kyrillische Strecken-/Ortsangaben, fehlende Strecken ohne Erfindung, Veranstaltungsarten und Einzeltermine ohne wiederholten Wochenplan. Die öffentlich erfassten Originalantworten vom 14.10. wurden zusätzlich lokal erneut mit den geänderten Parsern und Attributlimits geprüft.

Die 219 Browserprüfungen umfassen drei Themes mit drei Breiten sowie Warnungen auf normaler Kartenfläche, Verkehrsfrist und Ortsangabe, abgelaufene Fristen ohne behauptete Freigabe, Vorrang einer Unterbruchsmeldung vor Bildhinweisen und die Quellenzählung. Für die Quellenstatus-Texte wurde ein Kontrast von mindestens 4.5:1 und für die Erfolgsicons mindestens 3:1 in den geprüften Paletten gemessen. Diese Messung deckt die drei Testpaletten ab, nicht beliebige HA-Themes. Screenshots für geschlossene und geöffnete Karten werden als CI-Artefakt gespeichert.

## Nach Installation noch ausstehend

Für 1.2.1 bestätigen die vom Nutzer gezeigten Smartphone-Screenshots eine geladene Karte nach manueller Ressourcenregistrierung und sechs erfolgreiche Quellenabrufe. Die Abnahme der Änderungen aus 1.2.2 auf dem tatsächlichen HA-System steht aus. Es wurde keine Verbindung zu seiner produktiven HA-Instanz hergestellt und dort nichts geändert.

RSS-Ausschnitte bleiben begrenzt; Bildbeiträge werden nicht per OCR gelesen. Kein Artikelstatus ersetzt eine Messung der Versorgung im Haus. Diese fachlichen Grenzen werden in Karte und README ausdrücklich ausgewiesen.
