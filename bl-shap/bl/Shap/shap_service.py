#!/usr/bin/env python3
"""
SHAP Service – Churn Erklärbarkeit (TreeExplainer)
===================================================

Berechnet globale und lokale SHAP-Werte für ein gegebenes Experiment-ID
unter Nutzung der bestehenden DAL und Feature-Pipeline.

Leitplanken:
- Unterstützt Tree-Modelle: RandomForest, XGBoost, LightGBM, CatBoost
- Kein KernelExplainer-Fallback – bei Nicht-Unterstützung: Fail-Fast
- Gleiches Feature-Ordering wie beim Training (aus Model-Metadaten)
- Sampling/Batching via Konfiguration
- Ausgaben in Outbox: dynamic_system_outputs/outbox/shap/experiment_<id>/
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.paths_config import ProjectPaths
import os
import sys as _sys

# DAL / JSON-DB (bl liegt unter json-database/)
_JSON_DB_ROOT = ProjectPaths.json_database_directory()
if str(_JSON_DB_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_JSON_DB_ROOT))
from bl.json_database.churn_json_database import ChurnJSONDatabase  # type: ignore
from bl.json_database.sql_query_interface import SQLQueryInterface  # type: ignore

# Feature-Pipeline (Training-kompatibel) – Pfad zu bl-churn auf sys.path setzen (damit 'bl' Paket auflösbar ist)
_CHURN_ROOT = ProjectPaths.bl_churn_directory()
if str(_CHURN_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_CHURN_ROOT))
from bl.Churn.churn_feature_engine import ChurnFeatureEngine  # type: ignore


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class ShapConfig:
    sample_size: int = 10000
    batch_size: int = 2048
    background_size: int = 500
    top_k: int = 5
    make_plots: bool = False
    seed: int = 42
    top_global_n: int = 50
    aggregate_by_raw: bool = True  # optional: Raw-Feature Aggregation aktivieren
    cluster_by_digitalization: bool = True  # optional: Cluster-Auswertung nach N_DIGITALIZATIONRATE

    @staticmethod
    def from_filesystem() -> "ShapConfig":
        cfg_path = ProjectPaths.shap_config_file()
        if cfg_path.exists():
            try:
                data = _load_json(cfg_path)
                return ShapConfig(
                    sample_size=int(data.get("sample_size", 10000)),
                    batch_size=int(data.get("batch_size", 2048)),
                    background_size=int(data.get("background_size", 500)),
                    top_k=int(data.get("top_k", 5)),
                    make_plots=bool(data.get("make_plots", False)),
                    seed=int(data.get("seed", 42)),
                    top_global_n=int(data.get("top_global_n", 50)),
                    aggregate_by_raw=bool(data.get("aggregate_by_raw", True)),
                    cluster_by_digitalization=bool(data.get("cluster_by_digitalization", True)),
                )
            except Exception:
                # Robust: Verwende Defaults, wenn Config fehlerhaft ist
                return ShapConfig()
        return ShapConfig()


class ShapService:
    def __init__(self, experiment_id: int, config: Optional[ShapConfig] = None):
        self.experiment_id = int(experiment_id)
        self.paths = ProjectPaths()
        self.logger = self._setup_logging()
        self.cfg = config or ShapConfig.from_filesystem()

        # DAL
        self.db = ChurnJSONDatabase()
        self.sql = SQLQueryInterface()

    def _setup_logging(self) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        return logging.getLogger(__name__)

    # ------------------------------
    # Model Loading
    # ------------------------------
    def _find_model_file(self) -> Tuple[Path, Optional[Path]]:
        """Findet Model + Metadata für die experiment_id.
        Sucht bevorzugt in dynamic_system_outputs/<churn_experiments>, fallback bl-churn/models.
        Returns: (model_path, metadata_path or None)
        """
        patterns = [
            # dynamic outputs (neue Pipeline)
            (self.paths.dynamic_system_outputs_directory() / "churn_experiments", f"churn_model_{self.experiment_id}_*.joblib"),
            # legacy models dir
            (self.paths.models_directory(), f"churn_model_{self.experiment_id}_*.joblib"),
            (self.paths.models_directory(), "*.joblib"),  # letzter Fallback: neuestes Modell
        ]

        candidates: List[Path] = []
        for base, glob_pat in patterns:
            try:
                if base.exists():
                    found = sorted(base.glob(glob_pat), key=lambda p: p.stat().st_mtime, reverse=True)
                    candidates.extend(found)
            except Exception:
                continue

        if not candidates:
            raise FileNotFoundError(
                f"Kein gespeichertes Modell gefunden (experiment_id={self.experiment_id}). Bitte Training/Export prüfen."
            )

        model_path = candidates[0]
        # Prefer conventional *_metadata.json, otherwise try sibling .json with same stem
        md_candidates: List[Path] = []
        md1 = Path(str(model_path).replace(".joblib", "_metadata.json"))
        md2 = Path(str(model_path).replace(".joblib", ".json"))
        for md in (md1, md2):
            try:
                if md.exists():
                    md_candidates.append(md)
            except Exception:
                pass
        metadata_path = md_candidates[0] if md_candidates else None
        return model_path, metadata_path

    def _load_model_and_metadata(self) -> Tuple[Any, Dict[str, Any]]:
        from joblib import load as joblib_load  # lazy import

        model_path, metadata_path = self._find_model_file()
        self.logger.info(f"📦 Lade Modell: {model_path}")
        model = joblib_load(str(model_path))

        metadata: Dict[str, Any] = {}
        if metadata_path and metadata_path.exists():
            try:
                metadata = _load_json(metadata_path)
            except Exception as e:
                self.logger.warning(f"⚠️ Metadaten konnten nicht geladen werden: {e}")

        return model, metadata

    # ------------------------------
    # Data Preparation via DAL + Feature-Pipeline
    # ------------------------------
    def _get_experiment_record(self) -> Optional[Dict[str, Any]]:
        try:
            return self.db.get_experiment_by_id(self.experiment_id)
        except Exception:
            return None

    def _get_experiment_backtest_to(self) -> Optional[int]:
        try:
            exp = self._get_experiment_record()
            if not exp:
                return None
            val = exp.get("backtest_to") or exp.get("backtest_to_int")
            return int(val) if val is not None else None
        except Exception:
            return None

    def _load_precomputed_features(self) -> pd.DataFrame:
        """Lädt precomputete Features aus customer_churn_details (per DAL) und filtert optional nach experiment_id."""
        try:
            df = self.sql.execute_query("SELECT * FROM customer_churn_details", output_format="pandas")
        except Exception as e:
            raise RuntimeError(f"customer_churn_details konnte nicht geladen werden: {e}")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            raise RuntimeError("customer_churn_details ist leer oder nicht verfügbar")
        # Filter auf Experiment (robust für unterschiedliche Spaltennamen)
        if "experiment_id" in df.columns:
            df = df[df["experiment_id"].astype("Int64") == self.experiment_id].copy()
        elif "id_experiments" in df.columns:
            df = df[df["id_experiments"].astype("Int64") == self.experiment_id].copy()
        # Optionaler Zeitfilter per ENV: TIMEBASE_FROM (YYYYMM)
        try:
            tb_from = os.environ.get("TIMEBASE_FROM")
            if tb_from and "I_TIMEBASE" in df.columns:
                df = df[df["I_TIMEBASE"].astype("Int64") >= int(tb_from)].copy()
        except Exception:
            pass
        return df.reset_index(drop=True)

    def _build_feature_matrix(self, df_raw: pd.DataFrame, feature_names: List[str]) -> Tuple[pd.DataFrame, np.ndarray, List[str]]:
        """
        Erstellt alle benötigten Features und gibt X in exakt derselben Reihenfolge wie im Training zurück.
        Returns: (df_features_filtered, X, ordered_feature_names)
        """
        # Für Rolling/Enhanced Features benötigen wir die Historie je Kunde
        # Data Dictionary laden, um temporale Features gezielt zu identifizieren
        dd: Optional[Dict[str, Any]] = None
        try:
            dd_path = self.paths.get_data_dictionary_file()
            if dd_path.exists():
                dd = _load_json(dd_path)
        except Exception:
            dd = None
        engine = ChurnFeatureEngine(data_dictionary=dd)

        # Vollständige Feature-Erstellung auf Rohdaten
        df_with_roll = engine.create_rolling_features(df_raw)
        df_with_enh = engine.create_enhanced_features(df_with_roll)

        # Sicherstellen, dass Customer/Timebase vorhanden sind (für spätere Filterung/Exports)
        customer_col = engine._get_customer_column(df_with_enh)
        timebase_col = engine._get_timebase_column(df_with_enh)
        if customer_col not in df_with_enh.columns:
            raise RuntimeError(f"Customer-ID Spalte nicht gefunden (erwartet u.a. '{customer_col}')")

        # Nur Trainingsfeatures in identischer Reihenfolge extrahieren
        missing = [f for f in feature_names if f not in df_with_enh.columns]
        if missing:
            raise RuntimeError(
                f"Es fehlen {len(missing)} Trainingsfeatures in den erzeugten Features. Beispiele: {missing[:10]}"
            )

        df_features_ordered = df_with_enh[feature_names].fillna(0)
        X = df_features_ordered.values.astype(np.float64, copy=False)
        return df_with_enh[[customer_col, timebase_col]].join(df_features_ordered), X, feature_names

    # ------------------------------
    # SHAP Compute
    # ------------------------------
    def _validate_supported_model(self, model: Any) -> None:
        name = type(model).__name__
        supported = {
            "RandomForestClassifier",
            "XGBClassifier",
            "LGBMClassifier",
            "CatBoostClassifier",
        }
        if name not in supported:
            raise RuntimeError(
                f"Nicht unterstützter Modelltyp '{name}'. Unterstützt sind nur Tree-Modelle: "
                "RandomForest, XGBoost, LightGBM, CatBoost. Kein KernelExplainer-Fallback."
            )

    def _compute_shap_values(self, model: Any, X: np.ndarray, background: Optional[np.ndarray] = None) -> np.ndarray:
        # Lazy import (keine ML-Fallbacks, Fehler sollen sichtbar sein)
        import shap  # type: ignore

        self._validate_supported_model(model)

        # Background/Reference Set
        if background is None or len(background) == 0:
            rng = np.random.default_rng(self.cfg.seed)
            bg_size = max(10, min(self.cfg.background_size, X.shape[0]))
            bg_idx = rng.choice(X.shape[0], size=bg_size, replace=False)
            background = X[bg_idx]

        explainer = shap.TreeExplainer(model, data=background)

        # Für Klassifikation: Liste je Klasse möglich → wähle positive Klasse
        shap_values = explainer.shap_values(X, check_additivity=False)
        if isinstance(shap_values, list):
            try:
                # Positive Klasse (1) bevorzugen, sonst letzte Klasse
                classes = list(getattr(model, "classes_", []))
                idx = classes.index(1) if 1 in classes else -1
            except Exception:
                idx = -1
            shap_matrix = np.asarray(shap_values[idx])
        else:
            shap_matrix = np.asarray(shap_values)

        if shap_matrix.shape[0] != X.shape[0]:
            raise RuntimeError("Formfehler bei SHAP-Berechnung: Samplesize inkonsistent")

        return shap_matrix

    # ------------------------------
    # Aggregation & Export
    # ------------------------------
    def _load_feature_mapping(self) -> Dict[str, List[str]]:
        """Lädt Raw→Engineered Feature-Mapping aus der zentralen Config.
        Erwartetes Format: { "I_MAINTENANCE": ["I_MAINTENANCE_L12_sum", ...], ... }
        """
        mapping: Dict[str, List[str]] = {}
        try:
            fmap = self.paths.feature_mapping_file()
            if fmap.exists():
                data = json.loads(fmap.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for raw, lst in data.items():
                        if isinstance(raw, str) and isinstance(lst, list):
                            mapping[raw] = [str(x) for x in lst if isinstance(x, str)]
        except Exception:
            mapping = {}
        return mapping

    def _aggregate_shap_by_raw(self, feature_names: List[str], shap_matrix: np.ndarray) -> Tuple[List[str], np.ndarray, Dict[str, List[str]]]:
        """Aggregiert SHAP-Werte über Engineered-Features je Raw-Feature.
        Returns: (aggregated_feature_names, aggregated_shap_matrix, used_mapping)
        """
        mapping = self._load_feature_mapping()
        if not mapping:
            # Keine Aggregation möglich
            return feature_names, shap_matrix, {}

        name_to_idx = {name: i for i, name in enumerate(feature_names)}
        aggregated_cols: List[str] = []
        aggregated_values: List[np.ndarray] = []
        used_mapping: Dict[str, List[str]] = {}

        used_engineered: set[str] = set()
        for raw, eng_list in mapping.items():
            idxs = [name_to_idx[e] for e in eng_list if e in name_to_idx]
            if not idxs:
                continue
            # Summe der SHAPs über alle zugehörigen engineered Spalten
            agg_vals = shap_matrix[:, idxs].sum(axis=1)
            aggregated_cols.append(raw)
            aggregated_values.append(agg_vals)
            used_mapping[raw] = [feature_names[i] for i in idxs]
            used_engineered.update(used_mapping[raw])

        if not aggregated_cols:
            return feature_names, shap_matrix, {}

        # Optional: Unmapped engineered Features separat erhalten (nicht aggregiert)
        # Für Klarheit liefern wir NUR aggregierte Raw-Features zurück
        agg_matrix = np.vstack([col.reshape(-1, 1) for col in aggregated_values]).T  # shape (n, k)
        return aggregated_cols, agg_matrix, used_mapping

    def _infer_digitalization_cluster(self, df_slice: pd.DataFrame) -> List[str]:
        """Ermittelt pro Zeile eine Cluster-Kategorie für N_DIGITALIZATIONRATE.
        Delegiert an zentrale Segmentierungsfunktion.
        """
        from config.digitalization_segmentation import infer_digitalization_cluster
        return infer_digitalization_cluster(df_slice)
    def _export_global_summary(self, out_dir: Path, feature_names: List[str], shap_matrix: np.ndarray) -> None:
        abs_vals = np.abs(shap_matrix)
        mean_abs = abs_vals.mean(axis=0)
        mean_raw = shap_matrix.mean(axis=0)

        rows = []
        for i, feat in enumerate(feature_names):
            # SHAP kann mehrdimensionale Rückgaben liefern (z. B. multi-output).
            # Für den Export reduzieren wir robust auf Skalar.
            mean_abs_scalar = float(np.asarray(mean_abs[i]).mean())
            mean_raw_scalar = float(np.asarray(mean_raw[i]).mean())
            rows.append({
                "feature": feat,
                "mean_abs_shap": mean_abs_scalar,
                "mean_shap": mean_raw_scalar,
            })

        # Ranking nach mean_abs_shap und Top-N limitieren
        rows.sort(key=lambda r: r["mean_abs_shap"], reverse=True)
        if isinstance(self.cfg.top_global_n, int) and self.cfg.top_global_n > 0:
            rows = rows[: self.cfg.top_global_n]
        for rank, row in enumerate(rows, start=1):
            row["rank"] = rank

        payload = {
            "experiment_id": self.experiment_id,
            "global_shap": rows,
        }

        out_path = out_dir / "shap_global_summary.json"
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self.logger.info(f"💾 Global Summary: {out_path}")

        # Optional: Aggregierte Global-Summary nach Raw-Features
        if self.cfg.aggregate_by_raw:
            try:
                agg_feats, agg_shap, used_map = self._aggregate_shap_by_raw(feature_names, shap_matrix)
                if agg_feats and len(agg_feats) > 0 and agg_shap is not None:
                    abs_vals_a = np.abs(agg_shap)
                    mean_abs_a = abs_vals_a.mean(axis=0)
                    mean_raw_a = agg_shap.mean(axis=0)
                    rows_a = []
                    for i, feat in enumerate(agg_feats):
                        rows_a.append({
                            "feature": feat,
                            "mean_abs_shap": float(np.asarray(mean_abs_a[i]).mean()),
                            "mean_shap": float(np.asarray(mean_raw_a[i]).mean()),
                            "components": used_map.get(feat, []),
                        })
                    rows_a.sort(key=lambda r: r["mean_abs_shap"], reverse=True)
                    if isinstance(self.cfg.top_global_n, int) and self.cfg.top_global_n > 0:
                        rows_a = rows_a[: self.cfg.top_global_n]
                    for rank, row in enumerate(rows_a, start=1):
                        row["rank"] = rank
                    payload_a = {
                        "experiment_id": self.experiment_id,
                        "global_shap_aggregated": rows_a,
                    }
                    out_path_a = out_dir / "shap_global_summary_aggregated.json"
                    out_path_a.write_text(json.dumps(payload_a, indent=2, ensure_ascii=False), encoding="utf-8")
                    self.logger.info(f"💾 Global Summary (aggregiert): {out_path_a}")
            except Exception as e:
                self.logger.warning(f"⚠️ Aggregierte Global-Summary übersprungen: {e}")

    def _export_global_by_digitalization(self, out_dir: Path, df_slice_for_groups: pd.DataFrame, feature_names: List[str], shap_matrix: np.ndarray) -> None:
        try:
            clusters = self._infer_digitalization_cluster(df_slice_for_groups)
            if not clusters:
                return
            # Gruppen bilden
            from collections import defaultdict
            grp_to_idx: Dict[str, List[int]] = defaultdict(list)
            for i, lab in enumerate(clusters):
                grp_to_idx[str(lab)].append(i)
            result: Dict[str, List[Dict[str, Any]]] = {}
            for grp, idxs in grp_to_idx.items():
                if not idxs:
                    continue
                sub = shap_matrix[idxs, :]
                abs_vals = np.abs(sub)
                mean_abs = abs_vals.mean(axis=0)
                mean_raw = sub.mean(axis=0)
                rows = []
                for j, feat in enumerate(feature_names):
                    rows.append({
                        "feature": feat,
                        "mean_abs_shap": float(np.asarray(mean_abs[j]).mean()),
                        "mean_shap": float(np.asarray(mean_raw[j]).mean()),
                    })
                rows.sort(key=lambda r: r["mean_abs_shap"], reverse=True)
                topn = rows[: self.cfg.top_global_n] if isinstance(self.cfg.top_global_n, int) and self.cfg.top_global_n > 0 else rows
                # rank annotieren
                for rank, row in enumerate(topn, start=1):
                    row["rank"] = rank
                result[str(grp)] = topn
            out = {
                "experiment_id": self.experiment_id,
                "global_shap_by_digitalization": result
            }
            p = out_dir / "shap_global_summary_by_digitalization.json"
            p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            self.logger.info(f"💾 Global Summary (by digitalization): {p}")
        except Exception as e:
            self.logger.warning(f"⚠️ SHAP Digitalization-Aggregat fehlgeschlagen: {e}")

    def _export_local_topk(self, out_dir: Path, df_meta: pd.DataFrame, X: np.ndarray, shap_matrix: np.ndarray, feature_names: List[str]) -> None:
        top_k = max(1, int(self.cfg.top_k))

        customer_col = "Kunde" if "Kunde" in df_meta.columns else df_meta.columns[0]
        timebase_col = "I_TIMEBASE" if "I_TIMEBASE" in df_meta.columns else None

        lines: List[str] = []
        for i in range(X.shape[0]):
            vals = X[i]
            shaps = shap_matrix[i]
            shaps_arr = np.asarray(shaps)
            # Ranking über Features: bei multi-output mittlere |SHAP| je Feature verwenden
            if shaps_arr.ndim > 1:
                scores = np.mean(np.abs(shaps_arr), axis=0)
            else:
                scores = np.abs(shaps_arr)
            idx_sorted = np.argsort(scores)[::-1][:top_k]
            top_items = []
            for idx in idx_sorted:
                s = float(np.asarray(shaps_arr)[..., idx].mean())
                v = float(np.asarray(vals[idx]).mean())
                top_items.append({
                    "feature": feature_names[idx],
                    "value": v,
                    "shap": s,
                    "sign": "positive" if s >= 0 else "negative",
                })

            rec = {
                "experiment_id": self.experiment_id,
                "customer_id": int(df_meta.iloc[i][customer_col]) if pd.notna(df_meta.iloc[i][customer_col]) else None,
                "timebase": int(df_meta.iloc[i][timebase_col]) if timebase_col and pd.notna(df_meta.iloc[i][timebase_col]) else None,
                "topk": top_items,
            }
            lines.append(json.dumps(rec, ensure_ascii=False))

        out_path = out_dir / "shap_local_topk.jsonl"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        self.logger.info(f"💾 Local Top-K: {out_path} ({len(lines)} Zeilen)")

        # Optional: Aggregierte Local Top-K nach Raw-Features (nur SHAP, ohne value)
        if self.cfg.aggregate_by_raw:
            try:
                agg_feats, agg_shap, _used_map = self._aggregate_shap_by_raw(feature_names, shap_matrix)
                if agg_feats and len(agg_feats) > 0 and agg_shap is not None:
                    lines_a: List[str] = []
                    k = max(1, int(self.cfg.top_k))
                    n_cols = int(agg_shap.shape[1]) if hasattr(agg_shap, "shape") and len(getattr(agg_shap, "shape", [])) >= 2 else 0
                    # Sicherstellen, dass wir nicht über verfügbare Spalten hinausgehen
                    k_eff = min(k, n_cols, len(agg_feats))
                    if k_eff <= 0:
                        raise RuntimeError("Aggregierte SHAP-Matrix hat keine Spalten – Mapping prüfen")
                    for i in range(agg_shap.shape[0]):
                        shaps = agg_shap[i]
                        scores = np.abs(np.asarray(shaps))
                        order = np.argsort(scores)[::-1]
                        idx_sorted = [int(ix) for ix in order[:k_eff] if 0 <= int(ix) < len(agg_feats)]
                        top_items = []
                        for idx in idx_sorted:
                            s = float(np.asarray(shaps)[..., idx].mean())
                            feat_name = agg_feats[idx] if idx < len(agg_feats) else f"agg_{idx}"
                            top_items.append({
                                "feature": feat_name,
                                "shap": s,
                                "sign": "positive" if s >= 0 else "negative",
                            })
                        rec = {
                            "experiment_id": self.experiment_id,
                            "customer_id": int(df_meta.iloc[i]["Kunde"]) if "Kunde" in df_meta.columns and pd.notna(df_meta.iloc[i]["Kunde"]) else None,
                            "timebase": int(df_meta.iloc[i]["I_TIMEBASE"]) if "I_TIMEBASE" in df_meta.columns and pd.notna(df_meta.iloc[i]["I_TIMEBASE"]) else None,
                            "topk": top_items,
                        }
                        lines_a.append(json.dumps(rec, ensure_ascii=False))
                    out_path_la = out_dir / "shap_local_topk_aggregated.jsonl"
                    out_path_la.write_text("\n".join(lines_a), encoding="utf-8")
                    self.logger.info(f"💾 Local Top-K (aggregiert): {out_path_la} ({len(lines_a)} Zeilen)")
            except Exception as e:
                self.logger.warning(f"⚠️ Aggregiertes Local Top-K übersprungen: {e}")

    def _maybe_make_plots(self, out_dir: Path, X: np.ndarray, shap_matrix: np.ndarray, feature_names: List[str]) -> None:
        if not self.cfg.make_plots:
            return
        try:
            import shap  # type: ignore
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt  # type: ignore

            # Bar Plot
            plt.figure(figsize=(10, 6))
            shap.summary_plot(shap_matrix, features=X, feature_names=feature_names, plot_type="bar", show=False)
            bar_path = out_dir / "shap_summary_bar.png"
            plt.tight_layout()
            plt.savefig(bar_path, dpi=150)
            plt.close()

            # Beeswarm
            plt.figure(figsize=(10, 6))
            shap.summary_plot(shap_matrix, features=X, feature_names=feature_names, show=False)
            swarm_path = out_dir / "shap_beeswarm.png"
            plt.tight_layout()
            plt.savefig(swarm_path, dpi=150)
            plt.close()

            self.logger.info("🖼️  SHAP-Plots erzeugt")
        except Exception as e:
            self.logger.warning(f"⚠️ Plot-Erzeugung fehlgeschlagen: {e}")

    # ------------------------------
    # Public API
    # ------------------------------
    def run(self) -> Path:
        # Ausgabeverzeichnis
        out_dir = _ensure_dir(self.paths.outbox_shap_experiment_directory(self.experiment_id))

        # Model und Metadaten
        model, metadata = self._load_model_and_metadata()
        feature_names: List[str] = []
        if isinstance(metadata, dict):
            # Unterstütze beide Formate: top-level 'feature_names' und nested 'features.feature_names'
            fn = metadata.get("feature_names")
            if not fn:
                fn = (metadata.get("features", {}) or {}).get("feature_names")
            if isinstance(fn, list):
                feature_names = fn
        if not feature_names:
            raise RuntimeError("Feature-Namen konnten nicht aus Metadaten geladen werden – SHAP abgebrochen")

        # Daten laden (DAL) – precomputed engineered Features verwenden
        df_cd = self._load_precomputed_features()
        # Falls TIMEBASE_FROM nicht gesetzt ist, automatisch aus Experiment backtest_from ableiten
        try:
            if "I_TIMEBASE" in df_cd.columns and not os.environ.get("TIMEBASE_FROM"):
                exp = self._get_experiment_record() or {}
                tb_from = exp.get("backtest_from") or exp.get("backtest_from_int")
                if tb_from:
                    df_cd = df_cd[df_cd["I_TIMEBASE"].astype("Int64") >= int(tb_from)].copy()
        except Exception:
            pass
        # Meta-Spalten
        customer_col = "Kunde" if "Kunde" in df_cd.columns else None
        timebase_col = "I_TIMEBASE" if "I_TIMEBASE" in df_cd.columns else None
        # Features identisch zur Modell-Featureliste, aber nur die im Experiment verfügbaren verwenden
        available_set = set(df_cd.columns)
        final_features: List[str] = [f for f in feature_names if f in available_set]
        missing = [f for f in feature_names if f not in available_set]
        if missing:
            self.logger.warning(
                f"⚠️ {len(missing)} Modell-Features fehlen in customer_churn_details (Experiment {self.experiment_id}). "
                f"Beispiele: {missing[:10]} — verwende Schnittmenge ({len(final_features)} Features)."
            )
        if not final_features:
            raise RuntimeError("Keine der Modell-Features sind in customer_churn_details vorhanden – SHAP abgebrochen")
        df_features_ordered = df_cd[final_features].fillna(0)
        X_full = df_features_ordered.values.astype(np.float64, copy=False)
        # df_meta bestimmen
        meta_cols: List[str] = []
        if customer_col:
            meta_cols.append(customer_col)
        if timebase_col:
            meta_cols.append(timebase_col)
        df_meta = df_cd[meta_cols].copy() if meta_cols else pd.DataFrame(index=df_cd.index)
        ordered_features = final_features

        # Background aus Trainingsfenster des Experiments wählen (falls möglich)
        background_X: Optional[np.ndarray] = None
        try:
            exp = self._get_experiment_record() or {}
            tr_from = exp.get("training_from") or exp.get("training_from_int")
            tr_to = exp.get("training_to") or exp.get("training_to_int")
            if tr_from and tr_to and "I_TIMEBASE" in df_cd.columns:
                bg_df = df_cd[(df_cd["I_TIMEBASE"].astype("Int64") >= int(tr_from)) & (df_cd["I_TIMEBASE"].astype("Int64") <= int(tr_to))]
                if not bg_df.empty:
                    background_X = bg_df[ordered_features].fillna(0).values.astype(np.float64, copy=False)
        except Exception:
            background_X = None

        # Sampling
        rng = np.random.default_rng(self.cfg.seed)
        n = X_full.shape[0]
        if n == 0:
            raise RuntimeError("Keine Datenzeilen für SHAP-Berechnung gefunden (nach Filterung)")
        sample_n = min(int(self.cfg.sample_size), n)
        sampled_idx = None  # merke Indizes zur späteren Auswertung (z. B. Digitalization-Gruppen)
        if sample_n < n:
            idx = rng.choice(n, size=sample_n, replace=False)
            sampled_idx = idx
            df_meta = df_meta.iloc[idx]
            X = X_full[idx]
        else:
            X = X_full

        # SHAP rechnen
        shap_matrix = self._compute_shap_values(model, X, background=background_X)

        # Exporte
        self._export_global_summary(out_dir, ordered_features, shap_matrix)
        self._export_local_topk(out_dir, df_meta.reset_index(drop=True), X, shap_matrix, ordered_features)
        # Digitalization-Cluster (optional)
        if self.cfg.cluster_by_digitalization:
            try:
                # Für die Clusterbildung benötigen wir die Digitalization-Spalten aus df_cd –
                # nicht nur die Meta-Spalten. Wähle dazu denselben Zeilenausschnitt wie für X/df_meta.
                if sampled_idx is not None:
                    df_for_groups = df_cd.iloc[sampled_idx].reset_index(drop=True)
                else:
                    df_for_groups = df_cd.reset_index(drop=True)
                self._export_global_by_digitalization(out_dir, df_for_groups, ordered_features, shap_matrix)
            except Exception:
                pass
        self._maybe_make_plots(out_dir, X, shap_matrix, ordered_features)

        # Kurzer Report
        self.logger.info(
            f"SHAP abgeschlossen: n={X.shape[0]}, d={X.shape[1]}, top_k={self.cfg.top_k}, seed={self.cfg.seed}"
        )

        # Persistenz in JSON-DB
        try:
            _global_json = json.loads((out_dir / "shap_global_summary.json").read_text(encoding="utf-8"))
            _rows = _global_json.get("global_shap", []) if isinstance(_global_json, dict) else []
            self._persist_global_to_jsondb(rows=_rows)
        except Exception:
            pass
        # Digitalization-Cluster persistieren
        if self.cfg.cluster_by_digitalization:
            try:
                _byd_json = json.loads((out_dir / "shap_global_summary_by_digitalization.json").read_text(encoding="utf-8"))
                _map = _byd_json.get("global_shap_by_digitalization", {}) if isinstance(_byd_json, dict) else {}
                self._persist_global_by_digitalization_to_jsondb(_map)
            except Exception:
                pass
        try:
            self._persist_local_to_jsondb(out_dir / "shap_local_topk.jsonl")
        except Exception:
            pass

        # Persistenz: Aggregierte Varianten
        if self.cfg.aggregate_by_raw:
            try:
                _global_json_a = json.loads((out_dir / "shap_global_summary_aggregated.json").read_text(encoding="utf-8"))
                _rows_a = _global_json_a.get("global_shap_aggregated", []) if isinstance(_global_json_a, dict) else []
                self._persist_global_aggregated_to_jsondb(rows=_rows_a)
            except Exception:
                pass
            try:
                self._persist_local_aggregated_to_jsondb(out_dir / "shap_local_topk_aggregated.jsonl")
            except Exception:
                pass

        return out_dir

    # ------------------------------
    # Persistence to JSON-DB
    # ------------------------------
    def _ensure_table(self, name: str, schema: Dict[str, Dict[str, str]]) -> None:
        try:
            tables = self.db.data.setdefault("tables", {})
            if name not in tables:
                tables[name] = {"description": name, "source": "shap", "schema": schema, "records": []}
        except Exception:
            pass

    def _persist_global_to_jsondb(self, rows: List[Dict[str, Any]]) -> None:
        schema = {
            "experiment_id": {"display_type": "integer"},
            "feature": {"display_type": "text"},
            "mean_abs_shap": {"display_type": "decimal"},
            "mean_shap": {"display_type": "decimal"},
            "rank": {"display_type": "integer"},
            "dt_inserted": {"display_type": "datetime"}
        }
        self._ensure_table("shap_global", schema)
        recs = self.db.data["tables"]["shap_global"]["records"]
        from datetime import datetime as _dt
        for r in rows:
            recs.append({
                "experiment_id": int(self.experiment_id),
                "feature": r.get("feature"),
                "mean_abs_shap": r.get("mean_abs_shap"),
                "mean_shap": r.get("mean_shap"),
                "rank": r.get("rank"),
                "dt_inserted": _dt.now().isoformat()
            })
        self.db.save()

    def _persist_local_to_jsondb(self, jsonl_path: Path) -> None:
        schema = {
            "experiment_id": {"display_type": "integer"},
            "Kunde": {"display_type": "integer"},
            "I_TIMEBASE": {"display_type": "integer"},
            "feature": {"display_type": "text"},
            "value": {"display_type": "decimal"},
            "shap": {"display_type": "decimal"},
            "sign": {"display_type": "text"},
            "rank": {"display_type": "integer"},
            "dt_inserted": {"display_type": "datetime"}
        }
        self._ensure_table("shap_local_topk", schema)
        recs = self.db.data["tables"]["shap_local_topk"]["records"]
        from datetime import datetime as _dt
        # JSONL einlesen und in flache Records zerlegen
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                cust = obj.get("customer_id")
                tb = obj.get("timebase")
                topk = obj.get("topk") or []
                for rank, item in enumerate(topk, start=1):
                    recs.append({
                        "experiment_id": int(self.experiment_id),
                        "Kunde": cust,
                        "I_TIMEBASE": tb,
                        "feature": item.get("feature"),
                        "value": item.get("value"),
                        "shap": item.get("shap"),
                        "sign": item.get("sign"),
                        "rank": rank,
                        "dt_inserted": _dt.now().isoformat()
                    })
        self.db.save()

    def _persist_global_by_digitalization_to_jsondb(self, grp_map: Dict[str, List[Dict[str, Any]]]) -> None:
        schema = {
            "experiment_id": {"display_type": "integer"},
            "digitalization_group": {"display_type": "text"},
            "feature": {"display_type": "text"},
            "mean_abs_shap": {"display_type": "decimal"},
            "mean_shap": {"display_type": "decimal"},
            "rank": {"display_type": "integer"},
            "dt_inserted": {"display_type": "datetime"}
        }
        self._ensure_table("shap_global_by_digitalization", schema)
        recs = self.db.data["tables"]["shap_global_by_digitalization"]["records"]
        from datetime import datetime as _dt
        for grp, rows in (grp_map or {}).items():
            if not isinstance(rows, list):
                continue
            for r in rows:
                recs.append({
                    "experiment_id": int(self.experiment_id),
                    "digitalization_group": str(grp),
                    "feature": r.get("feature"),
                    "mean_abs_shap": r.get("mean_abs_shap"),
                    "mean_shap": r.get("mean_shap"),
                    "rank": r.get("rank"),
                    "dt_inserted": _dt.now().isoformat()
                })
        self.db.save()

    def _persist_global_aggregated_to_jsondb(self, rows: List[Dict[str, Any]]) -> None:
        schema = {
            "experiment_id": {"display_type": "integer"},
            "feature": {"display_type": "text"},
            "mean_abs_shap": {"display_type": "decimal"},
            "mean_shap": {"display_type": "decimal"},
            "rank": {"display_type": "integer"},
            "components": {"display_type": "text"},
            "dt_inserted": {"display_type": "datetime"}
        }
        self._ensure_table("shap_global_aggregated", schema)
        recs = self.db.data["tables"]["shap_global_aggregated"]["records"]
        from datetime import datetime as _dt
        for r in rows:
            recs.append({
                "experiment_id": int(self.experiment_id),
                "feature": r.get("feature"),
                "mean_abs_shap": r.get("mean_abs_shap"),
                "mean_shap": r.get("mean_shap"),
                "rank": r.get("rank"),
                "components": ",".join(r.get("components", []) if isinstance(r.get("components"), list) else []),
                "dt_inserted": _dt.now().isoformat()
            })
        self.db.save()

    def _persist_local_aggregated_to_jsondb(self, jsonl_path: Path) -> None:
        schema = {
            "experiment_id": {"display_type": "integer"},
            "Kunde": {"display_type": "integer"},
            "I_TIMEBASE": {"display_type": "integer"},
            "feature": {"display_type": "text"},
            "shap": {"display_type": "decimal"},
            "sign": {"display_type": "text"},
            "rank": {"display_type": "integer"},
            "dt_inserted": {"display_type": "datetime"}
        }
        self._ensure_table("shap_local_topk_aggregated", schema)
        recs = self.db.data["tables"]["shap_local_topk_aggregated"]["records"]
        from datetime import datetime as _dt
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                cust = obj.get("customer_id")
                tb = obj.get("timebase")
                topk = obj.get("topk") or []
                for rank, item in enumerate(topk, start=1):
                    recs.append({
                        "experiment_id": int(self.experiment_id),
                        "Kunde": cust,
                        "I_TIMEBASE": tb,
                        "feature": item.get("feature"),
                        "shap": item.get("shap"),
                        "sign": item.get("sign"),
                        "rank": rank,
                        "dt_inserted": _dt.now().isoformat()
                    })
        self.db.save()



