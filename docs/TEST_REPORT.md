# Prüfbericht · Aranđelovac Live 1.5.0

Stand: 20.10.2026. Ziel: HA Core 2026.10.1, Python 3.14.8.

- 187 Offline-Python-Tests: erfolgreich, einschliesslich Regressionen für Kategorien-/Ortsabdeckung, Folgeseiten, Änderungen im selben Wasserartikel, spätere Reparaturmeldungen, verneinte/erwartete Entwarnungen und abgelaufene Planfenster.
- 20 Tests mit echtem HA Core 2026.10.1: erfolgreich, einschliesslich neuer Quelle, Options Flow mit allen Gemeindekategorien und `partial`-Status.
- 737 Chromium-Assertions: erfolgreich in drei Themes bei 320, 440 und 736 px; keine JavaScript-Fehler.
- Syntax, Paket- und Versionsprüfung: erfolgreich.
- Quellenabruf verwendet die tatsächlich ausgelieferten Provider. Metadaten des aktuellen Abgleichs stehen in `live-verification.json`; fremde Artikelvolltexte werden nicht veröffentlicht.

Die Reparaturabschlussmeldung vom 22.09. wird als abgeschlossene Reparatur gelesen. Sie bestätigt keine aktuelle Wasserversorgung; die frühere Störung bleibt entsprechend als historisch/unbestätigt getrennt. Das ist eine bewusste fachliche Grenze. Undatierte Museumsangebote werden nicht zu neuen Veranstaltungen oder Veröffentlichungen umgedeutet.

Live-Prüfung 20.10.2026, 07:41 Europe/Belgrade: neun Quellen verfügbar; die Bibliothek antwortete mit HTTP 503 und wird korrekt als unbekannt/nicht verfügbar statt als Null dargestellt. Verkehr: 3, Gemeinde: 7, lokale Arbeiten: 5, undatierte Museumsangebote: 4. Produktive Installation und Zustandsprüfung erfolgen nach erfolgreicher CI-Freigabe.

---

## Historische Prüfberichte bis 1.4.0


Stand: 14.10.2026. Geprüftes Laufzeitziel: Home Assistant Core 2026.10.1, Python 3.14.2.

## Ausgeführte Prüfungen

| Ebene | Ergebnis |
|---|---|
| Ursprüngliche EDS-/Transport-/Coordinator-Prüfungen | 109 Tests erfolgreich |
| Zusätzliche Quellen-, Datums-, Status-, Programm- und Budgetprüfungen | 59 Tests erfolgreich |
| Gesamte Offline-Python-Suite | 168 Tests erfolgreich |
| Reale HA-Core-Tests | 17 Tests erfolgreich |
| Chromium-Karte | 727 Assertions erfolgreich, keine JavaScript-Fehler |
| Bildschirmbreiten | 320, 440 und 736 px, jeweils helles, dunkles und grünes Theme |
| Struktur/Syntax | Python compileall, JavaScript node --check, JSON, Versionsabgleich und Paketstruktur erfolgreich |
| Live-Quellen | Alle neun Provider verfügbar; Details in live-verification.json |

Die zusätzlichen Quellentests verwenden reduzierte synthetische Beispiele entsprechend den untersuchten öffentlichen Strukturen. Die vollständigen Originalantworten neuer Artikel sind keine öffentlichen Repository-Fixtures. Die bestehenden EDS-Fixtures wurden aus dem früheren Paket übernommen.

## HA-Core-Prüfungen

Die Prüfungen verwenden den echten HA Core und seine offiziellen Test-Fixtures, keine nachgebaute Entity Registry. Upstream-HTTP wird für reproduzierbare Laufzeittests ersetzt; ein separater Live-Test prüft die tatsächlichen Quellen.

Geprüft: UI-/Import-Flow, neun getrennte Einträge, Nachrüsten fehlender Quellen bei vorhandenem EDS, doppelte Konfiguration, Sensorplattform und 18 Entitäten, echte Registry-Unique-IDs, Fehler nach Erfolg, Diagnose bei unavailable, Reload/Unload, Quellenisolation, Options Flow, tatsächliche HTTP-Auslieferung der Karten-Datei sowie Registrierung des Frontendmoduls.

