# Aranđelovac Live 1.3.0

Kino ist aus der Dashboardkarte ausgeblendet. Andere Veranstaltungen und Kulturmeldungen werden vollständig innerhalb des geladenen Quellenausschnitts angezeigt und nicht mehr nach acht Einträgen abgeschnitten.

- Drei zusätzliche unabhängige Quellen: Museum, Bibliothek Sveti Sava und die Tourismusübersicht für Feste und Basare. Insgesamt neun Quellen und 18 Sensoren einschliesslich Quellenstatus.
- Getrennte Anzeige für veröffentlichte Termine, Kulturmeldungen/Ankündigungen und allgemeine Saisonhinweise.
- Ein Datum ohne Uhrzeit bleibt ein Datum ohne erfundene Startzeit. Vergangene erkennbare Termine werden entfernt; Ticketverkaufs- und Anmeldefristen werden nicht als Termine ausgegeben.
- Kinofilter auch für ältere Karten-Daten ohne Kategorie. Sonstige Kulturmeldungen haben beim Sensor-Attributbudget Vorrang vor Filmprogrammen. Die Quellenzählung der Hauptsensoren bleibt für vorhandene Automationen erhalten.
- Klarerer Wasserhinweis: „Teilweise als Bild verfügbar“.

## Aktualisieren

1. In HACS auf **1.3.0** aktualisieren und Home Assistant vollständig neu starten.
2. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Aranđelovac Live → Komplettpaket · alle 9 Quellen** wählen. Nur die drei fehlenden Quellen werden ergänzt; bestehende Einträge und Entitäts-IDs bleiben erhalten.
3. Die vorhandene manuelle Dashboard-Ressource bearbeiten, Typ **JavaScript-Modul**:
   `/arandjelovac_live/arandjelovac-live-card.js?v=1.3.0`
4. HA-Seite beziehungsweise App vollständig neu laden. Die Karten-YAML bleibt gültig.

Die öffentlichen Quellen wurden live geprüft. Der Saisonkatalog bestätigt keine Jahrestermine; RSS bleibt ein begrenzter Ausschnitt. Die Abnahme dieser Version auf dem produktiven HA-System steht aus.
