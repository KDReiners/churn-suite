Last reviewed: 2025-09-21

# UI – Management Studio (Read-Only JSON SQL)

## Zweck
Web-UI (Flask) für read-only SQL-Abfragen und einfache Verwaltung auf der JSON-Database (DuckDB-basiert).

## Quick Start
```bash
cd /Users/klaus.reiners/Projekte/churn-suite/bl-workspace
make mgmt
make open
```

Direktstart:
```bash
cd /Users/klaus.reiners/Projekte/churn-suite/ui-managementstudio
python app.py
```

## Endpunkte
- `/sql` – Editor, Tabellenliste, Ergebnis-Grid, Views, CLI-Tabellen
- `/sql/tables` – Tabellen mit Record-Zahl und Beschreibung
- `/sql/schema/<table>` – Schema-Infos (display_type/description)
- `/sql/views` (GET/POST) – Views auf JSON-DB (erfordert Passwort für POST)
- `/sql/query` (POST) – Query-Ausführung (nur SELECT/EXPLAIN/PRAGMA/WITH)
- `/logs/live` – In-Memory Log-Stream (Polling)
- `/experiments` (GET/POST/PUT/DELETE) – CRUD auf Experimente (Passwort erforderlich)
- `/experiments/<id>/run` – Pipeline-Run (churn/cox/cf) async, passwortgeschützt
- `/experiments/<id>/materialize` – Materialisierung von Detailtabellen

## Konfiguration
- ENV: `MGMT_STUDIO_PORT`, `MGMT_OUTBOX_ROOT`, `MGMT_CHURN_DB_PATH`
- Pfade: `config/paths_config.py`

## Sicherheit
- Read-only SQL-Whitelist, Timeout, LIMIT enforcement
- Admin-Aktionen nur mit `X-Admin-Password`

## Troubleshooting
- UI lädt nicht → Pfade/ENV prüfen, venv aktivieren
- Tabellen/Views fehlen → JSON-DB prüfen, Pipelines ausführen
- Timeout → Query vereinfachen, LIMIT reduzieren

## Frisch ingestierte Dateien finden
- Outbox-Root:
  - ENV `MGMT_OUTBOX_ROOT` (vom Dev-Skript gesetzt) oder `OUTBOX_ROOT`
  - Fallback: `bl-churn/dynamic_system_outputs/outbox`
- Stage0-Exports liegen unter: `outbox/stage0_cache/<csv_hash>.json`
- Workflow in der UI:
  1) `make ingest` ausführen (erzeugt Stage0 + Outbox-Export)
  2) UI starten: `make mgmt` und `make open` → Tab SQL öffnen
  3) Tabelle/View „files“ prüfen (falls vorhanden) oder Dateiliste via OS/Explorer öffnen
  4) Optional: Query auf JSON-DB (z. B. letzte Files) – sofern in DB registriert

Beispiel für eine einfache SQL (falls Files registriert wurden):
```sql
SELECT *
FROM files
ORDER BY dt_inserted DESC
LIMIT 10;
```