Der echte Laufzeittest zeigte, dass HA bei unavailable normale Extra-Attribute ausblendet. Deshalb ergänzt Version 1.2.0 pro Quelle einen stets lesbaren Diagnose-Sensor. Der Hauptsensor behält echte HA-Verfügbarkeit. Die Karte wird auch gegen genau diesen Fehlerzustand getestet.

## Browser-Prüfungen

Getestet mit Chromium: Darstellung in drei Themes und drei Breiten, aufklappbare Bereiche, Erhalt geöffneter Kacheln bei Zustandsupdates, die klaren Bereiche für Versorgung, Veranstaltungen und Gemeinde, Quellenzählung, Quellenausfall, Diagnose bei fehlenden Hauptsensorattributen und Escaping fremder Texte/URLs. Bei keiner geprüften Breite tritt horizontales Überlaufen auf.

Im isolierten Browser sind HA-eigene Icons Platzhalter; im laufenden HA stellt ha-icon die Symbole bereit. Die Karte selbst benötigt keine externen JavaScript-Bibliotheken.

Für 1.2.1 wurde der Startup-Fehler mit der echten `@webcomponents/scoped-custom-element-registry`-Polyfill-Version 0.0.10 reproduziert: Die unveränderte 1.2.0-Karte ist nach dem Registry-Wechsel nicht mehr über `customElements.get` auffindbar. Der neue Regressionstest scheitert damit beim Warten auf die Karte. Mit der Korrektur bestehen drei Ladereihenfolgen (vor dem Polyfill, nach dem Polyfill vor dem HA-Element, nach dem HA-Element), Konstruktion gegen die aktive HTMLElement-Klasse und doppeltes Laden als Modul/Ressource. Die 88 Assertions beinhalten diese neun neuen Prüfungen. Die Polyfill-Abhängigkeit wird ausschliesslich im Browsertest verwendet, nicht im ausgelieferten Kartenmodul.

Version 1.2.2 ergänzt die Prüfung aller verwendeten Icon-Namen gegen den tatsächlich mit HA 2026.10.1 ausgelieferten MDI-Katalog. `road-barrier` fehlt darin; das verwendete `road-variant` ist vorhanden. Neue Parserregressionen prüfen lateinische und kyrillische Strecken-/Ortsangaben, fehlende Strecken ohne Erfindung, Veranstaltungsarten und Einzeltermine ohne wiederholten Wochenplan. Die öffentlich erfassten Originalantworten vom 14.10. wurden zusätzlich lokal erneut mit den geänderten Parsern und Attributlimits geprüft.

Die 219 Browserprüfungen umfassen drei Themes mit drei Breiten sowie Warnungen auf normaler Kartenfläche, Verkehrsfrist und Ortsangabe, abgelaufene Fristen ohne behauptete Freigabe, Vorrang einer Unterbruchsmeldung vor Bildhinweisen und die Quellenzählung. Für die Quellenstatus-Texte wurde ein Kontrast von mindestens 4.5:1 und für die Erfolgsicons mindestens 3:1 in den geprüften Paletten gemessen. Diese Messung deckt die drei Testpaletten ab, nicht beliebige HA-Themes. Screenshots für geschlossene und geöffnete Karten werden als CI-Artefakt gespeichert.

## Nach Installation noch ausstehend

Für 1.2.1 bestätigen die vom Nutzer gezeigten Smartphone-Screenshots eine geladene Karte nach manueller Ressourcenregistrierung und sechs erfolgreiche Quellenabrufe. Die späteren Smartphone-Screenshots bestätigen auch die Darstellung von 1.2.2. Die weiteren Smartphone-Screenshots vom 14.10.2026 bestätigen Version 1.3.0 mit neun erreichbaren Quellen, einer datierten Lesung, einer getrennten Theaterankündigung und den Saisonhinweisen ohne Kino. Die folgenden Screenshots bestätigen auch die Textaufklappung und Veranstaltungsicons von 1.3.1. Die produktive Abnahme von Version 1.4.0 steht noch aus. Es wurde keine Verbindung zu seiner produktiven HA-Instanz hergestellt und dort nichts geändert.

