#!/usr/bin/env python3
"""
Runner Service - Dünne Orchestrierungsschicht für BL-Module
FastAPI Service für Pipeline-Ausführung und Log-Streaming
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Zentrale Pfad-Konfiguration
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.paths_config import ProjectPaths

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JSON-DB Integration
sys.path.insert(0, str(ProjectPaths.json_database_directory()))
try:
    from bl.json_database.churn_json_database import ChurnJSONDatabase
    json_db = ChurnJSONDatabase()
    logger.info("JSON-DB successfully initialized")
except ImportError as e:
    logger.warning(f"JSON-DB Import failed: {e}")
    json_db = None

app = FastAPI(title="Churn Suite Runner Service", version="1.0.0")

# CORS-Middleware hinzufügen für UI-Integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-Memory Log Store für Live-Streaming
log_store: List[Dict] = []
active_processes: Dict[str, subprocess.Popen] = {}
executor = ThreadPoolExecutor(max_workers=3)


# === PYDANTIC MODELS ===

class ChurnRunRequest(BaseModel):
    experiment_id: int
    training_from: str
    training_to: str
    test_from: str
    test_to: str
    test_reduction: Optional[float] = 0.0


class CoxRunRequest(BaseModel):
    experiment_id: int
    cutoff_exclusive: str


class CounterfactualsRunRequest(BaseModel):
    experiment_id: int
    sample: Optional[int] = None
    limit: Optional[int] = None


class RunResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ExperimentCreate(BaseModel):
    experiment_name: str
    model_type: str
    feature_set: str
    training_from: str
    training_to: str
    backtest_from: str
    backtest_to: str
    id_files: Optional[List[int]] = [1]


class ExperimentUpdate(BaseModel):
    experiment_name: Optional[str] = None
    model_type: Optional[str] = None
    feature_set: Optional[str] = None
    training_from: Optional[str] = None
    training_to: Optional[str] = None
    backtest_from: Optional[str] = None
    backtest_to: Optional[str] = None
    id_files: Optional[List[int]] = None


class ExperimentResponse(BaseModel):
    experiment_id: int
    experiment_name: str
    model_type: str
    feature_set: str
    training_from: str
    training_to: str
    backtest_from: str
    backtest_to: str
    id_files: List[int]
    status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# === UTILITY FUNCTIONS ===

def add_log(level: str, message: str, job_id: Optional[str] = None):
    """Log-Eintrag für Live-Stream hinzufügen"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
        "job_id": job_id
    }
    log_store.append(log_entry)
    logger.info(f"[{job_id}] {message}")
    
    # Log-Store begrenzen (letzten 1000 Einträge)
    if len(log_store) > 1000:
        log_store[:] = log_store[-1000:]


def generate_job_id(pipeline: str, experiment_id: int) -> str:
    """Eindeutige Job-ID generieren"""
    timestamp = int(time.time())
    return f"{pipeline}_{experiment_id}_{timestamp}"


def run_subprocess(cmd: List[str], job_id: str, cwd: Path) -> int:
    """Subprocess ausführen und Logs streamen"""
    add_log("INFO", f"Starting command: {' '.join(cmd)}", job_id)
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        active_processes[job_id] = process
        
        # Live-Output streamen
        for line in iter(process.stdout.readline, ''):
            if line:
                add_log("OUTPUT", line.strip(), job_id)
        
        process.wait()
        return_code = process.returncode
        
        if return_code == 0:
            add_log("SUCCESS", f"Process completed successfully", job_id)
        else:
            add_log("ERROR", f"Process failed with return code {return_code}", job_id)
            
        return return_code
        
    except Exception as e:
        add_log("ERROR", f"Subprocess execution failed: {str(e)}", job_id)
        return 1
    finally:
        active_processes.pop(job_id, None)


# === API ENDPOINTS ===

@app.get("/")
async def root():
    return {"service": "Churn Suite Runner", "status": "running"}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "active_jobs": len(active_processes),
        "log_entries": len(log_store)
    }


