#!/usr/bin/env python3
"""
Read-only Flask SQL-Interface (Management Studio) für JSON-Datenbank.

Endpunkte:
- GET  /sql                 → UI (Editor + Tabellenliste + Ergebnis-Grid)
- GET  /sql/tables          → Tabellennamen, Record-Anzahl, Beschreibung
- GET  /sql/schema/<table>  → Schema (display_type, description) + Quelle
- POST /sql/query           → Query-Ausführung (Whitelist: SELECT/EXPLAIN/PRAGMA)

Regeln:
- Pfade via paths_config
- Read-only: Nur SELECT/EXPLAIN/PRAGMA
- Statement-Whitelist, Timeout, Zeilenlimit
- Lineage: id_files sichtbar halten (falls möglich aus experiments ableitbar)
"""

from __future__ import annotations

import sys
import os

# Sicherstellen, dass der Projekt-Root im Python-Pfad liegt (für Modul-Imports)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from config.paths_config import ProjectPaths

import os
import json
import re
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from flask import Flask, jsonify, render_template, request, redirect, url_for, send_from_directory

# Business-Logic Imports
from bl.json_database.sql_query_interface import SQLQueryInterface
from bl.json_database.churn_json_database import ChurnJSONDatabase

# Optional: ENV Overrides für OUTBOX_ROOT und DB-Pfad
# MGMT_OUTBOX_ROOT → setzt OUTBOX_ROOT für alle Pfadauflösungen
# MGMT_CHURN_DB_PATH (oder CHURN_DB_PATH) → expliziter Pfad zur churn_database.json
_MGMT_OUTBOX = os.environ.get("MGMT_OUTBOX_ROOT")
if _MGMT_OUTBOX:
    os.environ["OUTBOX_ROOT"] = _MGMT_OUTBOX

def _open_db() -> ChurnJSONDatabase:
    """Öffnet die JSON-DB strikt über ProjectPaths (keine ENV-Overrides)."""
    db_path = ProjectPaths.dynamic_system_outputs_directory() / "churn_database.json"
    try:
        return ChurnJSONDatabase(str(db_path))
    except TypeError:
        # Fallback für ältere Signaturen
        return ChurnJSONDatabase(str(db_path))

# Zusätzliche Loader für mehrere Template-Verzeichnisse (ManagementStudio + CRUD)
from jinja2 import ChoiceLoader, FileSystemLoader
import threading
import logging
from collections import deque
from time import time
from math import isfinite
from datetime import datetime


from pathlib import Path as _Path

# Bevorzugt: Template/Static relativ zu dieser Datei (robust gegen abweichende Roots)
_BASE_DIR = _Path(__file__).resolve().parent
template_dir_fs = str(_BASE_DIR / "templates")
static_dir_fs = str(_BASE_DIR / "static")

# Zusätzlich (Fallback/Kompatibilität): ProjectPaths-basierte Verzeichnisse
template_dir_pp = str(ProjectPaths.project_root() / "ui-managementstudio" / "templates")
static_dir_pp = str(ProjectPaths.project_root() / "ui-managementstudio" / "static")
crud_templates_dir = str(ProjectPaths.project_root() / "ui-crud")
crud_static_dir = str(ProjectPaths.project_root() / "ui-crud" / "static")

# Flask App auf FileSystem-Pfade setzen (damit /sql die korrekten Dateien lädt)
app = Flask(__name__, template_folder=template_dir_fs, static_folder=static_dir_fs)

# Jinja Loader: zuerst FileSystem, dann ProjectPaths, dann CRUD
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(template_dir_fs),
    FileSystemLoader(template_dir_pp),
    FileSystemLoader(crud_templates_dir)
])

# Einfacher Passwortschutz für Schreib-Operationen
ADMIN_PASSWORD = "data knows it all"

def _check_password() -> bool:
    # Passwort aus Header oder JSON-Body
    header_pw = request.headers.get("X-Admin-Password", "")
    if header_pw:
        return header_pw == ADMIN_PASSWORD
    try:
        payload = request.get_json(silent=True) or {}
        body_pw = payload.get("password", "")
        return body_pw == ADMIN_PASSWORD
    except Exception:
        return False


# -----------------------------
# Helpers
# -----------------------------

ALLOWED_PREFIXES = ("SELECT", "EXPLAIN", "PRAGMA", "WITH")
FORBIDDEN_KEYWORDS = (
    "UPDATE", "DELETE", "INSERT", "CREATE", "DROP", "ALTER", "ATTACH", "DETACH",
    "COPY", "EXPORT", "IMPORT", "REPLACE", "VACUUM", "TRUNCATE", "GRANT", "REVOKE"
)

DEFAULT_ROW_LIMIT = 10000
QUERY_TIMEOUT_SECONDS = 600  # 10 Minuten Timeout


def _is_read_only_sql(sql: str) -> bool:
    if not sql:
        return False
    normalized = re.sub(r"\s+", " ", sql).strip()
    upper = normalized.upper()
    # Single-statement simple check: disallow multiple semicolons
    if upper.count(";") > 1:
        return False
    # Must start with allowed prefixes
    if not upper.startswith(ALLOWED_PREFIXES):
        return False
    # No forbidden keywords anywhere
    for kw in FORBIDDEN_KEYWORDS:
        if kw in upper:
            return False
    return True


def _ensure_limit(sql: str, max_limit: int = DEFAULT_ROW_LIMIT) -> str:
    # PRAGMA-Statements unterstützen kein angehängtes LIMIT → unverändert lassen
    norm = sql.lstrip()
    if norm.upper().startswith("PRAGMA"):
        return sql
    # If query already contains LIMIT, do nothing
    if re.search(r"\bLIMIT\b\s+\d+", sql, flags=re.IGNORECASE):
        return sql
    # Append LIMIT at end (safe for SELECT/EXPLAIN/WITH-CTE)
    return f"{sql.rstrip().rstrip(';')} LIMIT {max_limit}"


def _inject_saved_views(sql: str, db: ChurnJSONDatabase) -> str:
    """Fügt gespeicherte Views als WITH-CTEs vor der User-Query ein.
    Falls die User-Query bereits mit WITH beginnt, werden die CTEs zusammengeführt.
    """
    try:
        views = db.list_views()
    except Exception:
        views = []
    if not views:
        return sql
    ctes: List[str] = []
    for v in views:
        name = (v.get("name") or "").strip()
        query = (v.get("query") or "").strip().rstrip(";")
        if not name or not query:
            continue
        ctes.append(f"{name} AS ({query})")
    if not ctes:
        return sql
    prefix = "WITH " + ", ".join(ctes)
    norm = sql.lstrip()
    if norm.upper().startswith("WITH "):
        body = norm[4:].lstrip()
        return f"{prefix}, {body}"
    return f"{prefix} {sql}"


