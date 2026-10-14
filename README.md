# Aranđelovac Live

Lokale Informationen für Home Assistant: geplante Stromabschaltungen, Wassermeldungen, Verkehr, Veranstaltungen und Gemeindemeldungen. Eine gemeinsame Dashboardkarte für das Smartphone mit den klar getrennten Bereichen **Versorgung & Verkehr**, **Veranstaltungen** und **Nachrichten aus der Gemeinde**.

## Installation mit HACS

Voraussetzung: **Home Assistant Core 2026.10.1 oder neuer**, HACS und Internetzugriff auf die öffentlichen Quellen. Geprüftes Laufzeitziel dieser Version: HA 2026.10.1. Keine API-Schlüssel, Konten, zusätzlichen Dienste oder nachzuinstallierenden Python-Pakete nötig.

1. In HACS oben rechts **Benutzerdefinierte Repositories** öffnen.
2. `https://github.com/AshenSage/ha-arandjelovac-scraper` hinzufügen, Kategorie **Integration**.
3. **Aranđelovac Live** herunterladen und Home Assistant vollständig neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Aranđelovac Live**.
5. **Komplettpaket · alle 9 Quellen** wählen. Es entstehen neun unabhängige Integrationseinträge. Bereits vorhandene Quellen werden übersprungen.
6. Nach Abschluss der Einrichtung die HA-Seite bzw. App einmal vollständig neu laden.
7. Im gewünschten Dashboard eine **manuelle Karte** hinzufügen:

```yaml
type: custom:arandjelovac-live-card
title: Aranđelovac Live
```

Die Integration liefert die Karte aus und meldet sie als zusätzliches Frontendmodul an. Kein Kopieren nach `www` und kein zweites HACS-Repository nötig. Falls die automatische Einbindung im verwendeten Frontend nicht greift, die unten genannte Dashboard-Ressource eintragen. Nach einem Python-Update HA neu starten; nach einem Kartenupdate auch den Browser neu laden.

Seit Version 1.2.1 wartet die Karte auf die HA-Oberfläche, bevor sie sich registriert. Das verhindert den bekannten Verlust früh geladener Custom Elements beim Wechsel der HA-Elementregistrierung.

Falls die Karte nach dem Neustart noch nicht erkannt wird:

1. Unter **Einstellungen → Geräte & Dienste** prüfen, ob **Aranđelovac Live** eingerichtet ist. Ein Download in HACS allein aktiviert die Integration noch nicht.
2. HA vollständig neu starten und anschliessend die HA-Seite beziehungsweise App neu laden.
3. Nur bei weiter bestehendem Fehler unter **Dashboards → Ressourcen** diese URL als **JavaScript-Modul** ergänzen: `/arandjelovac_live/arandjelovac-live-card.js?v=1.4.0`. Falls der Menüpunkt fehlt, im Benutzerprofil den erweiterten Modus einschalten.
4. Liefert dieselbe URL beim direkten Öffnen eine 404-Seite, ist die Integration noch nicht geladen. Dann zuerst die Integrationsseite und HA-Protokolle prüfen; eine Ressourcenregistrierung behebt keinen fehlenden HTTP-Pfad.

Bei einer bereits manuell eingetragenen Ressource deren URL nach dem Update auf `?v=1.4.0` ändern und die HA-Seite beziehungsweise App neu laden. Den bestehenden Eintrag bearbeiten, keine zweite Ressource hinzufügen. Die Karten-YAML und Entitäts-IDs bleiben erhalten.

Die Karte zeigt kompakte Verkehrszusammenfassungen mit ausdrücklich genannter Strecke, Ort und Frist. Warnungen verwenden einen farbigen Rand auf der normalen Kartenfläche. Wassertexte nennen Meldungen und weisen auf Bildbeiträge hin. Kino ist in der Dashboardkarte ausgeblendet. Theater, Konzerte, Ausstellungen, Lesungen und andere Kulturmeldungen bleiben sichtbar. Einzeltermine aus Programmen verlinken auf das Original, statt den gesamten Wochenplan zu wiederholen. **9/9 Quellen erreichbar** bezeichnet erfolgreiche, noch aktuelle Quellenabrufe und keine bestätigte Versorgung im Haus.

## Quellen und Sensoren

