Last reviewed: 2025-09-21

# CRUD/Runner – Neuaufbau-Plan (Vorschlag)

## Ziel
Stabile, entkoppelte Ausführung der Churn/Cox/CF-Pipelines mit klaren Pfaden, reproduzierbaren Environments und einer leichten CRUD-UI.

## Aktueller Funktionsumfang (erfasst)
- Experiments-CRUD:
  - Anlegen/Ändern/Löschen von Experimenten (`/experiments`, `/experiments/<id>`)
  - Materialisierung pro Experiment (`/experiments/<id>/materialize`)
- Runner-Aufrufe:
  - POST `/experiments/<id>/run` mit `pipeline` in {`churn`,`cox`,`cf`}
  - Live-Logs via `/logs/live?since=...`
- Ablage:
  - JSON-DB in `bl-churn/dynamic_system_outputs/churn_database.json`
  - Backtests/Modelle unter `bl-churn/models` (via `ProjectPaths`)

## Hauptprobleme
- Gemischte Imports aus Submodulen → mehrere `ProjectPaths`-Klassen, Pfadkonflikte
- Fehlende ML-Abhängigkeiten im UI-venv → Laufzeitfehler
- CRUD-UI und Runner im selben Prozess → schwer zu isolieren/diagnostizieren

## Neuaufbau – Architektur
- Backend (Runner-Service):
  - Separater FastAPI/Flask Dienst `runner-service/` mit eigenem `requirements.txt` (inkl. scikit-learn, joblib, scipy)
  - Endpunkte:
    - POST `/run/churn` {experiment_id, training_from, training_to, test_from, test_to}
    - POST `/run/cox` {experiment_id, cutoff_exclusive}
    - POST `/run/cf`  {experiment_id, sample, limit}
    - GET  `/logs/stream?since=...` (SSE) oder Polling-Endpoint
  - Läuft mit explizitem `PYTHONPATH` (bl-churn, bl-cox, bl-counterfactuals, json-database) und ENV (`OUTBOX_ROOT`, `UI_SETTINGS_PATH`)
  - Lock-Handling zentral

- Frontend (ui-crud neu):
  - Reines HTML/JS (oder kleines Vue/React)
  - Konsumiert nur die Runner-API (kein BL-Import nötig)
  - Tabellen/Views über Read-Only Management Studio oder direkt aus JSON-DB (DuckDB/SQL)

## Pfade & ENV (verbindlich)
- `UI_SETTINGS_PATH` → `bl-churn/config/shared/config/ui_settings.json`
- `OUTBOX_ROOT` → `<repo>/dynamic_system_outputs/outbox`
- `CHURN_DB_PATH` → Pfad zur JSON-DB (Standard: `bl-churn/dynamic_system_outputs/churn_database.json`)

## Schrittplan (inkrementell)
1. Runner-Service-Verzeichnis anlegen, `requirements.txt` mit vollständigen BL-Dependencies.
2. Minimal-Endpoints (nur Churn) implementieren, Logs per SSE bereitstellen.
3. ui-crud Buttons auf Runner-API umstellen.
4. Cox/CF ergänzen, Materialisierung adaptieren.
5. Tests/Smoke: Run (Churn) → JSON-DB → Materialize → CF.

## Risiken/Abgrenzungen
- Größere JSON-DB kann I/O intensiv sein → optional asynchrone Läufe + Job-Queue.
- Pfadkonstanten strikt zentral halten (nur eine `ProjectPaths`-Quelle).

Last reviewed: 2025-09-21

# CRUD/Runner – Neuaufbau-Plan (Vorschlag)

## Ziel
Stabile, entkoppelte Ausführung der Churn/Cox/CF-Pipelines mit klaren Pfaden, reproduzierbaren Environments und einer leichten CRUD-UI.

## Aktueller Funktionsumfang (erfasst)
- Experiments-CRUD:
  - Anlegen/Ändern/Löschen von Experimenten (`/experiments`, `/experiments/<id>`)
  - Materialisierung pro Experiment (`/experiments/<id>/materialize`)
- Runner-Aufrufe:
  - POST `/experiments/<id>/run` mit `pipeline` in {`churn`,`cox`,`cf`}
  - Live-Logs via `/logs/live?since=...`
- Ablage:
  - JSON-DB in `bl-churn/dynamic_system_outputs/churn_database.json`
  - Backtests/Modelle unter `bl-churn/models` (via `ProjectPaths`)

## Hauptprobleme
- Gemischte Imports aus Submodulen → mehrere `ProjectPaths`-Klassen, Pfadkonflikte
- Fehlende ML-Abhängigkeiten im UI-venv → Laufzeitfehler
- CRUD-UI und Runner im selben Prozess → schwer zu isolieren/diagnostizieren

## Neuaufbau – Architektur
- Backend (Runner-Service):
  - Separater FastAPI/Flask Dienst `runner-service/` mit eigenem `requirements.txt` (inkl. scikit-learn, joblib, scipy)
  - Endpunkte:
    - POST `/run/churn` {experiment_id, training_from, training_to, test_from, test_to}
    - POST `/run/cox` {experiment_id, cutoff_exclusive}
    - POST `/run/cf`  {experiment_id, sample, limit}
    - GET  `/logs/stream?since=...` (Server-Sent Events oder Polling)
  - Läuft mit explizitem `PYTHONPATH` (bl-churn, bl-cox, bl-counterfactuals, json-database) und ENV (`OUTBOX_ROOT`, `UI_SETTINGS_PATH`)
  - Lock-Handling zentral

- Frontend (ui-crud neu):
  - Reines HTML/JS (oder kleines Vue/React bei Bedarf)
  - Konsumiert nur die Runner-API (kein BL-Import nötig)
  - Tabellen/Views über bestehendes Read-Only Management Studio oder direkt aus JSON-DB (DuckDB/SQL)

## Pfade & ENV (verbindlich)
- `UI_SETTINGS_PATH` → `bl-churn/config/shared/config/ui_settings.json`
- `OUTBOX_ROOT` → `<repo>/dynamic_system_outputs/outbox`
- JSON-DB Pfad konfigurierbar über `CHURN_DB_PATH`

## Schrittplan (inkrementell)
1. Runner-Service-Verzeichnis anlegen, `requirements.txt` mit vollständigen BL-Dependencies.
2. Minimal-Endpoints (nur Churn) implementieren, Logs per SSE bereitstellen.
3. ui-crud Buttons auf Runner-API umstellen.
4. Cox/CF ergänzen, Materialisierung adaptieren.
5. Tests/Smoke: Run (Churn) → JSON-DB → Materialize → CF.

## Risiken/Abgrenzungen
- Größere JSON-DB kann I/O intensiv sein → optional asynchrone Läufe + Job-Queue.
- Pfadkonstanten strikt zentral halten (nur eine `ProjectPaths`-Quelle).


