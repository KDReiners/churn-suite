Last reviewed: 2025-09-21

# UI – CRUD (Static Server)

## Zweck
Einfacher statischer Server (Index/Assets) – optionales Frontend für CRUD-Demos.

## Quick Start
```bash
cd /Users/klaus.reiners/Projekte/churn-suite/bl-workspace
make crud
make open
```

Direktstart:
```bash
cd /Users/klaus.reiners/Projekte/churn-suite/ui-crud
python3 -m http.server 8080
```

## Hinweise
- Assets/HTML-Prototypen können hier abgelegt werden
- Management Studio bindet CRUD-Templates als Fallback ein (siehe `ui-managementstudio/app.py`)

