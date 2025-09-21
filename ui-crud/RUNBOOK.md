Last reviewed: 2025-09-21

# RUNBOOK – UI CRUD (Static)

## Zweck
Operativer Leitfaden für den statischen CRUD-Server (Prototyping/Assets).

## Start/Stop
```bash
cd /Users/klaus.reiners/Projekte/churn-suite/bl-workspace
make crud
make open

# Stop (Ports leeren)
make down
```

Direktstart:
```bash
cd /Users/klaus.reiners/Projekte/churn-suite/ui-crud
python3 -m http.server 8080
```

## Healthchecks
- HTTP 200 auf `http://localhost:8080/`
- Statische Assets werden geladen (Chrome DevTools prüfen)

## Troubleshooting
- Port belegt → `make down` ausführen oder Prozess auf 8080 beenden
- 404 → Arbeitsverzeichnis/Dateipfade prüfen

## Betriebshinweise
- Nur statische Inhalte; keine sensiblen Daten ablegen
- Für produktive Abfragen die Management Studio UI nutzen

## Known Issues
- Kein HTTPS/Basic-Auth – nur lokal verwenden
- Kein Asset-Build – größere Frontends benötigen Build-Tooling