RSS-Ausschnitte bleiben begrenzt; Bildbeiträge werden nicht per OCR gelesen. Kein Artikelstatus ersetzt eine Messung der Versorgung im Haus. Diese fachlichen Grenzen werden in Karte und README ausdrücklich ausgewiesen.

## Veranstaltungen ohne Kino · Version 1.3.0

Kino wird vor der Auswahl der Kartenanzeige ausgefiltert, einschliesslich älterer Einträge ohne `event_type`. Ein Filmprogramm mit mehr als 20 Vorstellungen verdrängt keine vorhandene Kulturankündigung aus dem Sensorbudget. In der Veranstaltungskarte gilt das bisherige Acht-Einträge-Limit nicht mehr; alle geladenen Nicht-Kino-Einträge werden angezeigt. Die Quellenzählung der Hauptsensoren bleibt erhalten.

Neue Regressionen prüfen datierte Termine ohne Uhrzeit, vergangene Termine, Anmeldefristen, Lesungen, Saisonhinweise ohne erfundenes Jahr, Kinoausblendung, Sichtbarkeit nach dem achten Eintrag und den Monatswechsel bei der Terminvorschau. Die 294 Browserprüfungen laufen in drei Themes und drei Breiten; ein Kartenlimit von 1 blendet andere geladene Veranstaltungen nicht aus.

Der echte HA-Upgrade-Test ergänzt ausschliesslich Museum, Bibliothek und Feste/Basare zu den sechs vorhandenen Quellen. Die bestehenden ConfigEntry-Objekte bleiben erhalten. Einrichtung aller neun Quellen, 18 Sensoren und Ausfall einer einzelnen Quelle werden ebenfalls im echten HA Core geprüft.

Die drei zusätzlichen öffentlichen Quellen wurden mit dem produktiven HTTP- und Parserpfad live geprüft: Museum liefert aktuell keine Meldung im konfigurierten Zeitraum; die Bibliothek einen Termin am 15.10.2026 um 19:00; die Tourismusübersicht 13 allgemeine Saisonhinweise. Das sind Momentaufnahmen des Abrufs vom 14.10.2026, kein Anspruch auf einen vollständigen lokalen Veranstaltungskalender. Rohantworten bleiben lokale Recherchedateien; der veröffentlichte Bericht enthält Abrufmetadaten statt vollständiger fremder Artikel.


## Kompakte Anzeige und Veranstaltungsicons · Version 1.3.1

473 Browser-Assertions prüfen weiterhin drei Themes und die Breiten 320, 440 und 736 px. Neu abgedeckt sind die eigene geschlossene Saisonübersicht, das unabhängige Öffnen dieser Liste, deutsche Saisonmonate einschliesslich kyrillischer Monatsangaben und weiterhin fehlende erfundene Jahreszahlen. Veröffentlichungsdaten von Ankündigungen und Gemeindemeldungen werden ausdrücklich als solche bezeichnet.

Lange Texte werden per nativem Details-Element geöffnet und geschlossen; die Vorschau zeigt weder die wiederholte Überschrift noch den gesamten Text. Tastaturbedienung mit Enter, der Wechsel zwischen Mehr/Weniger anzeigen sowie der Erhalt der geöffneten Text- und Saisonbereiche bei neuen Sensorständen und erzwungenem Minutenrendern werden tatsächlich im Browser ausgeführt. Fremde HTML-Fragmente in langen Texten und Datensatz-IDs bleiben auch nach dem Öffnen Text; unsichere Links werden nicht ausgegeben.

