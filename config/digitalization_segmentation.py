#!/usr/bin/env python3
"""
Einfache Segmentierung für N_DIGITALIZATIONRATE.

Rückgabe: Liste von Cluster-Labels (String) mit gleicher Länge wie df_slice.

Heuristik:
- Falls One-Hot-Bins wie N_DIGITALIZATIONRATE_* vorhanden sind, wähle pro Zeile die Spalte
  mit dem größten Wert als Label.
- Sonst, falls eine numerische Spalte N_DIGITALIZATIONRATE existiert, bilde Bins.
- Fallback: gib eine Default-Klasse "unknown" pro Zeile zurück.
"""

from __future__ import annotations

from typing import List

import pandas as pd  # type: ignore


def infer_digitalization_cluster(df_slice: pd.DataFrame) -> List[str]:
    if df_slice is None or df_slice.empty:
        return []

    cols = list(df_slice.columns)

    # 1) One-Hot-Bins nutzen, falls vorhanden
    bin_cols = [c for c in cols if c.startswith("N_DIGITALIZATIONRATE_")]
    if bin_cols:
        # Wähle die Spalte mit dem maximalen Wert je Zeile als Label
        try:
            sub = df_slice[bin_cols].fillna(0)
            idx = sub.values.argmax(axis=1)
            labels = [bin_cols[i] if 0 <= i < len(bin_cols) else "unknown" for i in idx]
            return labels
        except Exception:
            pass

    # 2) Numerische Spalte in Bins mappen
    if "N_DIGITALIZATIONRATE" in df_slice.columns:
        try:
            s = pd.to_numeric(df_slice["N_DIGITALIZATIONRATE"], errors="coerce").fillna(0)
            # Einfache Bins (anpassbar)
            bins = [-1e9, 0.2, 0.4, 0.6, 0.8, 1e9]
            names = [
                "N_DIGITALIZATIONRATE_0.2",
                "N_DIGITALIZATIONRATE_0.4",
                "N_DIGITALIZATIONRATE_0.6",
                "N_DIGITALIZATIONRATE_0.8",
                "N_DIGITALIZATIONRATE_1.0",
            ]
            cats = pd.cut(s, bins=bins, labels=names, include_lowest=True)
            return [str(x) if pd.notna(x) else "unknown" for x in cats]
        except Exception:
            pass

    # 3) Fallback
    return ["unknown"] * len(df_slice)



