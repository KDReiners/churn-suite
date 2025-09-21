Last reviewed: 2025-09-21

# Known Issues – Zentrales Board

Kurzübersicht offener Themen über alle Module hinweg. Detaillierte Pflege erfolgt in den jeweiligen RUNBOOKs.

## Überblick nach Modulen

### bl-churn
- Threshold-Optimierung: Automatisierung ausstehend (F1/Elbow/Precision Auswahl)
- AUC-Ziel 0.99 derzeit verfehlt – Feature-/Tuning-Track offen

### bl-cox
- Cutoff-UX (cutoff_exclusive) rudimentär – UI/Forms geplant
- Risiko-Kategorien heuristisch – Schwellenreview offen

### bl-counterfactuals
- Surrogat-Qualität schwankt bei kleinen Samples
- Policy-Grenzen teilweise zu restriktiv – Business-Abgleich nötig

### json-database
- Backup-Retention prüfen/erhöhen
- View-Namenskonflikte – Konventionen/Validierung erweitern

### ui-managementstudio
- Logs nur In-Memory – optionales File-Logging
- Validierung Experiments-CRUD erweitern

#### 2025-09-21 – CRUD/Runner-Integration und Pfade
- Symptome:
  - Route `/crud` zeitweise 404; statische Assets nicht geladen
  - „Run Churn“ scheitert mit `ModuleNotFoundError: joblib` (fehlende ML-Deps im UI-venv)
  - Wiederkehrend `AttributeError: ProjectPaths.ui_settings_file` (mehrere `ProjectPaths`-Klassen/Importpfade)
  - Lock-Datei `churn_database.json.lock` blockiert Folgeprozesse nach Fehlern
- Ursachen:
  - Uneinheitliche `sys.path`-Reihenfolge (Submodule), doppelte `ProjectPaths`-Definitionen, fehlende Abhängigkeiten im UI-venv
  - Inkonsequente Pfadauflösung (relativ zu `bl-churn` vs. relativ zum Management Studio)
- Workaround (kurzfristig):
  - ENV setzen: `UI_SETTINGS_PATH` → `bl-churn/config/shared/config/ui_settings.json`
  - BL-Requirements im UI-venv installieren (joblib, scikit-learn, scipy)
  - Lock-Datei bei Fehlern entfernen und Abbruch kommunizieren
- Empfehlung (mittel-/langfristig): siehe `CRUD_REWRITE_PLAN.md` (separater Runner-Service + schlanke UI)

### ui-crud
- Kein HTTPS/Basic-Auth – nur lokal
- Kein Asset-Build – Bedarf bei größeren UIs

## Template für Einträge
```markdown
- <Kurzbeschreibung> – Status: <offen/in Bearbeitung>; Impact: <niedrig/mittel/hoch>; Workaround: <falls vorhanden>; Owner: <Name>; Target-Date: <YYYY-MM-DD>
```

Hinweis: Bitte Änderungen zusätzlich im jeweiligen RUNBOOK unter „Known Issues“ ergänzen.

