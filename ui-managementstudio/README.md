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

