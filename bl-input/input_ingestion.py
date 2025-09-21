"""
INPUT INGESTION MODULE
======================

Zentrale, domänen-agnostische CSV→Stage0 Ingestion.

- Delegiert die eigentliche Analyse/Speicherung an `bl/Churn/Step0_InputAnalysis.py`
- Registriert erzeugte Stage0-Dateien optional in der JSON-Datenbank
- Verwendet ausschließlich `ProjectPaths` für Pfade

Hinweis: Keine Logik-Duplikation – Step0 bleibt der alleinige Erzeuger.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from config.paths_config import ProjectPaths

# Step0-Delegation
from bl.Churn.Step0_InputAnalysis import analyze_csv_input, CSVStructureAnalyzer

# JSON-DB (nur für optionale Registrierung der erzeugten Datei)
from bl.json_database.churn_json_database import ChurnJSONDatabase


class InputIngestionService:
    """
    Domänen-agnostischer Service zur Ingestion von CSV-Eingabedaten in Stage0.

    Responsibilities:
    - CSV-Hashing/Analyse delegiert an Step0 (keine Duplikation)
    - Erzeugte Stage0-Datei lokalisieren (`stage0_cache/<hash>.json`)
    - Optional: Registrierung in JSON-DB (Files-Tabelle)
    """

    def __init__(self):
        self.stage0_dir: Path = ProjectPaths.dynamic_system_outputs_directory() / "stage0_cache"
        ProjectPaths.ensure_directory_exists(self.stage0_dir)

    def ingest_csv_to_stage0(
        self,
        csv_path: Path | str,
        force_reanalysis: bool = False,
        register_in_json_db: bool = True,
    ) -> Tuple[Optional[Path], Dict[str, Any]]:
        """
        Führt CSV→Stage0-Ingestion durch und gibt Pfad zur Stage0-Datei zurück.

        Args:
            csv_path: Pfad zur Eingabe-CSV
            force_reanalysis: True erzwingt Neu-Analyse trotz Cache
            register_in_json_db: File-Registrierung in JSON-DB (Files-Tabelle)

        Returns:
            (stage0_file_path, results_dict)
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            return None, {"error": f"CSV not found: {csv_path}"}

        # Delegation an Step0 (speichert automatisch <hash>.json in stage0_cache)
        results: Dict[str, Any] = analyze_csv_input(str(csv_path), force_reanalysis=force_reanalysis)
        if isinstance(results, dict) and results.get("error"):
            return None, results

        csv_hash: Optional[str] = results.get("csv_hash")
        if not csv_hash:
            return None, {"error": "csv_hash missing in Step0 results"}

        stage0_path: Path = self.stage0_dir / f"{csv_hash}.json"
        if not stage0_path.exists():
            # Step0 sollte gespeichert haben – falls nicht, ist dies ein Fehlerzustand
            return None, {"error": f"Stage0 file not found after analysis: {stage0_path}"}

        if register_in_json_db:
            try:
                db = ChurnJSONDatabase()
                db.create_file_record(file_name=stage0_path.name, source_type="stage0_cache")
                db.save()  # Persistiere Änderungen
            except Exception as e:
                # Registrierung ist optional – Fehler nicht eskalieren, aber zurückmelden
                results.setdefault("warnings", []).append(f"JSON-DB registration failed: {e}")

        return stage0_path, results

    def ensure_stage0_for_latest_input(
        self,
        force_reanalysis: bool = False,
        register_in_json_db: bool = True,
    ) -> Tuple[Optional[Path], Dict[str, Any]]:
        """
        Komfortfunktion: Verwendet `ProjectPaths.main_churn_data_file()`.
        """
        return self.ingest_csv_to_stage0(
            ProjectPaths.main_churn_data_file(),
            force_reanalysis=force_reanalysis,
            register_in_json_db=register_in_json_db,
        )


def ingest_csv_to_stage0(
    csv_path: Path | str,
    force_reanalysis: bool = False,
    register_in_json_db: bool = True,
) -> Tuple[Optional[Path], Dict[str, Any]]:
    """Convenience-Funktion ohne explizite Service-Instanziierung."""
    return InputIngestionService().ingest_csv_to_stage0(
        csv_path=csv_path,
        force_reanalysis=force_reanalysis,
        register_in_json_db=register_in_json_db,
    )


