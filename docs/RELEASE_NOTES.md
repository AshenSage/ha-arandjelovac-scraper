# Aranđelovac Live 1.3.1

Die Veranstaltungskarte wird kompakter und unterscheidet Veranstaltungsarten durch eigene Symbole.

- Lesungen, Theater, Konzerte, Ausstellungen, Märkte/Basare und Festivals haben passende Icons. Auch die geschlossene Vorschau übernimmt das Symbol des nächsten Termins. Die drei Veranstaltungsgruppen haben eigene Symbole.
- Lange Meldungstexte zeigen eine kurze Vorschau mit **Mehr anzeigen / Weniger anzeigen**. Ein identischer vollständiger Titel am Textanfang wird entfernt. Die geladenen Textausschnitte und Originalverweise bleiben zugänglich.
- **Feste & Basare · Saisonübersicht** ist innerhalb des Veranstaltungsbereichs separat eingeklappt und zeigt die Zahl der Einträge. Saisonmonate erscheinen auf Deutsch; es wird weiterhin kein Jahrestermin erfunden.
- Veröffentlichungsdaten werden ausdrücklich mit **Veröffentlicht am** bezeichnet. Sie werden nicht als Veranstaltungstage dargestellt.
- Geöffnete Textdetails und Saisonbereiche bleiben bei Quellenupdates und der lokalen Minutenaktualisierung erhalten. Die Bedienelemente sind per Tastatur zugänglich.
- Kino bleibt ausgeblendet. Alle geladenen anderen Veranstaltungen bleiben erreichbar; Quellen, Sensoren und Karten-YAML bleiben erhalten.

## Aktualisieren

1. In HACS auf **1.3.1** aktualisieren und Home Assistant vollständig neu starten.
2. Falls eine manuelle Dashboard-Ressource eingetragen ist, deren URL bearbeiten, Typ **JavaScript-Modul**:
   `/arandjelovac_live/arandjelovac-live-card.js?v=1.3.1`
3. HA-Seite beziehungsweise App vollständig neu laden. Bei bereits neun eingerichteten Quellen ist keine erneute Einrichtung nötig.

Bei einem Update direkt von 1.2.x ergänzt **Integration hinzufügen → Aranđelovac Live → Komplettpaket · alle 9 Quellen** ausschliesslich die fehlenden Quellen.

Geprüft: 168 Python-Tests, 17 Tests im echten HA Core 2026.10.1 und 473 Chromium-Assertions in drei Themes bei 320, 440 und 736 px. Die neuen Symbole wurden gegen den tatsächlichen HA-Icon-Katalog geprüft. Die produktive Smartphone-Abnahme von 1.3.1 folgt nach Installation; Nutzer-Screenshots bestätigen bereits 1.3.0 mit neun erreichbaren Quellen und zusätzlichen Veranstaltungsinhalten.