@app.post("/run/churn", response_model=RunResponse)
async def run_churn(request: ChurnRunRequest, background_tasks: BackgroundTasks):
    """Churn-Pipeline ausführen"""
    job_id = generate_job_id("churn", request.experiment_id)
    
    # Subprocess-Command zusammenstellen - verwende process_experiment() direkt
    cmd = [
        sys.executable,
        "-c",
        f"""
import sys
sys.path.insert(0, '{ProjectPaths.bl_churn_directory()}')
sys.path.insert(0, '{ProjectPaths.json_database_directory()}')
from bl.Churn.churn_auto_processor import ChurnAutoProcessor
from bl.json_database.churn_json_database import ChurnJSONDatabase

# Lade Experiment aus Datenbank
db = ChurnJSONDatabase()
exp_id = {request.experiment_id}
experiment = db.get_experiment_by_id(exp_id)
if not experiment:
    print("ERROR: Experiment " + str(exp_id) + " not found")
    sys.exit(1)

# Verarbeite Experiment
processor = ChurnAutoProcessor()
test_reduction = {request.test_reduction if hasattr(request, 'test_reduction') and request.test_reduction is not None else 0.0}
success = processor.process_experiment(experiment, custom_periods=None, test_reduction=float(test_reduction))
if not success:
    print("ERROR: Processing failed for experiment " + str(exp_id))
    sys.exit(1)
    
print("SUCCESS: Experiment " + str(exp_id) + " processed successfully")
"""
    ]
    
    # Background-Task starten
    background_tasks.add_task(
        lambda: executor.submit(run_subprocess, cmd, job_id, ProjectPaths.project_root())
    )
    
    return RunResponse(
        job_id=job_id,
        status="started",
        message=f"Churn pipeline started for experiment {request.experiment_id}"
    )


@app.post("/run/cox", response_model=RunResponse)
async def run_cox(request: CoxRunRequest, background_tasks: BackgroundTasks):
    """Cox-Pipeline ausführen"""
    job_id = generate_job_id("cox", request.experiment_id)
    
    cmd = [
        sys.executable,
        "-c",
        f"""
import sys
sys.path.insert(0, '{ProjectPaths.bl_cox_directory()}')
sys.path.insert(0, '{ProjectPaths.json_database_directory()}')
from bl.Cox.cox_auto_processor import main
main(experiment_id={request.experiment_id}, cutoff_exclusive='{request.cutoff_exclusive}')
"""
    ]
    
    background_tasks.add_task(
        lambda: executor.submit(run_subprocess, cmd, job_id, ProjectPaths.project_root())
    )
    
    return RunResponse(
        job_id=job_id,
        status="started",
        message=f"Cox pipeline started for experiment {request.experiment_id}"
    )


@app.post("/run/cf", response_model=RunResponse)
async def run_counterfactuals(request: CounterfactualsRunRequest, background_tasks: BackgroundTasks):
    """Counterfactuals-Pipeline ausführen"""
    job_id = generate_job_id("cf", request.experiment_id)
    
    cmd = [
        sys.executable,
        "-c",
        f"""
import sys
sys.path.insert(0, '{ProjectPaths.bl_counterfactuals_directory()}')
sys.path.insert(0, '{ProjectPaths.json_database_directory()}')
from bl.Counterfactuals.counterfactuals_cli import main
main(experiment_id={request.experiment_id}, sample={request.sample}, limit={request.limit})
"""
    ]
    
    background_tasks.add_task(
        lambda: executor.submit(run_subprocess, cmd, job_id, ProjectPaths.project_root())
    )
    
    return RunResponse(
        job_id=job_id,
        status="started",
        message=f"Counterfactuals pipeline started for experiment {request.experiment_id}"
    )


@app.get("/logs/stream")
async def get_logs(since: Optional[str] = None, job_id: Optional[str] = None):
    """Live-Logs abrufen (Polling-basiert)"""
    filtered_logs = log_store
    
    # Filter nach Zeitstempel
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            filtered_logs = [
                log for log in filtered_logs 
                if datetime.fromisoformat(log["timestamp"]) > since_dt
            ]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format")
    
    # Filter nach Job-ID
    if job_id:
        filtered_logs = [log for log in filtered_logs if log.get("job_id") == job_id]
    
    return {
        "logs": filtered_logs,
        "total_count": len(log_store),
        "filtered_count": len(filtered_logs)
    }


@app.get("/jobs")
async def get_active_jobs():
    """Aktive Jobs anzeigen"""
    return {
        "active_jobs": list(active_processes.keys()),
        "count": len(active_processes)
    }


@app.delete("/jobs/{job_id}")
async def kill_job(job_id: str):
    """Job beenden"""
    if job_id not in active_processes:
        raise HTTPException(status_code=404, detail="Job not found")
    
    process = active_processes[job_id]
    try:
        process.terminate()
        add_log("WARNING", f"Job terminated by user", job_id)
        return {"message": f"Job {job_id} terminated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to terminate job: {str(e)}")


# === EXPERIMENT CRUD ENDPOINTS ===

