from __future__ import annotations

from pathlib import Path
from typing import Optional
import os


class ProjectPaths:
    """
    Zentrale Pfadsteuerung für das Repository.

    Regeln:
    - Keine Side-Effects bei Import
    - Rückgaben sind immer Path-Objekte
    - Environment-Overrides respektieren (z. B. OUTBOX_ROOT)
    """

    # -------------------------
    # Basisorte
    # -------------------------
    @staticmethod
    def project_root() -> Path:
        # Diese Datei liegt unter <ROOT>/config/paths_config.py
        return Path(__file__).resolve().parents[1]

    @staticmethod
    def _existing_first(*candidates: Path) -> Path:
        for candidate in candidates:
            if candidate.exists():
                return candidate
        # Falls keiner existiert, gib den ersten (bevorzugten) trotzdem zurück
        return candidates[0]

    # -------------------------
    # Konfiguration
    # -------------------------
    @staticmethod
    def config_directory() -> Path:
        root = ProjectPaths.project_root()
        # Präferenz: json-database/config/shared/config, dann bl-churn/config/shared/config
        return ProjectPaths._existing_first(
            root / "json-database" / "config" / "shared" / "config",
            root / "bl-churn" / "config" / "shared" / "config",
        )

    @staticmethod
    def _config_file(filename: str) -> Path:
        """Liefert die erste existierende Konfigurationsdatei in der bevorzugten Reihenfolge.
        Fallback: erster Kandidat (auch wenn nicht vorhanden), damit Aufrufer einen konsistenten Pfad erhalten.
        """
        root = ProjectPaths.project_root()
        candidates = [
            root / "json-database" / "config" / "shared" / "config" / filename,
            root / "bl-churn" / "config" / "shared" / "config" / filename,
            root / "bl-cox" / "config" / "shared" / "config" / filename,
            root / "bl-counterfactuals" / "config" / "shared" / "config" / filename,
        ]
        for p in candidates:
            if p.exists():
                return p
        return candidates[0]

    @staticmethod
    def json_database_directory() -> Path:
        return ProjectPaths.project_root() / "json-database"

    @staticmethod
    def bl_churn_directory() -> Path:
        return ProjectPaths.project_root() / "bl-churn"

    @staticmethod
    def bl_cox_directory() -> Path:
        return ProjectPaths.project_root() / "bl-cox"

    @staticmethod
    def feature_mapping_file() -> Path:
        return ProjectPaths._config_file("feature_mapping.json")

    @staticmethod
    def get_data_dictionary_file() -> Path:
        return ProjectPaths._config_file("data_dictionary_optimized.json")

    @staticmethod
    def cf_cost_policy_file() -> Path:
        return ProjectPaths._config_file("cf_cost_policy.json")

    @staticmethod
    def ui_settings_file() -> Path:
        return ProjectPaths._config_file("ui_settings.json")

    # -------------------------
    # Daten / Artefakte
    # -------------------------
    @staticmethod
    def input_data_directory() -> Path:
        return ProjectPaths.project_root() / "bl-input" / "input_data"

    @staticmethod
    def main_churn_data_file() -> Path:
        # Bewährter Default-Name im Repo
        return ProjectPaths.input_data_directory() / "churn_Data_cleaned.csv"

    @staticmethod
    def get_input_data_path() -> Path:
        # Alias für ältere Aufrufer
        return ProjectPaths.main_churn_data_file()

    @staticmethod
    def models_directory() -> Path:
        return ProjectPaths.project_root() / "bl-churn" / "models"

    @staticmethod
    def get_models_directory() -> Path:
        # Alias für ältere Aufrufer
        return ProjectPaths.models_directory()

    @staticmethod
    def artifacts_directory() -> Path:
        return ProjectPaths.project_root() / "artifacts"

    @staticmethod
    def artifacts_for_experiment(experiment_id: int | str) -> Path:
        return ProjectPaths.artifacts_directory() / f"experiment_{int(experiment_id)}"

    # -------------------------
    # Dynamic System Outputs / Outbox
    # -------------------------
    @staticmethod
    def dynamic_system_outputs_directory() -> Path:
        # Aktueller Ort im Repo-Baum
        return ProjectPaths.project_root() / "bl-churn" / "dynamic_system_outputs"

    @staticmethod
    def dynamic_outputs_directory() -> Path:
        # Alias für ältere Aufrufer
        return ProjectPaths.dynamic_system_outputs_directory()

    @staticmethod
    def outbox_directory() -> Path:
        # ENV-Override (z. B. vom Management Studio gesetzt)
        env_outbox = os.environ.get("OUTBOX_ROOT")
        if env_outbox:
            return Path(env_outbox)
        return ProjectPaths.dynamic_system_outputs_directory() / "outbox"

    @staticmethod
    def outbox_churn_experiment_directory(experiment_id: int | str) -> Path:
        return ProjectPaths.outbox_directory() / "churn" / f"experiment_{int(experiment_id)}"

    @staticmethod
    def outbox_cox_experiment_directory(experiment_id: int | str) -> Path:
        return ProjectPaths.outbox_directory() / "cox" / f"experiment_{int(experiment_id)}"

    @staticmethod
    def outbox_counterfactuals_directory() -> Path:
        return ProjectPaths.outbox_directory() / "counterfactuals"

    # -------------------------
    # Utilities
    # -------------------------
    @staticmethod
    def ensure_directory_exists(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path


