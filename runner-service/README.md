Last reviewed: 2025-09-22

# Runner Service

Dünne Orchestrierungsschicht für BL-Module (Churn, Cox, Counterfactuals).

## Zweck
- FastAPI Service für Pipeline-Ausführung
- Subprocess-Management für BL-Module  
- Live-Log-Streaming
- Lock-Handling für parallele Jobs

## Quick Start
```bash
cd /Users/klaus.reiners/Projekte/churn-suite
source .venv311/bin/activate
python runner-service/app.py
```

## API Endpoints
- `POST /run/churn` - Churn-Pipeline starten
- `POST /run/cox` - Cox-Pipeline starten  
- `POST /run/cf` - Counterfactuals-Pipeline starten
- `GET /logs/stream` - Live-Logs abrufen (Polling)
- `GET /jobs` - Aktive Jobs anzeigen
- `DELETE /jobs/{job_id}` - Job beenden

## Architektur
- Keine Businesslogik, nur Prozess-Orchestrierung
- BL-Module laufen als separate Subprozesse
- JSON-DB → BL-Modul → Outbox → JSON-DB Workflow
- Zentrale Pfad-Konfiguration über `/config/paths_config.py`

## Environment
- `OUTBOX_ROOT` - Root-Level Outbox (Standard: `/dynamic_system_outputs/outbox/`)
- Port: 5050 (Standard)