@app.route("/sql/debug", methods=["GET"])
def debug_info():
    """Diagnose: zeigt effektive Template-/Static-Pfade und Template-Inhalt-Hash an."""
    import hashlib
    from pathlib import Path as _Path
    info: Dict[str, Any] = {
        "template_dir_fs": template_dir_fs,
        "static_dir_fs": static_dir_fs,
        "template_dir_pp": template_dir_pp,
        "static_dir_pp": static_dir_pp,
        "crud_templates_dir": crud_templates_dir,
        "project_root": str(ProjectPaths.project_root()),
    }
    # sql.html Vollpfad + mtime + Hash + Marker-Prüfung
    tpl_path = _Path(template_dir_fs) / "sql.html"
    info["sql_template_path"] = str(tpl_path)
    try:
        st = tpl_path.stat()
        info["sql_template_mtime"] = st.st_mtime
        data = tpl_path.read_bytes()
        info["sql_template_sha1"] = hashlib.sha1(data).hexdigest()
        txt = data.decode("utf-8", errors="ignore")
        info["has_views_panel"] = ("id=\"viewsList\"" in txt)
        info["has_plus_view_button"] = ("id=\"saveView\"" in txt)
        info["has_cache_bust_v2"] = ("?v=2" in txt)
        info["banner_with"] = ("SELECT/EXPLAIN/PRAGMA/WITH" in txt)
    except Exception as e:
        info["sql_template_error"] = str(e)
    return jsonify(info)


def _attach_lineage(rows: List[Dict[str, Any]], db: ChurnJSONDatabase) -> List[Dict[str, Any]]:
    if not rows:
        return rows
    # If id_files already present, nothing to do
    if any("id_files" in r for r in rows):
        return rows
    # Heuristik: Für backtest_results KEIN id_files-Inline-Lineage einblenden
    # Erkennung über typische Spalten
    sample = rows[0] if rows else {}
    if isinstance(sample, dict) and ("churn_probability" in sample or "risk_level" in sample):
        return rows
    # If experiment id available, enrich with experiments.id_files
    exp_table = db.data.get("tables", {}).get("experiments", {})
    exp_records: List[Dict[str, Any]] = exp_table.get("records", []) or []
    if not exp_records:
        return rows
    # Build lookup
    id_map: Dict[int, List[int]] = {}
    for exp in exp_records:
        try:
            key = int(exp.get("experiment_id"))
            id_map[key] = exp.get("id_files", []) or []
        except Exception:
            continue
    # Decide key name in result
    key_in_row = None
    if any("id_experiments" in r for r in rows):
        key_in_row = "id_experiments"
    elif any("experiment_id" in r for r in rows):
        key_in_row = "experiment_id"
    if not key_in_row:
        return rows
    # Enrich
    enriched: List[Dict[str, Any]] = []
    for r in rows:
        new_r = dict(r)
        try:
            exp_id = int(new_r.get(key_in_row)) if new_r.get(key_in_row) is not None else None
        except Exception:
            exp_id = None
        if exp_id is not None and "id_files" not in new_r:
            new_r["id_files"] = id_map.get(exp_id, [])
        enriched.append(new_r)
    return enriched


def _sanitize_jsonable(obj: Any) -> Any:
    """Konvertiert numpy/pandas-ähnliche Typen in JSON-serialisierbare Werte (rekursiv)."""
    try:
        # numpy optional behandeln, ohne harte Abhängigkeit
        import numpy as _np  # type: ignore
    except Exception:
        _np = None  # type: ignore

    if isinstance(obj, dict):
        return {k: _sanitize_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_jsonable(v) for v in obj]
    if isinstance(obj, tuple):
        return [_sanitize_jsonable(v) for v in obj]
    # numpy Arrays / Scalars
    if _np is not None:
        try:
            if isinstance(obj, _np.ndarray):
                return obj.tolist()
            if isinstance(obj, _np.generic):
                return obj.item()
        except Exception:
            pass
    # tolist()-fähige Objekte (z.B. pandas Series)
    if hasattr(obj, "tolist"):
        try:
            return obj.tolist()
        except Exception:
            pass
    # Standard-Python Zahlen: NaN/Inf → null
    try:
        import math as _math
        if isinstance(obj, float):
            if _math.isnan(obj) or _math.isinf(obj):
                return None
            return obj
        if isinstance(obj, (int, bool)):
            return obj
    except Exception:
        pass
    # Strings & andere einfache Typen direkt zurückgeben
    if isinstance(obj, str):
        return obj
    # Fallback: stringifizieren
    try:
        return str(obj)
    except Exception:
        return None


# -----------------------------
# Routes
# -----------------------------


@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("sql_home"), code=302)


@app.route("/sql", methods=["GET"])
@app.route("/sql/", methods=["GET"])
def sql_home():
    return render_template("sql.html")


# -----------------------------
# CRUD UI Routes (Experiments)
# -----------------------------

@app.route("/crud", methods=["GET"])
def crud_home():
    # Rendert ui-crud/experiments.html
    return render_template("experiments.html")

@app.route("/crud/experiments", methods=["GET"])
def crud_experiments():
    return render_template("experiments.html")

@app.route("/crud/debug", methods=["GET"])
def crud_debug():
    return render_template("debug.html")

# Pipeline Runner UI (Index) unter CRUD bereitstellen
@app.route("/crud/index.html", methods=["GET"])
def crud_index():
    return render_template("index.html")

# Alias für alte Links
@app.route("/crud/experiments-new.html", methods=["GET"])
def crud_experiments_new_alias():
    return render_template("experiments.html")

# Zusätzliche Aliasse/Weiterleitungen für robuste Navigation
@app.route("/crud", methods=["GET"])
def crud_root_redirect():
    return redirect(url_for("crud_index"))

@app.route("/crud/experiments.html", methods=["GET"])
def crud_experiments_html():
    return render_template("experiments.html")


@app.route("/crud/static/<path:filename>")
def crud_static(filename: str):
    # Statische Assets aus ui-crud/static
    return send_from_directory(crud_static_dir, filename)


