# Aranđelovac Live 1.2.2

Die Smartphone-Karte zeigt lokale Meldungen kompakter und verständlicher.

- Gültiges HA-Verkehrssymbol; alle verwendeten Symbole sind gegen den HA-2026.10.1-Katalog geprüft.
- Verkehr mit kurzer Kategorie, ausdrücklich genannter Strecke, Ort und angekündigter Endfrist. Originalmeldung bleibt aufgeklappt lesbar; abgelaufene Fristen bestätigen keine Freigabe.
- Verständliche Wassertexte mit Meldungsanzahl und Hinweis auf Bildbeiträge. Unterbruchsmeldungen behalten Vorrang.
- Erkannte Veranstaltungen als Kino, Theater, Konzert oder Ausstellung. Einzeltermine aus Wochenprogrammen wiederholen den Gesamtplan nicht mehr und verlinken auf das Original.
- Kompaktere Abstände, dezente Warnränder auf normaler Kartenfläche und besser lesbare Quellenstatus-Anzeigen im grünen Theme.
- Quellenübersicht mit **6/6 Quellen erreichbar**.

## Aktualisieren

1. In HACS auf **1.2.2** aktualisieren und Home Assistant vollständig neu starten.
2. Bei einer manuell eingetragenen Dashboard-Ressource den bestehenden Eintrag auf diese URL ändern, Typ **JavaScript-Modul**:
   `/arandjelovac_live/arandjelovac-live-card.js?v=1.2.2`
3. HA-Seite beziehungsweise App vollständig neu laden.

Die Karten-YAML und vorhandene Entitäts-IDs bleiben erhalten:

```yaml
type: custom:arandjelovac-live-card
title: Aranđelovac Live
```

Validierung: 159 Parser-/Transporttests, 13 echte HA-Tests und 219 Chromium-Prüfungen in drei Themes und drei Bildschirmbreiten. Die Abnahme der neuen Version in der produktiven HA-Installation steht aus.
