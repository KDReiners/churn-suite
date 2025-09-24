Last reviewed: 2025-09-22

# UI – CRUD (Pipeline Frontend)

## Zweck
Reines HTML/JS Frontend für Runner-Service API. Keine BL-Imports nötig.

## Quick Start
```bash
cd /Users/klaus.reiners/Projekte/churn-suite/ui-crud
python3 -m http.server 8080
# Browser: http://localhost:8080
```

## Funktionen
- Pipeline-Ausführung (Churn, Cox, Counterfactuals) über Runner-API
- Live-Log-Streaming (Polling-basiert)  
- Status-Tracking für aktive Jobs
- Moderne UI mit Apple-inspiriertem Design

## Architektur
- Konsumiert nur Runner-Service API (localhost:5050)
- Kein Backend, reine Client-Side App
- Polling für Live-Updates (2s Intervall)

## Dependencies
- Runner-Service muss laufen (localhost:5050)
- Moderne Browser (ES6+ Support)

