## Projekthandbuch – Strukturierte Übersicht

Zuletzt geprüft: 2025-09-22

### 1) Git-Flow
- **Haupt-Branches**: `main` (stabil, releasable), `develop` (Integration)
- **Kurzlebige Branches**: `feature/<kurz-beschreibung>`, `fix/<ticket>`, `chore/<aufgabe>`
- **Pull Requests**: Pflicht-Review, kleine PRs, CI grün vor Merge, klare Beschreibung
- **Squash-Merge**: Standard in `develop`/`main` (saubere Historie, ein Commit pro PR)
- **Releases**: Release-Branch `release/x.y`, Freeze nur Bugfixes, Tag bei Freigabe
- **Tags (SemVer)**: `vX.Y.Z` (Major: Breaking, Minor: Features, Patch: Fixes)
- **Hotfixes**: `hotfix/x.y.z` von `main`, danach Backmerge nach `develop`

### 2) Architektur-Leitplanken
- **Domain-Driven Design mit Event-Driven Architecture**:
  - **Selbständige Domänen**: `bl-churn`, `bl-cox`, `bl-counterfactuals` als isolierte Bounded Contexts
  - **JSON-DB als Shared Kernel**: Zentrale Datenquelle für alle Domänen
  - **Outbox Pattern**: Jede Domäne schreibt Ergebnisse in Outbox, JSON-DB liest sie ein
  - **Lose Kopplung**: Domänen kennen sich nicht untereinander, nur über JSON-DB
- **Runner-Service Orchestrierung**:
  - Dünne FastAPI-Schicht (`runner-service/`) für Pipeline-Ausführung
  - Subprocess-Management für BL-Module
  - Live-Log-Streaming und Job-Tracking
- **Zentrale Konfiguration**:
  - **Einzige ProjectPaths-Quelle**: `config/paths_config.py` (Root-Level)
  - **OUTBOX_ROOT**: `dynamic_system_outputs/outbox/` (Root-Level, nicht mehr unter bl-churn)
  - **Eine Python-Umgebung**: `requirements.txt` (Root-Level) für alle Module
- **DAL (Data Access Layer)**:
  - SQL-Server-Zugriff kapseln (z. B. `bl-churn/config/data_access_layer.py`, `json-database/bl/json_database/sql_query_interface.py`)
  - Verbindungs- und Query-Logik nicht in BL-Modulen streuen
- **JSON-DB (leichtgewichtige Persistenz/Cache)**:
  - Modul: `json-database/` (z. B. `bl/json_database/churn_json_database.py`, `bl/json_database/leakage_guard.py`)
  - Einsatzzwecke: Zwischenergebnisse, Artefakte, schnelle Iteration ohne DB-Schemaänderungen
  - Keine Langzeit-Wahrheit: Quelle bleibt MS SQL-Server

### 3) Repository-Regeln
- **Zentrale Pfad-Konfiguration**:
  - **Einzige Quelle**: `config/paths_config.py` (Root-Level)
  - Ersetzt alle modulspezifischen `*/config/paths_config.py`
  - Absolutpfade bevorzugen (auch in Tools/CI) für Reproduzierbarkeit
- **Zentrale Dependency-Verwaltung**:
  - **Eine requirements.txt**: Root-Level für alle Module
  - **Eine Python-Umgebung**: Alle Module nutzen dieselbe venv
  - Ersetzt modulspezifische `*/requirements.txt`
- **Keine Mockdaten im Repo**:
  - Keine produktionsähnlichen CSV/SQL-Dumps einchecken
  - Synthetic/Fixtures nur generativ zur Laufzeit oder in separatem, internem Artefakt-Storage
- **Trash-Ordner-Policy**:
  - Temporäre/zu löschende Artefakte in `/trash/` (mit `.gitkeep`), niemals in Modulkernen
  - CI ignoriert `/trash/`; regelmäßige Bereinigung