@app.route("/sql/tables", methods=["GET"])
def list_tables():
    db = _open_db()
    try:
        db.maybe_reload()
    except Exception:
        pass
    tables = db.data.get("tables", {})
    # Alle Tabellen anzeigen (keine Ausblendung)
    out: List[Dict[str, Any]] = []
    for name, meta in tables.items():
        # Keine Filterung – jede Tabelle anzeigen
        out.append({
            "table": name,
            "records": len(meta.get("records", []) or []),
            "description": meta.get("description", ""),
        })
    return jsonify({"tables": out})


@app.route("/sql/db-info", methods=["GET"])
def db_info():
    """Diagnose-Endpunkt: zeigt verwendeten DB-Pfad und SHAP-Tabellenstatus."""
    info: Dict[str, Any] = {}
    try:
        info["MGMT_CHURN_DB_PATH"] = os.environ.get("MGMT_CHURN_DB_PATH")
        info["CHURN_DB_PATH"] = os.environ.get("CHURN_DB_PATH")
        info["MGMT_OUTBOX_ROOT"] = os.environ.get("MGMT_OUTBOX_ROOT")
        info["OUTBOX_ROOT"] = os.environ.get("OUTBOX_ROOT")
        default_db = ProjectPaths.dynamic_system_outputs_directory() / "churn_database.json"
        info["default_db_path"] = str(default_db)
        try:
            st = default_db.stat()
            info["default_db_exists"] = True
            info["default_db_size"] = st.st_size
            info["default_db_mtime"] = st.st_mtime
        except Exception:
            info["default_db_exists"] = False
        db = _open_db()
        tables = db.data.get("tables", {})
        shap_tables = {k: len((v.get("records", []) or [])) for k, v in tables.items() if "shap" in k}
        info["shap_tables"] = shap_tables
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e), **info}), 500


# -----------------------------
# Live Log Streaming (Polling)
# -----------------------------

_log_buffer_lock = threading.Lock()
_log_buffer = deque(maxlen=2000)  # letzte 2000 Einträge
_log_seq = 0


class _MemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        global _log_seq
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        entry = {
            "id": None,
            "ts": record.created,
            "level": record.levelname,
            "logger": record.name,
            "message": msg,
        }
        with _log_buffer_lock:
            _log_seq += 1
            entry["id"] = _log_seq
            _log_buffer.append(entry)


_memory_handler = _MemoryLogHandler(level=logging.INFO)
_memory_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))

# Root-Logger ergänzen (nicht ersetzen)
try:
    root_logger = logging.getLogger()
    root_logger.addHandler(_memory_handler)
except Exception:
    pass


@app.route("/logs/live", methods=["GET"])
def logs_live():
    try:
        since = int(request.args.get("since", "0"))
    except Exception:
        since = 0
    with _log_buffer_lock:
        lines = [e for e in list(_log_buffer) if (e.get("id", 0) > since)]
        next_since = _log_seq
    return jsonify({
        "lines": lines,
        "next_since": next_since,
        "count": len(lines)
    })


def _append_log(level: str, logger_name: str, message: str) -> None:
    global _log_seq
    if not message:
        return
    entry = {
        "id": None,
        "ts": float(__import__('time').time()),
        "level": level,
        "logger": logger_name,
        "message": message.rstrip('\n')
    }
    with _log_buffer_lock:
        _log_seq += 1
        entry["id"] = _log_seq
        _log_buffer.append(entry)


class _StreamToLog:
    def __init__(self, level: str, logger_name: str):
        self.level = level
        self.logger_name = logger_name
        self._buffer = ""

    def write(self, s: str) -> int:
        if not isinstance(s, str):
            try:
                s = str(s)
            except Exception:
                return 0
        self._buffer += s
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            if line.strip():
                _append_log(self.level, self.logger_name, line)
        return len(s)

    def flush(self) -> None:
        if self._buffer.strip():
            _append_log(self.level, self.logger_name, self._buffer)
            self._buffer = ""


# -----------------------------
# Maintenance: Reload Threshold Tables
# -----------------------------

def _evaluate_threshold_metrics(y_true, y_prob, threshold: float) -> Dict[str, float]:
    tp = fp = tn = fn = 0
    for t, p in zip(y_true, y_prob):
        try:
            pred = 1 if float(p) >= float(threshold) else 0
        except Exception:
            pred = 0
        if pred == 1 and t == 1:
            tp += 1
        elif pred == 1 and t == 0:
            fp += 1
        elif pred == 0 and t == 0:
            tn += 1
        else:
            fn += 1
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


