Last reviewed: 2025-09-21

# RUNBOOK – UI Management Studio

## Zweck
Operativer Leitfaden für die Management Studio UI (read-only SQL & einfache Admin-Funktionen).

## Start/Stop
```bash
cd /Users/klaus.reiners/Projekte/churn-suite/bl-workspace
make mgmt
make open

# Stop (Ports leeren)
make down
```

Direktstart:
```bash
cd /Users/klaus.reiners/Projekte/churn-suite/ui-managementstudio
python app.py
```

## Healthchecks
- `GET /sql/tables` liefert Tabellenliste
- `POST /sql/query` mit `SELECT 1` liefert Ergebnis
- UI erreichbar unter `http://127.0.0.1:${MGMT_STUDIO_PORT:-5050}/sql`

## Konfiguration
- ENV: `MGMT_STUDIO_PORT`, `MGMT_OUTBOX_ROOT`, `MGMT_CHURN_DB_PATH`
- Pfade via `config/paths_config.py`

## Troubleshooting
- 404/Import-Fehler → Projekt-Root im `PYTHONPATH` sicherstellen
- Keine Tabellen → JSON-DB prüfen/laden; Pipelines ausführen
- Timeout → Query vereinfachen/LIMIT verkleinern

## Recovery
1) UI stoppen (`make down`)
2) JSON-DB Backup zurückspielen (siehe JSON-DB RUNBOOK)
3) UI neu starten, Healthchecks prüfen

## Sicherheit
- Admin-Endpoints erfordern `X-Admin-Password`
- SQL-Whitelist erzwingt Read-only

## Known Issues
- Live-Logs: Nur In-Memory, keine Persistenz – optionales File-Logging geplant
- Template-Lader: Fallback-Pfade (ProjectPaths) können in abweichenden Setups leer sein
- Experiments-CRUD: Validierung begrenzt – erweitertes Schema/Forms geplant

