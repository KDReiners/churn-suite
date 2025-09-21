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

### ui-crud
- Kein HTTPS/Basic-Auth – nur lokal
- Kein Asset-Build – Bedarf bei größeren UIs

## Template für Einträge
```markdown
- <Kurzbeschreibung> – Status: <offen/in Bearbeitung>; Impact: <niedrig/mittel/hoch>; Workaround: <falls vorhanden>; Owner: <Name>; Target-Date: <YYYY-MM-DD>
```

Hinweis: Bitte Änderungen zusätzlich im jeweiligen RUNBOOK unter „Known Issues“ ergänzen.

