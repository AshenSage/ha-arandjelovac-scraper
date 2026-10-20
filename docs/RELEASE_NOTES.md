# Aranđelovac Live 1.5.0

Dauerhafte Korrektur der Quellenabdeckung und der Einordnung von Versorgungsmeldungen. Fehlende Meldungen werden aus ihren Quellen gelesen, ohne fest eingetragene Einzelereignisse.

- Gemeinde: standardmässig alle Kategorien im Anzeigezeitraum statt nur Kategorie 47. Begrenzte Pagination; Beschaffung und interne Stellen ausgefiltert. Eigene Kategorien bleiben erhalten.
- JKP: datumsbegrenzte Folgeseiten und separate Quelle für lokale Arbeiten. Studentenbesuche zählen nicht mehr als Wassermeldungen. Wasserartikel werden beim nächsten regulären Abruf erneut gelesen statt bis zu sechs Stunden gecacht.
- Wasser: Reparaturabschluss, bestätigte Normalisierung, offene Störung und abgelaufenes Planfenster getrennt. Erwartete oder verneinte Normalisierung ist keine Entwarnung. Offene Meldungen haben bei begrenzter Anzeige Vorrang.
- Verkehr: Standardorte umfassen Gemeinde und benachbarte Zufahrten inklusive Topola–Božurnja. Bačka Topola bleibt ausgeschlossen; eigene Ortslisten bleiben erhalten.
- Museum: separate offizielle Ausstellungsübersicht zusätzlich zum RSS. Ohne bestätigte Laufzeit erscheinen Angebote ausdrücklich undatiert.
- Quellenstatus `partial` und sichtbarer Hinweis bei begrenzter Auswertung oder fehlgeschlagener Zusatzquelle.

## Aktualisieren

1. HACS-Version **1.5.0** installieren und HA neu starten.
2. **Integration hinzufügen → Aranđelovac Live → Komplettpaket · alle 10 Quellen** ergänzt nur die fehlende Quelle für lokale Arbeiten.
3. Eine vorhandene manuelle Kartenressource auf `/arandjelovac_live/arandjelovac-live-card.js?v=1.5.0` ändern und das Frontend neu laden. Bestehende Entity-IDs bleiben erhalten.

Prüfungen und aktueller Quellenabgleich: [TEST_REPORT.md](TEST_REPORT.md).