- **Konfigurationsdisziplin**:
  - Änderungen an `*/shared/config` per PR, Versionierung via Tags/Release-Notes
  - SENSITIVE Daten nur via Secrets/ENV, nie in Git

### 4) Dokumentations-Regeln
- **README pro Modul**:
  - Pflicht in: `bl-churn/`, `bl-cox/`, `bl-counterfactuals/`, `bl-input/`, `json-database/`, `ui-managementstudio/`
  - Minimalinhalt: Zweck, Architektur-Skizze, Setup/Runs, Konfigs, typische Fehler
- **RUNBOOKs für Operation**:
  - `RUNBOOK.md` in Kernmodulen für Betriebsabläufe, On-Call-Hinweise
- **Staleness-Check**:
  - „Last reviewed: YYYY-MM-DD“ im Kopf jeder README
  - Monatlicher Review-Kalender; PRs, die Verhalten ändern, müssen README/RUNBOOK aktualisieren
- **Beispiel-Citation**:
  - Code-Auszüge in Doku mit Pfadangabe in Backticks (z. B. `bl/Churn/churn_model_trainer.py`)

### 5) Tooling & Services
- **Runner-Service** (`runner-service/`):
  - FastAPI-Service für Pipeline-Orchestrierung (Port 5050)
  - Endpunkte (Auszug):
    - `POST /run/churn` (direkt, mit `experiment_id`, Zeiträumen, `test_mode`)
    - `POST /experiments/{id}/run` (indirekt, nutzt gespeichertes Experiment)
    - `GET  /files` (Dateiabdeckung: min/max `I_TIMEBASE`, `rows` je File-ID)
    - `GET  /logs/stream` (Live-Logs)
  - Subprocess-Management für BL-Module
  - Reload-Steuerung: `RUNNER_RELOAD=0` deaktiviert Auto-Reload für stabile Läufe
  - Start: `python runner-service/app.py`
- **CRUD-Frontend** (`ui-crud/`):
  - Reines HTML/JS Frontend für Runner-Service API
  - Live-Log-Streaming und Status-Tracking
  - Testmodus-Schalter: „Testmodus (90% Datenreduktion)“ (default an)
  - Start: `cd ui-crud && python3 -m http.server 8080`
- **Management Studio** (`ui-managementstudio/`):
  - Read-Only SQL-Interface für JSON-DB
  - Legacy CRUD-Funktionen (wird durch Runner-Service ersetzt)
- **Makefile-Shortcuts** (zentral in `bl-workspace/Makefile`):
  - `make ingest`: CSV→Stage0→Outbox→rawdata (Union, replace)
  - `make mgmt` / `make open`: Management Studio starten/öffnen
  - `make down`: Ports bereinigen
- **Outbox-Steuerung**:
  - `OUTBOX_ROOT` (ENV), Fallback: `dynamic_system_outputs/outbox` (Root-Level)

### 5.1) Dateningestion & Idempotenz (Clean Import)

- **Single-Env**: Es gibt genau eine Python-Umgebung `.venv` im Repo-Root (keine `.venv311`).
- **Befehl**: `cd bl-workspace && make ingest`
  - Erkennt bereits registrierte Input-CSV-Dateien und analysiert nur neue oder via `--override` angegebene Files
  - Schreibt Stage0-JSONs in `dynamic_system_outputs/stage0_cache/` und kopiert sie in die Outbox
  - Materialisiert `rawdata` als Union (replace=True)
- **Lineage-Policy**:
  - `files` enthält ausschließlich Einträge mit `source_type = input_data` (nur Ursprungs-CSV-Dateien)
  - `rawdata.id_files` referenziert die dazugehörigen Input-File-IDs (nicht die Stage0/Backtest-Artefakte)
  - Backtest-JSONs und Stage0-Dateien werden nicht in `files` gezählt
