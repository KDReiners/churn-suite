## Projekthandbuch – Strukturierte Übersicht

Zuletzt geprüft: 2025-09-21

### 1) Git-Flow
- **Haupt-Branches**: `main` (stabil, releasable), `develop` (Integration)
- **Kurzlebige Branches**: `feature/<kurz-beschreibung>`, `fix/<ticket>`, `chore/<aufgabe>`
- **Pull Requests**: Pflicht-Review, kleine PRs, CI grün vor Merge, klare Beschreibung
- **Squash-Merge**: Standard in `develop`/`main` (saubere Historie, ein Commit pro PR)
- **Releases**: Release-Branch `release/x.y`, Freeze nur Bugfixes, Tag bei Freigabe
- **Tags (SemVer)**: `vX.Y.Z` (Major: Breaking, Minor: Features, Patch: Fixes)
- **Hotfixes**: `hotfix/x.y.z` von `main`, danach Backmerge nach `develop`

### 2) Architektur-Leitplanken
- **Separation of Concerns**:
  - Business-Logik je Domäne getrennt: `bl-churn/bl/Churn`, `bl-cox/bl/Cox`, `bl-counterfactuals/bl/Counterfactuals`
  - Datenzugriff/Infra separat: `config/`, `json-database/`
  - UI getrennt: `ui-managementstudio/`
- **Delegation**:
  - Pipelines orchestrieren, spezialisierte Komponenten arbeiten: z. B. `bl-churn/bl/Churn/churn_auto_processor.py` delegiert an Loader/Features/Trainer/Evaluator
- **DAL (Data Access Layer)**:
  - SQL-Server-Zugriff kapseln (z. B. `bl-churn/config/data_access_layer.py`, `json-database/bl/json_database/sql_query_interface.py`)
  - Verbindungs- und Query-Logik nicht in BL-Modulen streuen
- **JSON-DB (leichtgewichtige Persistenz/Cache)**:
  - Modul: `json-database/` (z. B. `bl/json_database/churn_json_database.py`, `bl/json_database/leakage_guard.py`)
  - Einsatzzwecke: Zwischenergebnisse, Artefakte, schnelle Iteration ohne DB-Schemaänderungen
  - Keine Langzeit-Wahrheit: Quelle bleibt MS SQL-Server
- **Konfigurationen (Single Source of Truth)**:
  - `*/config/shared/config/*.json` (z. B. `algorithm_config_optimized.json`, `feature_mapping.json`, `ui_settings.json`)
  - Pfade/Globale Settings: `*/config/paths_config.py`, `bl-churn/config/global_config.py`
- **Testbarkeit**:
  - Deterministische Steps, klare Ein-/Ausgaben (z. B. `Tests/test_results_summary.json` in Modulen)
  - Kein I/O in Core-Logik ohne Abstraktion (Interfaces für DAL/Storage)

### 3) Repository-Regeln
- **ProjectPaths**:
  - Pfade zentral: `*/config/paths_config.py`; keine hartkodierten relativen Pfade in BL
  - Absolutpfade bevorzugen (auch in Tools/CI) für Reproduzierbarkeit
- **Keine Mockdaten im Repo**:
  - Keine produktionsähnlichen CSV/SQL-Dumps einchecken
  - Synthetic/Fixtures nur generativ zur Laufzeit oder in separatem, internem Artefakt-Storage
- **Trash-Ordner-Policy**:
  - Temporäre/zu löschende Artefakte in `/trash/` (mit `.gitkeep`), niemals in Modulkernen
  - CI ignoriert `/trash/`; regelmäßige Bereinigung
- **Konfigurationsdisziplin**:
  - Änderungen an `*/shared/config` per PR, Versionierung via Tags/Release-Notes
  - Sensible Daten nur via Secrets/ENV, nie in Git

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

### 5) Tooling
- **Makefile-Shortcuts** (zentral in `bl-workspace/Makefile`):
  - `make setup`: Environment/Dependencies installieren
  - `make lint` / `make test`: Qualitäts-Gates
  - `make run-<modul>`: Standard-Entry-Points starten (z. B. Churn/Cox)
  - `make clean` / `make data-clean`: Artefakte bereinigen
