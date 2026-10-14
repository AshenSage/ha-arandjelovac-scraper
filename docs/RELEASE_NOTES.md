# Aranđelovac Live 1.4.0

Die freigegebene kompakte Veranstaltungsansicht ist umgesetzt: drei Reiter mit Eintragszahl und ein Kalenderblatt direkt neben dem Termin.

- **Termine:** Chronologische Liste mit Kalendertag, Monat und Wochentag; daneben Uhrzeit und Titel. Keine erfundene Uhrzeit bei reinen Datumsangaben.
- **Vorschau:** Kulturmeldungen und Ankündigungen ohne bestätigten Veranstaltungstag. Veröffentlichungsdaten stehen klar bezeichnet in den Details.
- **Feste:** Allgemeiner Saisonkatalog mit deutschen Monatskürzeln und eigenem Hinweis auf unbestätigte Jahrestermine. Monatsspannen bleiben Spannen.
- Ein Eintrag öffnet seinen vollständigen geladenen Textausschnitt und den Originalverweis. Die Übersicht zeigt keine Artikeltexte. Alle geladenen Einträge ausser Kino bleiben erreichbar, auch nach dem achten Eintrag.
- Der gewählte Reiter, geöffnete Details und der Tastaturfokus bleiben bei Daten- und Minutenupdates erhalten. Die Reiter unterstützen Pfeiltasten und Pos1/Ende; mehrere Karten besitzen unabhängige Auswahlen.
- Vergangene bzw. bereits beendete erkennbare Termine verschwinden auch bei der lokalen Minutenaktualisierung. Ein heute vergangener Beginn ohne bekanntes Ende bleibt entsprechend gekennzeichnet.
- Klar getrennte Hauptbereiche: **Versorgung & Verkehr**, **Veranstaltungen** und **Nachrichten aus der Gemeinde**. Eigene Symbole für die Veranstaltungsarten bleiben erhalten.
- Quellenfehler bleiben im Veranstaltungsbereich sichtbar. Bei Ausfall aller Veranstaltungsquellen steht **–** statt einer vermeintlichen Nullzählung.

## Aktualisieren

1. In HACS auf **1.4.0** aktualisieren und Home Assistant vollständig neu starten.
2. Die bestehende manuelle Dashboard-Ressource bearbeiten, Typ **JavaScript-Modul**:
   `/arandjelovac_live/arandjelovac-live-card.js?v=1.4.0`
3. HA-Seite beziehungsweise App vollständig neu laden. Die Karten-YAML und alle neun bereits eingerichteten Quellen bleiben gültig; keine erneute Einrichtung nötig.

Bei einem Update direkt von 1.2.x ergänzt **Integration hinzufügen → Aranđelovac Live → Komplettpaket · alle 9 Quellen** ausschliesslich die fehlenden Quellen.

Geprüft: 168 Python-Tests, 17 Tests im echten HA Core 2026.10.1 und 727 Chromium-Assertions in drei Themes bei 320, 440 und 736 px. Die tatsächlichen HA-Symbole und eine lokale Wiedergabe der erfassten Quelldaten wurden ebenfalls geprüft. Die produktive Smartphone-Abnahme von 1.4.0 folgt nach Installation.
