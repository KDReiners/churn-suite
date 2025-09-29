#!/usr/bin/env python3
"""
CLI Runner für SHAP-Berechnung

Beispiel:
  python -m bl_shap.bl.Shap.shap_runner --experiment-id 1 --sample-size 10000 --top-k 5 --plots 0

oder via Makefile-Target:
  make shap EXP_ID=1 SAMPLE_SIZE=10000 TOPK=5
"""

from __future__ import annotations

import argparse
import os
from typing import Optional

from Shap.shap_service import ShapService, ShapConfig


def _bool_from_str(v: str) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run SHAP for given experiment")
    parser.add_argument("--experiment-id", type=int, required=False, default=int(os.environ.get("EXP_ID", "0")))
    parser.add_argument("--sample-size", type=int, default=int(os.environ.get("SAMPLE_SIZE", "10000")))
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("BATCH_SIZE", "2048")))
    parser.add_argument("--background-size", type=int, default=int(os.environ.get("BG_SIZE", "500")))
    parser.add_argument("--top-k", type=int, default=int(os.environ.get("TOPK", "5")))
    parser.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "42")))
    parser.add_argument("--plots", type=str, default=os.environ.get("PLOTS", "0"))

    args = parser.parse_args(argv)

    if not args.experiment_id or args.experiment_id <= 0:
        print("❌ Bitte --experiment-id (oder ENV EXP_ID) angeben > 0")
        return 2

    cfg = ShapConfig(
        sample_size=args.sample_size,
        batch_size=args.batch_size,
        background_size=args.background_size,
        top_k=args.top_k,
        make_plots=_bool_from_str(args.plots),
        seed=args.seed,
    )

    service = ShapService(experiment_id=args.experiment_id, config=cfg)
    out_dir = service.run()
    print(f"✅ SHAP Artefakte: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


