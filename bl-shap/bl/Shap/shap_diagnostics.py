#!/usr/bin/env python3
"""
SHAP Diagnostics – Klärung NextSteps Punkt 1
===========================================

Ziel:
- Analysiere, warum einzelne Features (z. B. I_CONSULTING) in shap_local_topk überproportional erscheinen.
- Prüfe fehlende Trainingsfeatures in customer_churn_details (Schnittmengeneffekt).
- Erzeuge Daten für Heatmap (Feature × Rangposition) und kompakte Zusammenfassung.

Leitplanken:
- Datenzugriff ausschließlich via DAL/JSON-DB (keine direkten Dateipfade außerhalb ProjectPaths).
- Pfade aus config/paths_config.ProjectPaths beziehen.
- Keine ML-Fallbacks, keine stillen Fehler – klar scheitern.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.paths_config import ProjectPaths
import sys as _sys

# JSON-DB / DAL – Pfad ergänzen (wie im SHAP-Service)
_JSON_DB_ROOT = ProjectPaths.json_database_directory()
if str(_JSON_DB_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_JSON_DB_ROOT))
from bl.json_database.churn_json_database import ChurnJSONDatabase  # type: ignore
from bl.json_database.sql_query_interface import SQLQueryInterface  # type: ignore


@dataclass
class DiagnosticsConfig:
    top_k: int = 5
    min_feature_count: int = 1  # Features mit weniger Auftritten werden optional gefiltert


class ShapDiagnostics:
    """Diagnostik-Analyse für SHAP-Outputs eines Experiments."""

    def __init__(self, experiment_id: int, config: Optional[DiagnosticsConfig] = None):
        self.experiment_id = int(experiment_id)
        self.cfg = config or DiagnosticsConfig()
        self.paths = ProjectPaths()
        self.db = ChurnJSONDatabase()
        self.sql = SQLQueryInterface()

    # ------------------------------
    # Hilfsfunktionen
    # ------------------------------
    def _load_local_topk_df(self) -> pd.DataFrame:
        """Lädt shap_local_topk aus JSON-DB (persistierte Form) als DataFrame."""
        tables = (self.db.data.get("tables", {}) or {})
        recs = (tables.get("shap_local_topk", {}) or {}).get("records", []) or []
        if not recs:
            raise RuntimeError("Keine shap_local_topk Records in JSON-DB gefunden. SHAP zuvor ausführen.")
        df = pd.DataFrame(recs)
        # Experiment-Filter robust (experiment_id integer)
        if "experiment_id" in df.columns:
            df = df[df["experiment_id"].astype("Int64") == self.experiment_id].copy()
        if df.empty:
            raise RuntimeError(f"Keine shap_local_topk Daten für experiment_id={self.experiment_id} gefunden.")
        # erwartete Spalten prüfen
        expected_cols = {"feature", "rank"}
        missing_cols = expected_cols - set(df.columns)
        if missing_cols:
            raise RuntimeError(f"shap_local_topk fehlt Spalten: {sorted(missing_cols)}")
        return df.reset_index(drop=True)

    def _load_customer_churn_details(self) -> pd.DataFrame:
        """Lädt customer_churn_details via SQL-Interface (DAL)."""
        df = self.sql.execute_query("SELECT * FROM customer_churn_details", output_format="pandas")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            raise RuntimeError("customer_churn_details ist leer oder nicht verfügbar")
        # Experiment-Filter
        if "experiment_id" in df.columns:
            df = df[df["experiment_id"].astype("Int64") == self.experiment_id].copy()
        elif "id_experiments" in df.columns:
            df = df[df["id_experiments"].astype("Int64") == self.experiment_id].copy()
        return df.reset_index(drop=True)

    def _load_model_feature_names(self) -> List[str]:
        """Versucht Feature-Namen aus Metadaten zu laden (analog shap_service)."""
        # Bevorzugt Outbox/Churn experiment_*/churn_model_*_metadata.json, dann bl-churn/models
        candidates: List[Path] = []
        # Outbox-Churn
        base = self.paths.outbox_churn_experiment_directory(self.experiment_id)
        if base.exists():
            candidates += sorted(base.glob(f"churn_model_{self.experiment_id}_*_metadata.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            candidates += sorted(base.glob(f"churn_model_{self.experiment_id}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        # Models-Dir (Fallback)
        mdir = self.paths.models_directory()
        if mdir.exists():
            candidates += sorted(mdir.glob(f"churn_model_{self.experiment_id}_*_metadata.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            candidates += sorted(mdir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

        for md in candidates:
            try:
                meta = json.loads(md.read_text(encoding="utf-8"))
                fn = meta.get("feature_names") or (meta.get("features", {}) or {}).get("feature_names")
                if isinstance(fn, list) and fn:
                    return [str(f) for f in fn]
            except Exception:
                continue
        # Als weiterer Fallback: SHAP Global Summary lesen
        shap_md = self.paths.outbox_shap_experiment_directory(self.experiment_id) / "shap_global_summary.json"
        if shap_md.exists():
            try:
                data = json.loads(shap_md.read_text(encoding="utf-8"))
                rows = (data or {}).get("global_shap", [])
                if rows:
                    return [str(r.get("feature")) for r in rows if r.get("feature")]
            except Exception:
                pass
        raise RuntimeError("Feature-Namen aus Metadaten konnten nicht geladen werden.")

    # ------------------------------
    # Kernanalyse
    # ------------------------------
    @staticmethod
    def _gini(values: List[float]) -> float:
        """Berechnet den Gini-Koeffizienten einer Häufigkeitsverteilung."""
        arr = np.asarray(values, dtype=float)
        if arr.size == 0:
            return 0.0
        if np.all(arr == 0):
            return 0.0
        sorted_arr = np.sort(arr)
        cumvals = np.cumsum(sorted_arr)
        gini = (arr.size + 1 - 2 * np.sum(cumvals) / cumvals[-1]) / arr.size
        return float(gini)

    def analyze(self) -> Dict[str, Any]:
        """Führt die Diagnostik aus und liefert ein Ergebnis-Dict."""
        # 1) shap_local_topk laden und Feature×Rang Matrix erstellen
        df_topk = self._load_local_topk_df()
        top_k = max(1, int(self.cfg.top_k))
        df_topk = df_topk[df_topk["rank"].astype(int) <= top_k].copy()

        # Häufigkeit je Feature insgesamt und je Rang
        feature_counts = df_topk.groupby("feature").size().sort_values(ascending=False)
        total_rows = int(feature_counts.sum()) if len(feature_counts) else 0
        feature_share = (feature_counts / max(1, total_rows)).to_dict()
        rank_feature_counts = df_topk.groupby(["rank", "feature"]).size().unstack(fill_value=0)

        # Gini über Feature-Verteilung (je Rang und gesamt)
        overall_gini = self._gini(feature_counts.tolist())
        gini_by_rank = {int(r): self._gini(rank_feature_counts.loc[r].tolist()) for r in rank_feature_counts.index}

        # 2) Fehlende Trainingsfeatures prüfen
        model_features = []
        missing_features: List[str] = []
        present_features: List[str] = []
        prevalence: Dict[str, float] = {}
        sparse_threshold = 0.05  # 5% als Heuristik für "selten vorhanden"
        try:
            model_features = self._load_model_feature_names()
            cd_df = self._load_customer_churn_details()
            present_set = set(cd_df.columns)
            missing_features = [f for f in model_features if f not in present_set]
            present_features = [f for f in model_features if f in present_set]
            # Prävalenz nur für Features berechnen, die in Top-K auftauchen
            top_features = sorted(set(df_topk["feature"].tolist()))
            for f in top_features:
                if f in cd_df.columns:
                    s = pd.to_numeric(cd_df[f], errors="coerce")
                    prevalence[f] = float(((s.fillna(0) != 0).mean()))
        except Exception as e:
            # Diagnose kann auch ohne diesen Teil fortgeführt werden
            model_features = []
            missing_features = []
            present_features = []
            prevalence = {}
            missing_reason = str(e)
        else:
            missing_reason = ""

        # 3) Ergebnis aufbereiten
        result: Dict[str, Any] = {
            "experiment_id": self.experiment_id,
            "top_k": top_k,
            "feature_frequency": feature_counts.head(50).to_dict(),  # Top-50 für schnelle Übersicht
            "rank_feature_matrix": rank_feature_counts.iloc[:top_k].to_dict(),
            "overall_gini": overall_gini,
            "gini_by_rank": gini_by_rank,
            "feature_share": feature_share,
            "missing_model_features_count": len(missing_features),
            "missing_model_features_examples": missing_features[:10],
            "present_model_features_count": len(present_features),
            "feature_prevalence": prevalence,
            "sparse_threshold": sparse_threshold,
            "sparse_top_features": [f for f, p in prevalence.items() if p <= sparse_threshold],
            "notes": {
                "missing_features_possible_effect": "Fehlende Trainingsfeatures in customer_churn_details können die Verteilung der Top-K-Treiber verzerren (Schnittmenge).",
                "interpretation": "Hoher Gini (nahe 1) weist auf starke Konzentration weniger Treiber hin; niedriger Gini (nahe 0) auf breite Verteilung.",
                "missing_reason": missing_reason,
            },
        }
        return result

    # ------------------------------
    # Export
    # ------------------------------
    def export(self, result: Dict[str, Any]) -> Path:
        out_dir = self.paths.outbox_shap_experiment_directory(self.experiment_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        # Summary JSON
        diag_path = out_dir / "shap_diagnostics_summary.json"
        diag_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        # Heatmap-Daten als CSV: Feature × Rang Counts (breit)
        matrix = result.get("rank_feature_matrix") or {}
        if matrix:
            # matrix ist dict: {feature: {rank: count}} oder {rank: {feature: count}} abhängig von to_dict()
            # oben: unstack → columns = features, index = rank → to_dict() liefert {feature: {rank: count}}
            df = pd.DataFrame(matrix)
            heatmap_csv = out_dir / "shap_diagnostics_heatmap.csv"
            df.to_csv(heatmap_csv, index=True)
        return diag_path


def main(argv: Optional[List[str]] = None) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
    import argparse

    parser = argparse.ArgumentParser(description="SHAP Diagnostics (NextSteps Punkt 1)")
    parser.add_argument("--experiment-id", type=int, required=True, help="Experiment-ID")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K für lokale SHAP-Treiber")
    args = parser.parse_args(argv)

    diag = ShapDiagnostics(experiment_id=args.experiment_id, config=DiagnosticsConfig(top_k=args.top_k))
    result = diag.analyze()
    path = diag.export(result)
    print(f"✅ SHAP Diagnostics gespeichert: {path}")
    print(f"   Overall Gini: {result.get('overall_gini'):.3f}")
    return path, result


if __name__ == "__main__":
    main()


