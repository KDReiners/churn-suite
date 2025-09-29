Last reviewed: 2025-09-27

# bl-shap

Zweck: SHAP‑Erklärbarkeit für Churn/Cox‑Modelle bereitstellen (global und lokal), Artefakte exportieren und nachgelagerte Module (CF/Reporting/UI) versorgen.

## Architektur
- Hält sich an die Projekt‑Leitplanken:
  - Datenzugriff ausschließlich über DAL (`*/config/data_access_layer.py`), zentrale Pfadsteuerung (`*/config/paths_config.py`).
  - Keine Businesslogik im Datenzugriff.
  - Artefakte (JSON/CSV/Bilder) in `dynamic_system_outputs/outbox/shap/experiment_<id>/`.
- Konsumiert Modelle/Features aus `bl-churn` bzw. `bl-cox`.
- Liefert SHAP‑Artefakte an `bl-counterfactuals` (Whitelist/Bounds) und UI.

## Nutzung

- Make-Target:
  - `make shap EXP_ID=1 SAMPLE_SIZE=10000 TOPK=5` (weitere ENV: `BG_SIZE`, `BATCH_SIZE`, `PLOTS=1`)
- Direkt per CLI:
  - `python -m bl_shap.bl.Shap.shap_runner --experiment-id 1 --sample-size 10000 --top-k 5`

Konfiguration über zentrale Datei `json-database/config/shared/config/shap_config.json`:

```json
{
  "sample_size": 10000,
  "batch_size": 2048,
  "background_size": 500,
  "top_k": 5,
  "top_global_n": 50,
  "make_plots": false,
  "seed": 42
}
```

## Outputs

- Outbox: `dynamic_system_outputs/outbox/shap/experiment_<id>/`
  - `shap_global_summary.json`: Liste von Objekten {feature, mean_abs_shap, mean_shap, rank}
  - `shap_local_topk.jsonl`: Zeilenweise {experiment_id, customer_id, timebase, topk:[{feature, value, shap, sign}]}
  - Optional: `shap_summary_bar.png`, `shap_beeswarm.png` (bei `make_plots=true`)

## Hinweise

- Unterstützte Modelle: RandomForest, XGBoost, LightGBM, CatBoost (TreeExplainer). Keine Fallbacks.
- Feature‑Names/Order werden aus Model‑Metadaten geladen; Feature‑Pipeline (Rolling/Enhanced) wird identisch angewendet.
- Datenzugriff: ausschließlich via DAL/JSON‑DB (`rawdata_original` View). Kein direkter CSV‑Zugriff.

Details zu noch offenen Punkten siehe `nextSteps.md`.

## Kurzüberblick: Vorgehen & Status

- Quelle: Precomputete engineered Features aus JSON‑DB `customer_churn_details`, gefiltert per `experiment_id` (und optional `TIMEBASE_FROM`).
- Modell: Laden aus `bl-churn/models/`; Featureliste aus Modell‑Metadaten; strikte Reihenfolge; fehlende Features → Schnittmenge (wird geloggt).
- Background (TreeExplainer): Kunden aus Trainingsfenster des Experiments (sofern vorhanden), sonst zufälliges Subset aus X.
- Outputs: Global Top‑50 (`top_global_n`) und lokal Top‑K je Kunde; optional Plots.
- Persistenz: Artefakte im Outbox‑Pfad; zusätzlich JSON‑DB Tabellen `shap_global` und `shap_local_topk` (CF/SQL‑fähig).

## Interaktion mit CF

- Global‑Whitelist: `SELECT feature FROM shap_global WHERE experiment_id=? ORDER BY rank LIMIT N;`
- Individuelle Treiber: `SELECT * FROM shap_local_topk WHERE experiment_id=? AND Kunde=? ORDER BY rank;`
- Richtungsableitung: Spalte `sign` pro Feature (positive/negative) als Indiz für Maßnahmen‑Bounds.