@app.get("/experiments")
async def get_experiment_by_ids():
    """Alle Experimente aus JSON-DB abrufen"""
    if not json_db:
        # Fallback: Mock-Daten für Demo
        mock_experiments = [
            {
                "experiment_id": 1,
                "experiment_name": "Demo Experiment 1",
                "model_type": "cox_survival",
                "feature_set": "standard",
                "training_from": "202301",
                "training_to": "202312",
                "backtest_from": "202401",
                "backtest_to": "202406",
                "id_files": [1],
                "status": "created",
                "created_at": "2025-09-22T09:00:00",
                "updated_at": "2025-09-22T09:00:00"
            }
        ]
        return {"records": mock_experiments, "count": len(mock_experiments)}
    
    try:
        # Direkt auf die experiments Tabelle zugreifen
        try:
            json_db.maybe_reload()
        except Exception:
            pass
        experiments = json_db.data.get("tables", {}).get("experiments", {}).get("records", [])
        return {"records": experiments, "count": len(experiments)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch experiments: {str(e)}")


@app.get("/experiments/{experiment_id}")
async def get_experiment_by_id(experiment_id: int):
    """Einzelnes Experiment abrufen"""
    if not json_db:
        if experiment_id == 1:
            return {
                "experiment_id": 1,
                "experiment_name": "Demo Experiment 1",
                "model_type": "cox_survival",
                "feature_set": "standard",
                "training_from": "202301",
                "training_to": "202312",
                "backtest_from": "202401",
                "backtest_to": "202406",
                "id_files": [1],
                "status": "created",
                "created_at": "2025-09-22T09:00:00",
                "updated_at": "2025-09-22T09:00:00"
            }
        else:
            raise HTTPException(status_code=404, detail="Experiment not found")
    
    try:
        try:
            json_db.maybe_reload()
        except Exception:
            pass
        experiment = json_db.get_experiment_by_id(experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")
        return experiment
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch experiment: {str(e)}")


@app.post("/experiments", response_model=ExperimentResponse)
async def create_experiment(experiment: ExperimentCreate):
    """Neues Experiment anlegen"""
    if not json_db:
        # Mock-Implementierung für Demo
        experiment_data = {
            "experiment_id": 999,  # Mock-ID
            "experiment_name": experiment.experiment_name,
            "model_type": experiment.model_type,
            "feature_set": experiment.feature_set,
            "training_from": experiment.training_from,
            "training_to": experiment.training_to,
            "backtest_from": experiment.backtest_from,
            "backtest_to": experiment.backtest_to,
            "id_files": experiment.id_files,
            "status": "created",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        add_log("INFO", f"Mock: Experiment created: {experiment.experiment_name} (ID: 999)", None)
        return experiment_data
    
    try:
        # Duplikate-Check (alle Felder außer Name)
        existing_experiments = json_db.data.get("tables", {}).get("experiments", {}).get("records", [])
        for existing in existing_experiments:
            if (existing.get("model_type") == experiment.model_type and
                existing.get("feature_set") == experiment.feature_set and
                existing.get("training_from") == experiment.training_from and
                existing.get("training_to") == experiment.training_to and
                existing.get("backtest_from") == experiment.backtest_from and
                existing.get("backtest_to") == experiment.backtest_to and
                existing.get("id_files") == experiment.id_files):
                raise HTTPException(status_code=400, detail="Experiment mit identischen Parametern bereits vorhanden")
        
        experiment_data = {
            "experiment_name": experiment.experiment_name,
            "model_type": experiment.model_type,
            "feature_set": experiment.feature_set,
            "training_from": experiment.training_from,
            "training_to": experiment.training_to,
            "backtest_from": experiment.backtest_from,
            "backtest_to": experiment.backtest_to,
            "id_files": experiment.id_files,
            "status": "created",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        experiment_id = json_db.create_experiment(
            experiment_name=experiment.experiment_name,
            training_from=experiment.training_from,
            training_to=experiment.training_to,
            backtest_from=experiment.backtest_from,
            backtest_to=experiment.backtest_to,
            model_type=experiment.model_type,
            feature_set=experiment.feature_set,
            file_ids=experiment.id_files
        )
        json_db.save()  # Wichtig: Änderungen persistent speichern!
        experiment_data["experiment_id"] = experiment_id
        
        add_log("INFO", f"Experiment created: {experiment.experiment_name} (ID: {experiment_id})", None)
        return experiment_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create experiment: {str(e)}")


@app.put("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(experiment_id: int, experiment: ExperimentUpdate):
    """Experiment aktualisieren"""
    if not json_db:
        raise HTTPException(status_code=500, detail="JSON-DB not available")
    
    try:
        # Prüfen ob Experiment existiert
        existing = json_db.get_experiment_by_id(experiment_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        # Update-Daten zusammenstellen
        update_data = {}
        if experiment.experiment_name is not None:
            update_data["experiment_name"] = experiment.experiment_name
        if experiment.model_type is not None:
            update_data["model_type"] = experiment.model_type
        if experiment.feature_set is not None:
            update_data["feature_set"] = experiment.feature_set
        if experiment.training_from is not None:
            update_data["training_from"] = experiment.training_from
        if experiment.training_to is not None:
            update_data["training_to"] = experiment.training_to
        if experiment.backtest_from is not None:
            update_data["backtest_from"] = experiment.backtest_from
        if experiment.backtest_to is not None:
            update_data["backtest_to"] = experiment.backtest_to
        if experiment.id_files is not None:
            update_data["id_files"] = experiment.id_files
        
        update_data["updated_at"] = datetime.now().isoformat()
        
        json_db.update_experiment(experiment_id, update_data)
        
        # Aktualisiertes Experiment zurückgeben
        updated_experiment = json_db.get_experiment_by_id_by_id(experiment_id)
        add_log("INFO", f"Experiment updated: {updated_experiment.get('experiment_name')} (ID: {experiment_id})", None)
        return updated_experiment
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update experiment: {str(e)}")


@app.delete("/experiments/{experiment_id}")
async def delete_experiment(experiment_id: int, cascade: bool = False):
    """Experiment löschen (mit Cascade-Option)"""
    if not json_db:
        raise HTTPException(status_code=500, detail="JSON-DB not available")
    
    try:
        # Prüfen ob Experiment existiert
        existing = json_db.get_experiment_by_id(experiment_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        if not cascade:
            raise HTTPException(status_code=400, detail="Cascade deletion required")
        
        json_db.delete_experiment(experiment_id, cascade=True)
        json_db.save()  # Änderungen persistent speichern!
        add_log("INFO", f"Experiment deleted: {existing.get('experiment_name')} (ID: {experiment_id})", None)
        return {"message": f"Experiment {experiment_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete experiment: {str(e)}")


class ExperimentRunRequest(BaseModel):
    pipeline: str
    cutoff_exclusive: Optional[str] = None
    test: Optional[bool] = False


@app.post("/experiments/{experiment_id}/run")
async def run_experiment_pipeline(experiment_id: int, request: ExperimentRunRequest, background_tasks: BackgroundTasks):
    """Pipeline für spezifisches Experiment ausführen"""
    if not json_db:
        raise HTTPException(status_code=500, detail="JSON-DB not available")
    
    try:
        # Experiment laden
        experiment = json_db.get_experiment_by_id(experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        # Pipeline-spezifische Logik
        if request.pipeline == "churn":
            # Churn-Pipeline mit Experiment-Daten
            def format_date(date_str, default):
                if not date_str:
                    return default
                if len(str(date_str)) == 6:  # YYYYMM format
                    return f"{str(date_str)[:4]}-{str(date_str)[4:]}"
                return str(date_str)
            
            churn_request = ChurnRunRequest(
                experiment_id=experiment_id,
                training_from=format_date(experiment.get("training_from"), "2020-01"),
                training_to=format_date(experiment.get("training_to"), "2023-12"),
                test_from=format_date(experiment.get("backtest_from"), "2024-01"),
                test_to=format_date(experiment.get("backtest_to"), "2024-06"),
                test_reduction=(0.9 if (getattr(request, 'test', False) or False) else 0.0)
            )
            return await run_churn(churn_request, background_tasks)
            
        elif request.pipeline == "cox":
            # Cox-Pipeline mit Experiment-Daten
            cox_request = CoxRunRequest(
                experiment_id=experiment_id,
                cutoff_exclusive=request.cutoff_exclusive or experiment.get("backtest_from", "202401")
            )
            return await run_cox(cox_request, background_tasks)
            
        elif request.pipeline == "cf":
            # Counterfactuals-Pipeline mit Experiment-Daten
            cf_request = CounterfactualsRunRequest(
                experiment_id=experiment_id,
                sample=None,
                limit=None
            )
            return await run_counterfactuals(cf_request, background_tasks)
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown pipeline: {request.pipeline}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run experiment pipeline: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    # Environment Setup
    ProjectPaths.ensure_directory_exists(ProjectPaths.outbox_directory())
    ProjectPaths.ensure_directory_exists(ProjectPaths.dynamic_system_outputs_directory())
    
    add_log("INFO", "Runner Service starting up", None)
    
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=5050,
        reload=True,
        log_level="info"
    )