| Quelle | Inhalt | Hauptsensor |
|---|---|---|
| EDS | Geplante Abschaltungen in Opština Aranđelovac | `sensor.arandjelovac_eds_outages` |
| JKP Bukulja | Wasserinformationen, Unterbruchsmeldungen, Bildbeiträge | `sensor.arandjelovac_jkp_water` |
| Putevi Srbije | Veröffentlichte Meldungen für eingestellte Orte | `sensor.arandjelovac_putevi_traffic` |
| Opština | Neuigkeiten der Gemeinde | `sensor.arandjelovac_opstina_news` |
| Kulturzentrum | Termine und Vorankündigungen | `sensor.arandjelovac_kultura_events` |
| Tourismusorganisation | Veranstaltungsmeldungen | `sensor.arandjelovac_tourism_events` |
| Narodni muzej | Museumsprogramm und Kulturmeldungen | `sensor.arandjelovac_museum_events` |
| Bibliothek Sveti Sava | Lesungen und Bibliotheksprogramm | `sensor.arandjelovac_library_events` |
| Tourismus · Manifestacije | Feste, Basare und saisonale Hinweise ohne bestätigten Jahrestermin | `sensor.arandjelovac_manifestations_events` |

Jede Quelle besitzt zusätzlich einen Diagnose-Sensor `sensor.arandjelovac_<provider>_source` mit `ok` oder `error`, Fehlerdetails und letztem erfolgreichen Abruf. Provider-IDs: `eds`, `jkp`, `putevi`, `opstina`, `kultura`, `tourism`, `museum`, `library`, `manifestations`. Dadurch bleibt der Fehler in der Karte sichtbar, wenn HA die Attribute des Hauptsensors bei `unavailable` ausblendet. Die Karte findet die Sensoren automatisch, auch nach regulären Umbenennungen. Bei Bedarf lassen sie sich ausdrücklich zuordnen:

```yaml
type: custom:arandjelovac-live-card
title: Aranđelovac Live
max_items: 8
transliterate: true
entities:
  eds: sensor.arandjelovac_eds_outages
  jkp: sensor.arandjelovac_jkp_water
  putevi: sensor.arandjelovac_putevi_traffic
  opstina: sensor.arandjelovac_opstina_news
  kultura: sensor.arandjelovac_kultura_events
  tourism: sensor.arandjelovac_tourism_events
  museum: sensor.arandjelovac_museum_events
  library: sensor.arandjelovac_library_events
  manifestations: sensor.arandjelovac_manifestations_events
```

`transliterate: true` zeigt kyrillische Meldungen in lateinischer serbischer Schrift. Es ist keine Übersetzung. Originaltexte bleiben in den Sensorattributen und auf der Quellenseite erhalten. Maximal 20 Einträge pro Quelle innerhalb des Attributbudgets; Kürzungen werden gekennzeichnet. Bei Veranstaltungen erscheinen alle geladenen Einträge ausser Kino, in den Reitern **Termine**, **Vorschau** und **Feste**. Vergangene erkennbare Termine werden auch bei der lokalen Minutenaktualisierung ausgeblendet. `max_items` begrenzt nur die übrigen Bereiche. Die Hauptsensoren behalten ihre Quellenzählung einschliesslich Kino für vorhandene Automationen; die Kinoausblendung betrifft die Dashboardkarte. Andere Kulturmeldungen haben bei der Attributauswahl Vorrang vor Kinoterminen.

## Bedeutung und Grenzen der Anzeige