Alle sechs Veranstaltungsarten erhalten unterschiedliche Symbole. Der Hauptbereich wechselt beim nächsten Theatertermin bzw. Markttermin zum passenden Icon. Ein Test im realen HA Core prüft sämtliche verwendeten MDI-Namen gegen den ausgelieferten Katalog. Eine zusätzliche lokale Sichtprüfung verwendet dessen tatsächliche SVG-Pfade mit erfassten Quelldaten im grünen Theme; weder die geschlossene Karte noch geöffnete Veranstaltungs-, Saison-, Nachrichten- oder Quellenbereiche laufen bei den drei geprüften Breiten horizontal über.

Die unveränderte Python-Suite besteht mit 168 Tests, die reale HA-Suite mit 17 Tests. Versionsabgleich, Paketprüfung und Python-/JavaScript-Syntaxprüfung bestehen ebenfalls. Diese Version ändert ausschliesslich die Darstellung und die Paketversion; ein erneuter Live-Abruf der unveränderten Quellenparser ist dafür nicht erforderlich. Die vorhandenen Live-Ergebnisse sind weiterhin mit ihrem tatsächlichen Abrufzeitpunkt dokumentiert.


## Veranstaltungsreiter und Kalenderdatum · Version 1.4.0

Die freigegebene Reiteransicht ist in der tatsächlich ausgelieferten HA-Karte umgesetzt. Die 727 Chromium-Assertions decken drei Themes und 320, 440 und 736 px ab. Geprüft werden die Anzahlen und Inhalte aller drei Reiter, der vollständige Kinofilter, die Sichtbarkeit nach dem achten geladenen Eintrag auch mit `max_items: 1`, Kalenderdatum und Wochentag sowie Termine ohne erfundene Uhrzeit.

Die Tests bedienen die Oberfläche mit Klicks, Enter, Pfeiltasten und Pos1/Ende. Auswahl, native Detailzustände und Fokus bleiben bei realen Sensoränderungen und erzwungener Minutenaktualisierung erhalten. Eine zweite Karte besitzt eine unabhängige Auswahl. Leere Kategorien und ein erster Datenstand ohne datierte Veranstaltung werden ebenfalls geprüft.

Die Datumsprüfungen erfassen den Monatswechsel, einen UTC-Zeitpunkt nach Mitternacht in Europe/Belgrade, den lokalen Tageswechsel, vergangene Datumstermine, bereits beendete Veranstaltungen und einen heute vergangenen Beginn ohne bekanntes Ende. Diese Fälle werden mit einer festen Browseruhr geprüft; die tatsächliche Minutenaktualisierung erfordert keine weitere Quellenabfrage. Allgemeine Saisonmonate, kyrillische Monatsangaben, Monatsspannen und numerische Saisonangaben werden ohne erfundenes Jahr ausgegeben.

Bei Teilausfall bleibt die fehlende Quelle sichtbar. Bei Ausfall aller Veranstaltungsquellen steht die Anzahl auf unbekannt, nicht auf null. Fremde Titel, lange Texte, Datensatz-IDs und Links werden auch nach dem Öffnen der Veranstaltungsdetails auf Escaping und sichere Links geprüft.

Die Quellenstatus-Texte und die ausgewählten Reiter erreichen in den drei geprüften Paletten mindestens 4.5:1 Kontrast, die Erfolgsicons mindestens 3:1. Die Beschriftungen der drei Reiter passen bei jeder geprüften Breite ohne horizontales Überlaufen. Eine lokale Sichtprüfung mit den echten HA-MDI-SVGs und zuvor erfassten Quelldaten bestätigt die Reiteransicht sowie geöffnete Termin-, Saison- und Quellenbereiche. Diese Aufnahme ist eine lokale Datenwiedergabe, keine Verbindung zur produktiven HA-Instanz.

Die 168 Python-Prüfungen und alle 17 realen HA-Core-Prüfungen bestehen. Der HTTP-Laufzeittest verifiziert die aktualisierte Karten-Datei mit Reitern und Kalenderdarstellung. Die Quellenparser und Abfrageintervalle bleiben unverändert; es wurde für dieses Darstellungsupdate kein neuer Live-Quellenabruf als erforderlich ausgegeben.
