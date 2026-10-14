# Aranđelovac Live 1.2.1

- Behebt eine mögliche Ursache von **Custom element not found**: Die Karte wartet mit Klassenerstellung und Registrierung, bis Home Assistants Elementregistrierung bereit ist.
- Automatische Frontendmodule und zusätzlich eingetragene Dashboard-Ressourcen können dieselbe Datei ohne doppelte Registrierung laden.
- Neue Browserregressionen prüfen drei Ladereihenfolgen mit der echten HA-Polyfill-Version 0.0.10; die bestehende Oberfläche bleibt erhalten.
- Nach dem Update HA neu starten und die Seite beziehungsweise App neu laden. Die bestehende Karten-YAML bleibt gültig.

## Komplettpaket seit 1.2.0

Komplettpaket für Strom, Wasser, Verkehr, Gemeindemeldungen sowie Kultur und Tourismus. Aufklappbare, HA-Theme-kompatible Smartphone-Karte mit **Veranstaltungen & News** und getrenntem Quellenstatus.

- Bestehender EDS-Provider und seine Entitätsidentität bleiben erhalten.
- Einrichtung aller sechs unabhängigen Quellen mit einem Auswahlpunkt.
- Frontenddatei wird automatisch ausgeliefert und geladen.
- Bildbeiträge, unbestätigte Enden, verkürzte Abdeckung und Quellenfehler werden ausdrücklich angezeigt.
- Reale HA-Core-2026.10.1-Laufzeittests, Parserregressionen und Chromium-Tests in zwei Themes und drei Bildschirmbreiten.

Nach HACS-Installation HA neu starten, **Aranđelovac Live → Komplettpaket** hinzufügen und die HA-Seite neu laden. Karte:

```yaml
type: custom:arandjelovac-live-card
title: Aranđelovac Live
```

Details und Grenzen stehen in README und TEST_REPORT. Test in der produktiven HA-Installation steht noch aus.