- **EDS:** Der Zustand zählt noch nicht abgelaufene veröffentlichte Einträge. Gefiltert wird ausschliesslich nach der Gemeinde, nicht allein nach dem EDS-Ogranak. Geprüfte Abdeckung und verkürzte Veröffentlichung werden ausdrücklich angezeigt. Ein gültiges Zeitfenster misst keinen Stromausfall im Haus.
- **Wasser:** Der Hauptsensor zählt Meldungen im Anzeigezeitraum, nicht gemessene Ausfälle. Bauarbeiten ohne angekündigten Unterbruch sind Informationen. Bildbeiträge bleiben als nicht automatisch ausgewertet sichtbar; es gibt keine OCR. Bei Meldungen ohne bestätigtes Ende wird kein Reparaturzeitpunkt erfunden. Nach drei Tagen werden solche Einträge als ältere Meldungen gekennzeichnet, ausdrücklich ohne Entwarnung.
- **Verkehr:** Standardfilter: Aranđelovac, Darosava, Ranilović. Quellenoptionen erlauben weitere Orte. Der Filter arbeitet mit Ortsnamen, nicht mit einem geografischen Radius. Eine abgelaufene veröffentlichte Frist bleibt als solche gekennzeichnet; das bestätigt keine Freigabe. Bildkoordinaten aus der Quellkarte werden nicht als GPS-Koordinaten ausgegeben.
- **Gemeinde:** Standardkategorie 47 (Neuigkeiten). Neueste 30 Veröffentlichungen dieser Kategorien, gefiltert auf den Anzeigezeitraum. Verlinkte PDFs, private Konten und Formulare werden nicht abgefragt.
- **Veranstaltungen:** Kulturzentrum, Tourismus, Museum und Bibliothek nutzen ihre aktuellen öffentlichen RSS-Ausschnitte. Das ist kein vollständiger Veranstaltungskalender. Kino ist in der Karte ausgeblendet, auch bei älteren Einträgen ohne Kategorie. Erkennbare Programmtage und Uhrzeiten werden getrennt erfasst. Bei bekanntem Datum ohne Uhrzeit wird keine Startzeit erfunden. Vergangene erkennbare Termine verschwinden; Ticketverkauf und Anmeldefristen werden nicht als Veranstaltungstermine ausgegeben. Unklare Kulturmeldungen bleiben getrennt von datierten Terminen sichtbar.
- **Feste und Basare:** Die zusätzliche öffentliche Tourismusübersicht wird als allgemeiner Veranstaltungskatalog eingelesen. Eine Angabe wie „decembar“ bestätigt keinen Termin im Dezember 2026. Solche Hinweise bleiben ausdrücklich als Saisonhinweis ohne bestätigten Jahrestermin gekennzeichnet. Verlinkte Detailseiten können ergänzende Angaben enthalten; diese Version liest die Übersichtsseite, nicht sämtliche Detailseiten oder Social-Media-Konten.
- **Quellenfehler:** Ein Hauptsensor wird `unavailable`; der zugehörige Quellenstatus bleibt mit Fehlerdetails lesbar. Ein Quellenfehler wird niemals als Nullzählung dargestellt. Jede Quelle aktualisiert unabhängig von den anderen.

Für Bukulja wird ausschliesslich die aktuelle öffentliche Meldungsseite mit ihren relevanten Artikeln verwendet. Keine API-, Login- oder Archivabfrage. Verlinkte Texte werden im Arbeitsspeicher maximal sechs Stunden wiederverwendet, danach neu gelesen. Ein Neustart stellt keine alten Quelldaten als aktuelle Wahrheit wieder her.

## Einstellungen und Intervalle

Unter **Geräte & Dienste → Aranđelovac Live → Quelle → Konfigurieren** lassen sich Anzeigezeitraum, Veranstaltungshorizont, Verkehrsorte bzw. Gemeindekategorien einstellen. EDS behält seine validierte Datumslogik.

| Quelle | Regulärer Abruf | Veraltet nach |
|---|---:|---:|
| EDS | 30 Min.; 15 Min. bei gültiger Teilabdeckung | 65 Min. |
| Bukulja | 15 Min. | 45 Min. |
| Putevi | 15 Min. | 45 Min. |
| Gemeinde | 60 Min. | 135 Min. |
| Kulturzentrum | 120 Min. | 255 Min. |
| Tourismus | 180 Min. | 375 Min. |
| Museum | 180 Min. | 375 Min. |
| Bibliothek | 180 Min. | 375 Min. |
| Feste und Basare | 360 Min. | 735 Min. |

Die lokale Minutenprüfung aktualisiert Ablauf und Quellenfrische ohne zusätzliche HTTP-Anfrage. Standard-Anzeigezeitraum: 30 Tage, Veranstaltungshorizont: 60 Tage. Fehler führen zu keinem sofortigen Retry-Sturm. Ein manueller Abruf ist über `homeassistant.update_entity` auf dem Hauptsensor möglich.

## Update von Version 1.3.x

In HACS auf **1.4.0** aktualisieren und HA neu starten. Die vorhandene manuelle Dashboard-Ressource auf `?v=1.4.0` ändern und die HA-Seite bzw. App neu laden. Bereits eingerichtete Quellen bleiben erhalten; der Einrichtungsdialog muss nicht erneut durchlaufen werden.

Die Veranstaltungskarte ist direkt sichtbar und nutzt drei Reiter mit Eintragszahl:

- **Termine:** Chronologisch nach veröffentlichtem Veranstaltungsdatum. Ein Kalenderblatt zeigt Tag, Monat und Wochentag; Uhrzeit und Titel stehen daneben. Ein Datum ohne Uhrzeit bleibt ausdrücklich ohne Uhrzeit.
- **Vorschau:** Kulturmeldungen und Ankündigungen ohne bestätigten Veranstaltungstermin. Das Veröffentlichungsdatum steht in den aufklappbaren Details, ausdrücklich als solches bezeichnet.
- **Feste:** Der allgemeine Saisonkatalog mit deutschen Monatskürzeln. Monatsspannen und Sommerangaben bleiben allgemeine Hinweise ohne erfundenen Jahrestermin.

Alle geladenen anderen Veranstaltungen bleiben über die Reiter erreichbar; Kino ist ausgeblendet. Eine einzelne Zeile öffnet Titel, Quellentext und Originalverweis. Veranstaltungsarten haben eigene Symbole. Der gewählte Reiter, geöffnete Einträge und der Tastaturfokus bleiben bei Daten- und Minutenupdates erhalten. Reiter lassen sich mit den Pfeiltasten sowie Pos1/Ende bedienen. Beim ersten Laden wird ein vorhandener Bereich gewählt; eine bewusst gewählte leere Kategorie bleibt bei späteren Updates ausgewählt.

Lange Wasser-, Verkehrs- und Gemeindetexte behalten **Mehr anzeigen / Weniger anzeigen**. Wiederholte vollständige Überschriften am Textanfang werden ausgeblendet. Veröffentlichungsdaten heissen **Veröffentlicht am**. Artikeltexte und Titel bleiben in der Quellsprache; `transliterate` steuert weiterhin nur die Schrift.

Quellenfehler werden unter dem Veranstaltungsbereich angezeigt. Wenn keine Veranstaltungsquelle verfügbar ist, zeigen die Reiter **–** anstelle einer vermeintlichen Nullzählung.

## Update von Version 1.2.x

Nach HACS-Update und HA-Neustart unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → Aranđelovac Live → Komplettpaket · alle 9 Quellen** wählen. Dadurch werden nur Museum, Bibliothek und Feste/Basare ergänzt. Die bisherigen sechs Einträge bleiben erhalten. Anschliessend die bestehende manuelle Dashboard-Ressource auf `?v=1.4.0` aktualisieren und die HA-Seite neu laden. Die Karten-YAML bleibt gültig.

## Update von Version 1.1.0

Der Integrationsordner und bestehende EDS-IDs bleiben `arandjelovac_live`. HACS kann den manuell installierten Ordner ersetzen. Bestehenden EDS-Eintrag behalten; danach erneut **Integration hinzufügen → Komplettpaket** wählen, um die acht fehlenden Quellen hinzuzufügen. Die neue Diagnose-Entität ergänzt den bestehenden Hauptsensor.

Falls noch das ältere Paket `eds_arandjelovac` installiert ist: zuerst den neuen EDS-Sensor prüfen, Karten/Automationen umstellen und die alte Integration anschliessend entfernen. Keine direkte Änderung an `.storage` vornehmen.

## Prüfen und Fehler melden

1. Unter **Entwicklerwerkzeuge → Zustände** die neun Hauptsensoren und Quellenstatus-Sensoren prüfen.
2. In der Karte **Quellen & Aktualität** aufklappen.
3. Bei Problemen unter **Geräte & Dienste → Aranđelovac Live → Quelle → Diagnosedaten herunterladen** die Diagnose holen.

Keine Meldung ist eine Information über den veröffentlichten Ausschnitt. Die Versorgung und Verkehrslage am konkreten Haus werden nicht gemessen.

Entwicklungsprüfungen:

```bash
python -m unittest discover -s tests -v
python -m pytest tests/ha -q
npm ci --ignore-scripts
npx playwright install chromium --only-shell
npm test
python tools/validate_package.py
```

Der unabhängige Live-Test greift nur mit ausdrücklichem Schalter auf die Quellen zu:

```bash
python tools/sources_probe.py --live
```

Die Option `--proxy-env` gilt ausschliesslich für Entwicklungsumgebungen mit vorgegebenem Proxy. Die laufende Integration verwendet die HA-HTTP-Session. Live-Captures gehören nicht ins öffentliche Repository.

Prüfstand und verbleibende Abnahme: [docs/TEST_REPORT.md](docs/TEST_REPORT.md). Die Smartphone-Screenshots bestätigen die bisherigen Versionen bis 1.3.1; die Darstellung von 1.4.0 wird nach Installation geprüft.