@app.route("/maintenance/reload-thresholds", methods=["POST"])
def maintenance_reload_thresholds():
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        db = ChurnJSONDatabase()
        # Seed Methoden
        try:
            db.ensure_threshold_methods_seeded()  # type: ignore[attr-defined]
        except Exception:
            pass

        tables = db.data.get("tables", {})
        backtest_tbl = tables.get("backtest_results", {}).get("records", []) or []

        # Gruppiere nach Experiment (Quelle 1: backtest_results)
        from collections import defaultdict
        exp_to_rows: Dict[int, list] = defaultdict(list)
        for r in backtest_tbl:
            try:
                exp_id = int(r.get("id_experiments") or r.get("experiment_id"))
            except Exception:
                continue
            exp_to_rows[exp_id].append(r)

        # Fallback Quelle 2: customer_details (wenn backtest_results leer)
        if not exp_to_rows:
            cust_tbl = tables.get("customer_details", {}).get("records", []) or []
            for r in cust_tbl:
                try:
                    exp_id = int(r.get("experiment_id") or r.get("id_experiments"))
                except Exception:
                    continue
                # Mappe Felder kompatibel zu backtest_results: churn_probability/actual_churn
                prob = r.get("Churn_Wahrscheinlichkeit")
                alive = r.get("I_ALIVE")
                actual = None
                if isinstance(alive, str):
                    actual = 0 if alive.lower() == 'true' else 1
                row = {
                    "churn_probability": prob,
                    "actual_churn": actual
                }
                exp_to_rows[exp_id].append(row)
            if not exp_to_rows:
                return jsonify({"error": "Keine Daten in backtest_results oder customer_details"}), 400

        # Für jede Gruppe berechnen
        import numpy as _np  # type: ignore
        try:
            from sklearn.metrics import roc_curve
            _HAS_SK = True
        except Exception:
            _HAS_SK = False

        updated_exps = []
        for exp_id, rows in exp_to_rows.items():
            y_true = []
            y_prob = []
            for r in rows:
                try:
                    y_true.append(int(r.get('actual_churn') or r.get('ACTUAL_CHURN') or 0))
                    y_prob.append(float(r.get('churn_probability') or r.get('CHURN_PROBABILITY') or 0.0))
                except Exception:
                    pass
            if not y_true or not y_prob:
                continue

            # Standard 0.5
            m05 = _evaluate_threshold_metrics(y_true, y_prob, 0.5)
            db.add_threshold_metrics(exp_id, 'standard_0_5', 0.5, m05['precision'], m05['recall'], m05['f1'], 'backtest', is_selected=0)  # type: ignore[attr-defined]

            # F1 optimal
            thr_range = _np.arange(0.1, 0.9, 0.01)
            best_f1 = -1.0
            best_thr = 0.5
            for th in thr_range:
                m = _evaluate_threshold_metrics(y_true, y_prob, float(th))
                if m['f1'] > best_f1:
                    best_f1 = m['f1']
                    best_thr = float(th)
                    best_m = m
            db.add_threshold_metrics(exp_id, 'f1_optimal', best_thr, best_m['precision'], best_m['recall'], best_m['f1'], 'backtest', is_selected=1)  # type: ignore[attr-defined]

            # Elbow (falls sklearn verfügbar)
            if _HAS_SK:
                try:
                    fpr, tpr, thr = roc_curve(y_true, y_prob)
                    distances = _np.sqrt((1 - tpr) ** 2 + fpr ** 2)
                    elbow_thr = float(thr[_np.argmin(distances)])
                    melb = _evaluate_threshold_metrics(y_true, y_prob, elbow_thr)
                    db.add_threshold_metrics(exp_id, 'elbow', elbow_thr, melb['precision'], melb['recall'], melb['f1'], 'backtest', is_selected=0)  # type: ignore[attr-defined]
                except Exception:
                    pass

            # Precision optimal (max precision)
            best_p = -1.0
            best_thr_p = 0.5
            for th in thr_range:
                m = _evaluate_threshold_metrics(y_true, y_prob, float(th))
                if m['precision'] > best_p:
                    best_p = m['precision']
                    best_thr_p = float(th)
                    best_mp = m
            db.add_threshold_metrics(exp_id, 'precision_optimal', best_thr_p, best_mp['precision'], best_mp['recall'], best_mp['f1'], 'backtest', is_selected=0)  # type: ignore[attr-defined]

            updated_exps.append(exp_id)

        if updated_exps:
            db.save()
        return jsonify({"updated_experiments": updated_exps, "count": len(updated_exps)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/maintenance/cleanup-artifacts", methods=["POST"])
def maintenance_cleanup_artifacts():
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        from datetime import datetime as _dt
        import os as _os
        import re as _re
        db = ChurnJSONDatabase()
        db.ensure_artifacts_registry()

        models_dir = ProjectPaths.get_models_directory()
        kept = []
        deleted = []
        errors = []

        # Sammle Churn-Modelle (Enhanced_EarlyWarning)
        json_models = sorted(models_dir.glob("Enhanced_EarlyWarning_*.json"))
        joblib_models = sorted(models_dir.glob("Enhanced_EarlyWarning_*.joblib"))
        backtests = sorted(models_dir.glob("Enhanced_EarlyWarning_Backtest_*.json"))

        # Map Timestamp → joblib/json
        def _ts(name: str) -> str:
            m = _re.search(r"_(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})", name)
            return m.group(1) if m else ""

        ts_to_json = { _ts(p.name): p for p in json_models if 'Backtest_' not in p.name }
        ts_to_joblib = { _ts(p.name): p for p in joblib_models }

        # Bestimme jüngste TS (pro Experiment nicht zuverlässig ableitbar ohne teures JSON-Parsing) → global jüngste behalten
        timestamps = sorted([t for t in ts_to_json.keys() if t], reverse=True)
        keep_ts = timestamps[0] if timestamps else None

        # Behalte jüngstes Paar (json+joblib)
        for ts, p in ts_to_json.items():
            paired_joblib = ts_to_joblib.get(ts)
            if ts == keep_ts:
                # Registry: als active markieren
                try:
                    db.add_artifact_record("model", None, str(p), status="active")
                    if paired_joblib:
                        db.add_artifact_record("model", None, str(paired_joblib), status="active")
                except Exception:
                    pass
                kept.append(str(p))
                if paired_joblib:
                    kept.append(str(paired_joblib))
            else:
                # Löschen
                for path in [p, paired_joblib]:
                    if not path:
                        continue
                    try:
                        _os.remove(path)
                        db.update_artifact_status(str(path), "deleted") or db.add_artifact_record("model", None, str(path), status="deleted")
                        deleted.append(str(path))
                    except Exception as e:
                        errors.append({"file": str(path), "error": str(e)})

        # Backtests: nur jüngsten behalten (global)
        bt_timestamps = sorted([_ts(p.name) for p in backtests if _ts(p.name)], reverse=True)
        keep_bt_ts = bt_timestamps[0] if bt_timestamps else None
        for p in backtests:
            ts = _ts(p.name)
            if ts and ts == keep_bt_ts:
                try:
                    db.add_artifact_record("backtest", None, str(p), status="active")
                except Exception:
                    pass
                kept.append(str(p))
            else:
                try:
                    _os.remove(p)
                    db.update_artifact_status(str(p), "deleted") or db.add_artifact_record("backtest", None, str(p), status="deleted")
                    deleted.append(str(p))
                except Exception as e:
                    errors.append({"file": str(p), "error": str(e)})

        db.save()
        return jsonify({
            "kept": kept,
            "deleted": deleted,
            "errors": errors,
            "kept_count": len(kept),
            "deleted_count": len(deleted)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/maintenance/purge-artifacts", methods=["POST"])
def maintenance_purge_artifacts():
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        db = ChurnJSONDatabase()
        db.ensure_artifacts_registry()
        tbl = db.data.get("tables", {}).get("artifacts_registry", {})
        records = tbl.get("records", []) or []
        keep = []
        purged = []
        for r in records:
            status = str(r.get("status", "")).lower()
            if status == "deleted":
                purged.append(r)
            else:
                keep.append(r)
        tbl["records"] = keep
        db.save()
        return jsonify({
            "purged_count": len(purged),
            "remaining_count": len(keep)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# Experiments CRUD API (JSON)
# -----------------------------

@app.route("/experiments", methods=["GET"])
def list_experiments():
    db = _open_db()
    records = db.data.get("tables", {}).get("experiments", {}).get("records", []) or []
    return jsonify({"records": records, "count": len(records)})


@app.route("/experiments", methods=["POST"])
def create_experiment():
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 403
    payload = request.get_json(silent=True) or {}
    required = ["experiment_name", "training_from", "training_to", "backtest_from", "backtest_to"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    # YYYYMM-Validierung
    def _valid_yyyymm(s: str) -> bool:
        return isinstance(s, (str, int)) and len(str(s)) == 6 and str(s).isdigit() and 1 <= int(str(s)[4:6]) <= 12
    for k in ("training_from", "training_to", "backtest_from", "backtest_to"):
        if not _valid_yyyymm(payload.get(k)):
            return jsonify({"error": f"Invalid YYYYMM for field '{k}'"}), 400
    try:
        db = _open_db()
        # Duplikat-Prüfung: gleiche Kombination aus Zeiträumen, Feature-Set, Modelltyp und id_files
        try:
            existing_records = db.data.get("tables", {}).get("experiments", {}).get("records", []) or []
            criteria_model_type = str(payload.get("model_type", "") or "")
            criteria_feature_set = str(payload.get("feature_set", "standard") or "standard")
            criteria_training_from = str(payload.get("training_from"))
            criteria_training_to = str(payload.get("training_to"))
            criteria_backtest_from = str(payload.get("backtest_from"))
            criteria_backtest_to = str(payload.get("backtest_to"))
            criteria_id_files = payload.get("id_files")

            for ex in existing_records:
                try:
                    if (
                        str(ex.get("model_type", "")) == criteria_model_type and
                        str(ex.get("feature_set", "standard")) == criteria_feature_set and
                        str(ex.get("training_from")) == criteria_training_from and
                        str(ex.get("training_to")) == criteria_training_to and
                        str(ex.get("backtest_from")) == criteria_backtest_from and
                        str(ex.get("backtest_to")) == criteria_backtest_to and
                        (ex.get("id_files") or None) == criteria_id_files
                    ):
                        return jsonify({"error": "Experiment mit identischen Parametern bereits vorhanden"}), 400
                except Exception:
                    continue
        except Exception:
            # Bei Fehlern in der Prüfung: weiterfahren, nicht blockieren
            pass
        exp_id = db.create_experiment(
            experiment_name=str(payload.get("experiment_name")),
            training_from=str(payload.get("training_from")),
            training_to=str(payload.get("training_to")),
            backtest_from=str(payload.get("backtest_from")),
            backtest_to=str(payload.get("backtest_to")),
            model_type=str(payload.get("model_type", "")) or "",
            feature_set=str(payload.get("feature_set", "standard")) or "standard",
            hyperparameters=None,  # Immer echten Snapshot aus algorithm_config_optimized.json verwenden
            file_ids=payload.get("id_files")
        )
        db.save()
        return jsonify({"experiment_id": exp_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/experiments/<int:experiment_id>", methods=["PUT"])
def update_experiment(experiment_id: int):
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 403
    payload = request.get_json(silent=True) or {}
    try:
        db = _open_db()
        ok = db.update_experiment(experiment_id, payload)
        if not ok:
            return jsonify({"error": "Experiment not found or no changes"}), 404
        db.save()
        return jsonify({"success": True, "experiment": db.get_experiment_by_id(experiment_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/experiments/<int:experiment_id>", methods=["DELETE"])
def delete_experiment(experiment_id: int):
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 403
    payload = request.get_json(silent=True) or {}
    cascade = bool(payload.get("cascade", False))
    if not cascade:
        return jsonify({"error": "Löschen erfordert cascade=true"}), 400
    try:
        db = ChurnJSONDatabase()
        ok = db.delete_experiment(experiment_id, cascade=True)
        if not ok:
            return jsonify({"error": "Experiment not found"}), 404
        db.save()

        # Optionales Aufräumen der Modelldateien: Behalte nur jeweils die neueste .json und .joblib
        try:
            import glob
            models_dir = ProjectPaths.get_models_directory()
            if models_dir.exists():
                json_files = sorted(models_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                joblib_files = sorted(models_dir.glob("*.joblib"), key=lambda p: p.stat().st_mtime, reverse=True)
                # Lösche alle bis auf die jeweils neueste Datei
                for p in (json_files[1:] if len(json_files) > 1 else []):
                    try: p.unlink()
                    except Exception: pass
                for p in (joblib_files[1:] if len(joblib_files) > 1 else []):
                    try: p.unlink()
                    except Exception: pass
        except Exception:
            pass

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/experiments/<int:experiment_id>/run", methods=["POST"])
def run_experiment(experiment_id: int):
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 403
    payload = request.get_json(silent=True) or {}
    pipeline = (payload.get("pipeline") or request.args.get("pipeline") or "").strip().lower()
    if pipeline not in ("churn", "cox", "cf"):
        return jsonify({"error": "pipeline must be 'churn', 'cox' or 'cf'"}), 400

    db = _open_db()
    exp = db.get_experiment_by_id(experiment_id)
    if not exp:
        return jsonify({"error": "Experiment not found"}), 404

    # Validierungen
    def _valid_yyyymm(s: str) -> bool:
        return isinstance(s, (str, int)) and len(str(s)) == 6 and str(s).isdigit() and 1 <= int(str(s)[4:6]) <= 12

    if pipeline == "churn":
        req_fields = [exp.get("training_from"), exp.get("training_to"), exp.get("backtest_from"), exp.get("backtest_to")]
        if not all(_valid_yyyymm(x) for x in req_fields):
            return jsonify({"error": "Ungültige oder fehlende YYYYMM Felder für Churn"}), 400
        from bl.Churn.churn_auto_processor import ChurnAutoProcessor  # lazy import
        _append_log("INFO", "ui", f"🚀 Starte CHURN für Experiment {experiment_id}")
        def _worker():
            try:
                import sys as _sys
                old_out, old_err = _sys.stdout, _sys.stderr
                _sys.stdout = _StreamToLog("INFO", "churn_pipeline")
                _sys.stderr = _StreamToLog("ERROR", "churn_pipeline")
                try:
                    proc = ChurnAutoProcessor()
                    proc.process_experiment(exp)
                finally:
                    try:
                        _sys.stdout.flush(); _sys.stderr.flush()
                    except Exception:
                        pass
                    _sys.stdout, _sys.stderr = old_out, old_err
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()
        try:
            _ensure_global_fusion_view(db)
        except Exception:
            pass
        return jsonify({"accepted": True, "pipeline": "churn"}), 202

    if pipeline == "cox":
        # Optionaler Laufzeit-Parameter für Cox: cutoff_exclusive (YYYYMM)
        cutoff_payload = payload.get("cutoff_exclusive")
        hp = exp.get("hyperparameters") or {}
        cutoff = cutoff_payload if cutoff_payload is not None else hp.get("cutoff_exclusive")
        if not _valid_yyyymm(cutoff):
            return jsonify({"error": "cutoff_exclusive (YYYYMM) erforderlich für Cox"}), 400

        # Persistiere cutoff_exclusive im Experiment (kein generisches Hyperparameter-Formular nötig)
        try:
            if not isinstance(hp, dict):
                hp = {}
            hp["cutoff_exclusive"] = int(cutoff)
            db.update_experiment(experiment_id, {"hyperparameters": hp})
            db.save()
        except Exception:
            pass
        from bl.Cox.cox_auto_processor import CoxAutoProcessor  # lazy import
        _append_log("INFO", "ui", f"🚀 Starte COX für Experiment {experiment_id} (cutoff_exclusive={cutoff})")
        def _worker():
            try:
                import sys as _sys
                old_out, old_err = _sys.stdout, _sys.stderr
                _sys.stdout = _StreamToLog("INFO", "cox_pipeline")
                _sys.stderr = _StreamToLog("ERROR", "cox_pipeline")
                try:
                    proc = CoxAutoProcessor()
                    proc.process_experiment(exp)
                finally:
                    try:
                        _sys.stdout.flush(); _sys.stderr.flush()
                    except Exception:
                        pass
                    _sys.stdout, _sys.stderr = old_out, old_err
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()
        try:
            _ensure_global_fusion_view(db)
        except Exception:
            pass
        return jsonify({"accepted": True, "pipeline": "cox"}), 202

    if pipeline == "cf":
        # Voraussetzungen prüfen: Churn-Details und Cox-Daten für Experiment vorhanden
        try:
            tables = db.data.get("tables", {})
            cd = tables.get("customer_details", {}).get("records", []) or []
            pri = tables.get("cox_prioritization_results", {}).get("records", []) or []
            # Churn vorhanden?
            has_churn = any((r.get("source") == "churn" and int(r.get("experiment_id") or -1) == int(experiment_id)) for r in cd)
            # Cox vorhanden? (Prioritization oder Survival)
            has_cox = any(int(r.get("id_experiments") or -1) == int(experiment_id) for r in pri)
            if not has_cox:
                cs = tables.get("cox_survival", {}).get("records", []) or []
                has_cox = any(int(r.get("id_experiments") or -1) == int(experiment_id) for r in cs)
            if not has_churn or not has_cox:
                missing = []
                if not has_churn: missing.append("churn customer_details")
                if not has_cox: missing.append("cox data")
                return jsonify({"error": "Voraussetzungen fehlen: " + ", ".join(missing)}), 400
        except Exception as e:
            return jsonify({"error": f"Prereq check failed: {e}"}), 400

        _append_log("INFO", "ui", f"🚀 Starte CF für Experiment {experiment_id}")
        def _worker():
            try:
                import sys as _sys
                old_out, old_err = _sys.stdout, _sys.stderr
                _sys.stdout = _StreamToLog("INFO", "cf_pipeline")
                _sys.stderr = _StreamToLog("ERROR", "cf_pipeline")
                try:
                    from bl.Counterfactuals import counterfactuals_cli as _cf
                    # Standard: sample 1.0 (100% vollständige Analyse), limit 0 (alle)
                    _cf.run(experiment_id=int(experiment_id), sample=1.0, limit=0)
                finally:
                    try:
                        _sys.stdout.flush(); _sys.stderr.flush()
                    except Exception:
                        pass
                    _sys.stdout, _sys.stderr = old_out, old_err
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()
        try:
            _ensure_global_fusion_view(db)
        except Exception:
            pass
        return jsonify({"accepted": True, "pipeline": "cf"}), 202

    return jsonify({"error": "Unsupported pipeline"}), 400


@app.route("/sql/schema/<table>", methods=["GET"])
def get_schema(table: str):
    db = _open_db()
    meta = db.data.get("tables", {}).get(table, None)
    if not isinstance(meta, dict):
        return jsonify({"error": f"Tabelle '{table}' nicht gefunden"}), 404
    schema = meta.get("schema", {}) or {}
    # Normalize schema entries – falls leer, aus erstem Record ableiten
    fields: List[Dict[str, Any]] = []
    if schema:
        for col, info in schema.items():
            fields.append({
                "name": col,
                "display_type": (info or {}).get("display_type", "text"),
                "description": (info or {}).get("description", ""),
            })
    else:
        records = meta.get("records", []) or []
        if records:
            sample = records[0]
            for col, val in sample.items():
                # einfache Typ-Ableitung
                if isinstance(val, bool):
                    dtype = "boolean"
                elif isinstance(val, int):
                    dtype = "integer"
                elif isinstance(val, float):
                    dtype = "decimal"
                elif isinstance(val, (list, dict)):
                    dtype = "json"
                else:
                    dtype = "text"
                fields.append({
                    "name": col,
                    "display_type": dtype,
                    "description": "",
                })
    return jsonify({
        "table": table,
        "description": meta.get("description", ""),
        "source": meta.get("source", ""),
        "schema": fields
    })


@app.route("/sql/views", methods=["GET"])
def list_views():
    db = ChurnJSONDatabase()
    try:
        return jsonify({"views": db.list_views()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/sql/views", methods=["POST"])
def create_or_update_view():
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    query = (payload.get("query") or "").strip()
    description = payload.get("description")
    db = ChurnJSONDatabase()
    ok = db.add_or_update_view(name, query, description)
    if not ok:
        return jsonify({"error": "Invalid view definition (name/query)"}), 400
    db.save()
    return jsonify({"status": "ok"})


# -----------------------------
# Global Fusion View (Churn + Cox)
# -----------------------------
def _ensure_global_fusion_view(db: ChurnJSONDatabase) -> None:
    try:
        view_sql = (
            "SELECT c.Kunde, c.experiment_id, c.Letzte_Timebase, c.I_ALIVE, "
            "c.Churn_Wahrscheinlichkeit, c.Predicted_Optimal, "
            "crp.risk_category, crp.priority_score, crp.p_event_6m, crp.p_event_12m "
            "FROM customer_details c "
            "LEFT JOIN customer_risk_profile crp "
            " ON crp.experiment_id = c.experiment_id AND crp.Kunde = c.Kunde "
            "WHERE c.source = 'churn'"
        )
        db.add_or_update_view("churn_cox_fusion", view_sql, "Globale Fusion von Churn- und Cox-Details je Kunde/Experiment (filterbar per experiment_id)")
        try:
            db.save()
        except Exception:
            pass
    except Exception:
        pass

# -----------------------------
# Materialization helpers (per experiment)
# -----------------------------

def _materialize_churn_details_for_experiment(db: ChurnJSONDatabase, experiment_id: int) -> int:
    all_cd = db.data.get("tables", {}).get("customer_details", {}).get("records", []) or []
    churn_rec = [r for r in all_cd if r.get("source") == "churn" and r.get("experiment_id") == experiment_id]
    tbl_name = f"customer_churn_details_{int(experiment_id)}"
    t = db.data.setdefault("tables", {}).setdefault(tbl_name, {
        "description": "Churn Customer Details (materialisiert pro Experiment)",
        "source": "managementstudio",
        "metadata": {},
        "schema": {},
        "records": []
    })
    t["records"] = list(churn_rec)
    t["metadata"] = {"created_at": datetime.now().isoformat(), "row_count": len(churn_rec), "experiment_id": experiment_id}
    return len(churn_rec)


def _materialize_cox_details_for_experiment(db: ChurnJSONDatabase, experiment_id: int) -> int:
    # Quelle: cox_prioritization_results (direkt, ohne DuckDB-Abhängigkeit)
    pri = db.data.get("tables", {}).get("cox_prioritization_results", {}).get("records", []) or []
    def _risk_category(score):
        try:
            s = float(score) if score is not None else 0.0
        except Exception:
            s = 0.0
        if s >= 70: return "Sehr Hoch"
        if s >= 50: return "Hoch"
        if s >= 30: return "Mittel"
        if s >= 15: return "Niedrig"
        return "Sehr Niedrig"
    out = []
    for r in pri:
        try:
            if int(r.get("id_experiments")) != int(experiment_id):
                continue
        except Exception:
            continue
        out.append({
            "Kunde": r.get("Kunde"),
            "experiment_id": experiment_id,
            "risk_category": _risk_category(r.get("PriorityScore")),
            "priority_score": r.get("PriorityScore"),
            "p_event_6m": r.get("P_Event_6m"),
            "p_event_12m": r.get("P_Event_12m")
        })
    tbl_name = f"customer_cox_details_{int(experiment_id)}"
    t = db.data.setdefault("tables", {}).setdefault(tbl_name, {
        "description": "Cox Customer Details (materialisiert pro Experiment)",
        "source": "managementstudio",
        "metadata": {},
        "schema": {},
        "records": []
    })
    t["records"] = out
    t["metadata"] = {"created_at": datetime.now().isoformat(), "row_count": len(out), "experiment_id": experiment_id}
    return len(out)


@app.route("/experiments/<int:experiment_id>/materialize", methods=["POST"])
def materialize_experiment(experiment_id: int):
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        db = ChurnJSONDatabase()
        n_churn = _materialize_churn_details_for_experiment(db, experiment_id)
        n_cox = _materialize_cox_details_for_experiment(db, experiment_id)
        # Eine einzige, globale Fusions-View – filterbar per experiment_id
        try:
            view_sql = (
                "SELECT c.Kunde, c.experiment_id, c.Letzte_Timebase, c.I_ALIVE, "
                "c.Churn_Wahrscheinlichkeit, c.Predicted_Optimal, "
                "crp.risk_category, crp.priority_score, crp.p_event_6m, crp.p_event_12m "
                "FROM customer_details c "
                "LEFT JOIN customer_risk_profile crp "
                " ON crp.experiment_id = c.experiment_id AND crp.Kunde = c.Kunde "
                "WHERE c.source = 'churn'"
            )
            db.add_or_update_view("churn_cox_fusion", view_sql, "Globale Fusion von Churn- und Cox-Details je Kunde/Experiment (filterbar per experiment_id)")
        except Exception:
            pass
        db.save()
        return jsonify({
            "experiment_id": experiment_id,
            "churn_rows": n_churn,
            "cox_rows": n_cox,
            "fusion_view": "churn_cox_fusion"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sql/views/<name>", methods=["DELETE"])
def delete_view(name: str):
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 401
    db = ChurnJSONDatabase()
    ok = db.delete_view(name)
    if not ok:
        return jsonify({"error": "Not found"}), 404
    db.save()
    return jsonify({"status": "ok"})


@app.route("/sql/query", methods=["POST"])
def run_query():
    payload = request.get_json(silent=True) or {}
    sql = (payload.get("query") or "").strip()
    row_limit = int(payload.get("limit") or DEFAULT_ROW_LIMIT)
    row_limit = min(row_limit, DEFAULT_ROW_LIMIT)

    if not _is_read_only_sql(sql):
        return jsonify({
            "error": "Nur SELECT/EXPLAIN/PRAGMA/WITH erlaubt. Statement verweigert.",
            "allowed": list(ALLOWED_PREFIXES)
        }), 400

    # Views injizieren (aus JSON-DB), dann LIMIT anhängen
    db = ChurnJSONDatabase()
    try:
        db.maybe_reload()
    except Exception:
        pass
    injected_sql = _inject_saved_views(sql, db)
    safe_sql = _ensure_limit(injected_sql, row_limit)

    interface = SQLQueryInterface()
    db = interface.db  # underlying JSON DB (für Lineage & Tabellen)

    def _exec() -> List[Dict[str, Any]]:
        res = interface.execute_query(safe_sql, output_format="raw")
        # interface.execute_query kann Fehler-Strings zurückgeben
        if isinstance(res, str):
            # Transportiere als Fehler
            raise RuntimeError(res)
        if not isinstance(res, list):
            return []
        return res

    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            rows = pool.submit(_exec).result(timeout=QUERY_TIMEOUT_SECONDS)
        except FuturesTimeout:
            return jsonify({"error": f"Timeout nach {QUERY_TIMEOUT_SECONDS}s", "injected_sql": injected_sql, "effective_sql": safe_sql}), 504
        except Exception as e:
            # Liefere effektives SQL zur Diagnose mit aus
            return jsonify({
                "error": str(e),
                "injected_sql": injected_sql,
                "effective_sql": safe_sql
            }), 400

    # Ensure Lineage column
    rows = _attach_lineage(rows, db)

    # Prepare DataTables-compatible response (sanitize for JSON)
    rows = _sanitize_jsonable(rows)
    # Spaltenreihenfolge aus erstem Record ableiten (entspricht SELECT-Order)
    if rows:
        try:
            columns = list(rows[0].keys())
        except Exception:
            columns = sorted({k for r in rows for k in r.keys()})
    else:
        columns = []
    return jsonify({
        "columns": columns,
        "rows": rows,
        "row_count": len(rows)
    })


# -----------------------------
# Outbox Info (Stage0 quick access)
# -----------------------------

@app.route("/outbox/info", methods=["GET"])
def outbox_info():
    try:
        base = ProjectPaths.outbox_directory()
        stage0 = (base / "stage0_cache").resolve()
        files = []
        if stage0.exists():
            # Jüngste zuerst (max 20)
            items = sorted(stage0.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
            for p in items:
                try:
                    st = p.stat()
                    files.append({
                        "name": p.name,
                        "path": str(p),
                        "size": st.st_size,
                        "mtime": st.st_mtime
                    })
                except Exception:
                    files.append({"name": p.name, "path": str(p)})
        return jsonify({
            "outbox_root": str(base),
            "stage0_dir": str(stage0),
            "files": files,
            "count": len(files)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# CLI Stored Procedures Endpoints
# -----------------------------

@app.route("/cli", methods=["GET"])
def list_cli_runs():
    db = ChurnJSONDatabase()
    rows = db.data.get("tables", {}).get("cli", {}).get("records", []) or []
    return jsonify({"rows": rows, "count": len(rows)})

@app.route("/cli/run", methods=["POST"])
def run_cli_procedure():
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    proc = (payload.get("procedure") or "").strip().lower()
    params = payload.get("params") or {}
    if proc != "pivot_case":
        return jsonify({"error": "Unknown procedure"}), 400
    try:
        target_yyyymm = int(params.get("target_yyyymm"))
    except Exception:
        return jsonify({"error": "target_yyyymm required (YYYYMM)"}), 400
    years = int(params.get("years") or 2)
    month = int(params.get("month") or 12)
    scope = (params.get("scope") or "same-file").lower()
    threshold = (params.get("threshold") or "optimal").lower()
    base = (params.get("base") or "churned").lower()
    save_table = params.get("save_table") or f"pivot_case_{target_yyyymm}"
    overwrite = bool(params.get("overwrite"))

    interface = SQLQueryInterface()
    # If table exists and overwrite not requested → abort with hint
    db_check = interface.db
    if save_table in (db_check.data.get("tables", {}) or {}):
        if not overwrite:
            return jsonify({
                "error": f"Tabelle '{save_table}' existiert bereits.",
                "exists": True,
                "table_name": save_table
            }), 409
        # Overwrite: delete table and remove cli references
        try:
            tables = db_check.data.get("tables", {})
            if save_table in tables:
                del tables[save_table]
            cli_tbl = tables.get("cli", {"records": []})
            recs = cli_tbl.get("records", [])
            cli_tbl["records"] = [r for r in recs if r.get("table_name") != save_table]
            db_check.save()
        except Exception:
            pass
    sql = interface._build_pivot_case_sql(
        target_yyyymm=target_yyyymm,
        years=years,
        month=month,
        scope=scope,
        threshold=threshold,
        base=base
    )
    try:
        raw = interface._execute_with_duckdb(sql)
    except Exception as e:
        return jsonify({"error": str(e), "generated_sql": sql}), 400
    # Save table
    schema: Dict[str, Dict[str, str]] = {}
    if raw:
        sample = raw[0]
        for k, v in sample.items():
            if isinstance(v, bool):
                dt = "text"
            elif isinstance(v, int):
                dt = "integer"
            elif isinstance(v, float):
                dt = "decimal"
            else:
                dt = "text"
            schema[k] = {"display_type": dt, "description": ""}
    db = interface.db
    db.data["tables"][save_table] = {
        "description": "Gespeicherte Prozedur: pivot_case",
        "source": "sql_query_interface",
        "metadata": {
            "generated_by": "pivot_case",
            "params": params,
            "created_at": datetime.now().isoformat()
        },
        "schema": schema,
        "records": raw
    }
    db.save()
    # Record CLI run
    try:
        interface._record_cli_run("pivot_case", {
            "target_yyyymm": target_yyyymm,
            "years": years,
            "month": month,
            "scope": scope,
            "threshold": threshold,
            "base": base
        }, save_table)
    except Exception:
        pass
    return jsonify({"status": "ok", "table_name": save_table, "row_count": len(raw)})

@app.route("/cli/table/<name>", methods=["DELETE"])
def delete_cli_table(name: str):
    if not _check_password():
        return jsonify({"error": "Unauthorized"}), 401
    db = ChurnJSONDatabase()
    tables = db.data.get("tables", {})
    if name not in tables:
        return jsonify({"error": "Not found"}), 404
    try:
        # Nur CLI-Tabellen dürfen gelöscht werden → muss in cli-Referenzen auftauchen
        cli_tbl = tables.get("cli", {"records": []})
        recs = cli_tbl.get("records", [])
        if not any(r.get("table_name") == name for r in recs):
            return jsonify({"error": "Nur CLI-Tabellen können gelöscht werden."}), 400
        # Löschen
        del tables[name]
        cli_tbl["records"] = [r for r in recs if r.get("table_name") != name]
        db.save()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def create_app() -> Flask:
    return app


if __name__ == "__main__":
    # Hinweis: Von Projekt-Root starten, damit Imports funktionieren.
    # Beispiel: python ui/managementstudio/app.py
    port = int(os.environ.get("MGMT_STUDIO_PORT", "5051"))
    debug_flag = bool(os.environ.get("MGMT_STUDIO_DEBUG"))
    # Standard: stabiler Hintergrundbetrieb ohne Reloader/Debug
    app.run(host="127.0.0.1", port=port, debug=debug_flag, use_reloader=debug_flag, threaded=True)