- **Idempotenz**:
  - Mehrfaches `make ingest` erzeugt keine Duplikate; `rawdata` wird ersetzt, `files` bleibt stabil (nur Input)
  - Re-Analyse eines bestimmten Files: `make ingest ARGS="--override ChurnData_20250831.csv"`
- **Reset (Clean Slate)**:
  - JSON-DB leeren (Tabellen & Metadaten korrekt setzen), Stage0/Outbox säubern, dann `make ingest`
  - Erwartete Validierung nach Clean Import:
    - `files = 2` (nur Input-CSV-Dateien)
    - `rawdata = 881.177` (442.959 + 438.218)

### 6) Quick Start

**Neue Architektur (Runner-Service + CRUD-Frontend):**
```bash
# 1. Runner-Service starten
cd /Users/klaus.reiners/Projekte/churn-suite
RUNNER_RELOAD=0 python runner-service/app.py

# 2. CRUD-Frontend starten (neues Terminal)
cd ui-crud
python3 -m http.server 8080
# Browser: http://localhost:8080

# 3. Pipeline ausführen über Web-UI oder API
curl -X POST http://localhost:5050/run/churn \
  -H "Content-Type: application/json" \
  -d '{"experiment_id": 1, "training_from": "2024-01", "training_to": "2024-12", "test_from": "2025-01", "test_to": "2025-08", "test_mode": false}'
```

**Legacy (Management Studio):**
```bash
# Projekt-Workspace
cd /Users/klaus.reiners/Projekte/churn-suite/bl-workspace

# Ingestion (alle neuen CSVs)
make ingest
# Override eines einzelnen Files
make ingest ARGS="--override ChurnData_20250831.csv"

# Management Studio starten und öffnen
make mgmt
make open
```
 
### 6.1) UI-Pipeline Start (Idempotent)

```bash
# Services starten (neue Sessions)
cd /Users/klaus.reiners/Projekte/churn-suite
source .venv/bin/activate
python runner-service/app.py &             # Port 5050
cd ui-crud && python3 -m http.server 8080 &
python ../ui-managementstudio/app.py &     # Port 5001

# Browser
# - Pipeline Runner:     http://localhost:8080/
# - Experiments (CRUD):  http://localhost:8080/experiments.html
# - Management Studio:   http://localhost:5001/sql/

# Pipeline idempotent starten (mehrfach möglich ohne Doppelungen)
curl -X POST http://localhost:5050/run/churn \
  -H "Content-Type: application/json" \
  -d '{"experiment_id": 1, "training_from": "202401", "training_to": "202412", "test_from": "202501", "test_to": "202508"}'
```

Hinweise:
- Management Studio cached die JSON-DB (Singleton). Bei neuen Tabellen (z. B. `backtest_results`) Studio kurz neu starten.
- `backtest_results` wird automatisch angelegt, falls noch nicht vorhanden.

### 6.2) Cox-Integration (Vorschau)
- Runner: `POST /run/cox` sowie `POST /experiments/{id}/run` mit `pipeline="cox"` (Cutoff über `hyperparameters.cutoff_exclusive`)
- Persistenz (JSON‑DB): `cox_survival`, `cox_prioritization_results`
- Management Studio: Materialisierung `customer_cox_details_{experiment_id}` und Fusion-View `churn_cox_fusion`
### 7) Runbooks

- bl-churn: [bl-churn/RUNBOOK.md](bl-churn/RUNBOOK.md)
- bl-cox: [bl-cox/RUNBOOK.md](bl-cox/RUNBOOK.md)
- bl-counterfactuals: [bl-counterfactuals/RUNBOOK.md](bl-counterfactuals/RUNBOOK.md)
- json-database: [json-database/RUNBOOK.md](json-database/RUNBOOK.md)

### 8) Sealed-Komponenten
- Ingestion-Orchestrator (`bl-workspace/dev`, Target `ingest`) ist SEALED. Änderungen nur nach expliziter Rückfrage und architektonischer Prüfung.