- **Auto-Ingestion**:
  - Ingestion-Einstieg: `bl-input/input_ingestion.py`
  - Zielt auf MS SQL-Server via DAL; optionales Schreiben in `json-database` für Caching
  - Konfigurierbar über `*/config/paths_config.py` und `*/shared/config/*.json`
- **Lazy Import (Performance/Optionalität)**:
  - Schwere/optionale Pakete erst bei Bedarf laden (z. B. via `importlib` innerhalb von Funktionen)
  - Feature-Gates über Configs; klarer Fallback, wenn Optionals fehlen
  - Startskripte vermeiden globale Side-Effects beim Import
- **UI-Tools**:
  - Management UI: `ui-managementstudio/app.py`, Assets unter `static/`, Templates unter `templates/`
  - SQL-Ansichten/Demos in `templates/sql.html` (nur nicht-sensible Queries)

### 6) Quick Start (konsistent)

```bash
# Projekt-Workspace
cd /Users/klaus.reiners/Projekte/churn-suite/bl-workspace

# Management Studio starten und öffnen
make mgmt
make open

# Churn Auto-Processor (Status/Validate/Run)
make churn ARGS="--status"
make churn ARGS="--validate"
make churn

# Cox direkt (siehe Modul-README)
source /Users/klaus.reiners/Projekte/churn-suite/bl-cox/.venv/bin/activate
cd /Users/klaus.reiners/Projekte/churn-suite/bl-cox
python bl/Cox/cox_auto_processor.py --status

# Counterfactuals direkt (siehe Modul-README)
source /Users/klaus.reiners/Projekte/churn-suite/bl-counterfactuals/.venv/bin/activate
cd /Users/klaus.reiners/Projekte/churn-suite/bl-counterfactuals
python bl/Counterfactuals/counterfactuals_cli.py --experiment-id 1 --sample 0.2

# SQL-Abfragen über JSON-DB
source /Users/klaus.reiners/Projekte/churn-suite/json-database/.venv/bin/activate
cd /Users/klaus.reiners/Projekte/churn-suite/json-database
python bl/json_database/query_churn_database.py "SELECT * FROM experiments ORDER BY experiment_id DESC LIMIT 5"
```

### 7) Runbooks

- bl-churn: [bl-churn/RUNBOOK.md](bl-churn/RUNBOOK.md)
- bl-cox: [bl-cox/RUNBOOK.md](bl-cox/RUNBOOK.md)
- bl-counterfactuals: [bl-counterfactuals/RUNBOOK.md](bl-counterfactuals/RUNBOOK.md)
- json-database: [json-database/RUNBOOK.md](json-database/RUNBOOK.md)

Hinweis: Offene Themen werden als „Known Issues“ im jeweiligen RUNBOOK gepflegt. Bitte neue Punkte dort ergänzen.

Zentrales Board: [KNOWN_ISSUES.md](KNOWN_ISSUES.md)

Template für Einträge:
```markdown
## Known Issues
- <Kurzbeschreibung> – Status: <offen/in Bearbeitung>; Impact: <niedrig/mittel/hoch>; Workaround: <falls vorhanden>; Owner: <Name>; Target-Date: <YYYY-MM-DD>
```

### Zusammenspiel (High-Level Flow)
- **Input**: `bl-input` lädt Daten aus MS SQL (DAL) → optional `json-database` Cache
- **Domänen-Pipelines**:
  - Churn: `bl-churn/bl/Churn/*` (Load → Feature → Train → Evaluate → Persist)
  - Cox: `bl-cox/bl/Cox/*` analoger Ablauf
  - Counterfactuals: `bl-counterfactuals/bl/Counterfactuals/*` konsumiert Modelle/Features
- **Konfiguration**: Einheitlich aus `*/config/` + `*/shared/config/*.json`
- **Persistenz**: Ergebnisse in SQL und/oder JSON-DB; UI liest für Einsicht
- **Betrieb**: Steuerung via Makefile-Targets; Dokumentation in READMEs/RUNBOOKs
- **Governance**: Änderungen per PR/Squash; Releases getaggt; Docs aktuell halten


