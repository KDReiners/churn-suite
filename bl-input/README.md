Last reviewed: 2025-09-21

# Input System - Business Logic Module

> SEALEDCOMPONENT: Ingestion-Flow gilt als stabil. Änderungen nur nach expliziter Rückfrage und architektonischer Prüfung.

```yaml
module_info:
  name: "Input business logic module"
  purpose: "Input business logic module"
  status: "DEVELOPMENT"
  integration_level: "COMPONENT"
  performance_target: "TBD"
  last_updated: "2025-09-21"
  ai_agent_optimized: true
```

## 🎯 **MODULE OVERVIEW**

### **Primary Functions:**
- **InputIngestionService Component** - Domänen-agnostischer Service zur Ingestion von CSV-Eingabedaten in Stage0.

Responsibilities:
- CSV-Hashing/Analyse delegiert an Step0 (keine Duplikation)
- Erzeugte Stage0-Datei lokalisieren (`stage0_cache/<hash>.json`)
- Optional: Registrierung in JSON-DB (Files-Tabelle)
 - Optional: Export der Stage0-JSON in die Outbox (`outbox/stage0_cache/`)

### **Business Impact:**
- **Input business functionality

## 🏗️ **ARCHITECTURE COMPONENTS**

### **Core Classes:**
```python
# Primary Components
InputIngestionService()    # Domänen-agnostischer Service zur Ingestion von CSV-Eingabedaten in Stage0.
```

### **Data Flow:**
```yaml
input:
  - "Stage0 cache data or configuration files"
  - "Module-specific parameters and settings"

process:
  1. "Data loading and validation"
  2. "Core processing logic"
  3. "Results generation and validation"
  4. "Output formatting and persistence"

output:
  - "Processed results and analyses"
  - "JSON-Database integration (where applicable)"
  - "Performance metrics and logs"
```

## 🚀 **QUICK START**

### **Setup (empfohlen: Python 3.11 venv)**
```bash
cd /Users/klaus.reiners/Projekte/churn-suite
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -U pip
pip install pandas==2.0.3 numpy==1.26.4 scikit-learn==1.3.2 duckdb==1.0.0

# optional: Ausgabeverzeichnisse sicherstellen
mkdir -p bl-churn/dynamic_system_outputs/stage0_cache bl-churn/dynamic_system_outputs/outbox
```

### **Direkte Ingestion einer CSV → Stage0 (+Outbox)**
```bash
cd /Users/klaus.reiners/Projekte/churn-suite
source .venv311/bin/activate
python -c "from bl_input_run import run; run()"  # siehe Programmatic API unten
```

### **Alternative (über DataAccessLayer mit Auto-Ingestion):**
```bash
# Lädt Stage0; erzeugt sie automatisch aus der neuesten CSV, falls nicht vorhanden
python -c "from config.data_access_layer import load_latest_stage0_data; df=load_latest_stage0_data(); print(df.shape)"
```

### **End-to-End Ingestion → JSON-DB rawdata (Union)**
```bash
# Führt CSV→Stage0→Outbox und danach Outbox→rawdata (Union, replace) aus
make -C bl-workspace ingest
```

### **Programmatic API:**
```python
from pathlib import Path
from input_ingestion import InputIngestionService

# Initialize component
service = InputIngestionService()

# Konkrete CSV verarbeiten
stage0_path, results = service.ingest_csv_to_stage0(
    csv_path=Path("/Users/klaus.reiners/Projekte/churn-suite/bl-input/input_data/churn_Data_cleaned.csv"),
    register_in_json_db=True,
    export_to_outbox=True,
)
print(stage0_path)
print(results.get("outbox_path"))

# Optional: kleiner Runner für CLI-ähnlichen Aufruf
def run():
    s = InputIngestionService()
    p1 = Path("/Users/klaus.reiners/Projekte/churn-suite/bl-input/input_data/churn_Data_cleaned.csv")
    p2 = Path("/Users/klaus.reiners/Projekte/churn-suite/bl-input/input_data/ChurnData_20250831.csv")
    for p in (p1, p2):
        sp, res = s.ingest_csv_to_stage0(p, register_in_json_db=True, export_to_outbox=True)
        print(sp)
        print(res.get("outbox_path"))
```

### **Outputs:**
- Stage0 Cache: `bl-churn/dynamic_system_outputs/stage0_cache/<csv_hash>.json`
- Outbox Export (optional): `bl-churn/dynamic_system_outputs/outbox/stage0_cache/<csv_hash>.json`

## 📊 **CONFIGURATION & CONSTANTS**

### **Key Configuration Files:**
```yaml
config_files:
  paths: "config/paths_config.py"
```

## 🔗 **SYSTEM INTEGRATION**

### **Dependencies:**
```yaml
internal_dependencies:
  - "bl.Churn.Step0_InputAnalysis"
  - "bl.json_database.churn_json_database"
  - "config.paths_config"

external_dependencies:
```

## 📈 **PERFORMANCE & MONITORING**

### **Performance Characteristics:**
```yaml
performance_metrics:
  processing_time: "< 30 seconds typical"
  memory_usage: "< 200MB typical"
  success_rate: "TBD - monitor in production"
  complexity_score: 13
```

## 🔧 **TROUBLESHOOTING FOR AI-AGENTS**

### **Common Issues:**
```yaml
configuration_errors:
  symptom: "Module fails to initialize"
  solution: "Check config file paths and dependencies; Python 3.11 venv aktiv; Dependencies installiert"

data_processing_errors:
  symptom: "Processing fails with data errors"
  solution: "Validate input data format and completeness"

integration_errors:
  symptom: "Database or external integration failures"
  solution: "Check connection parameters and permissions"
  
python_version_conflicts:
  symptom: "pandas/numpy ImportError (z. B. unter Python 3.13)"
  solution: "Repo-venv mit Python 3.11 verwenden (.venv311); Versionen: pandas 2.0.3, numpy 1.26.4, scikit-learn 1.3.2"
```

## 🧱 **Data Dictionary Typregeln (wirksam ab Stage0)**
- `Kunde`: INTEGER
- `i_*`: INTEGER (inkl. `I_Alive` als 1=alive, 0=churned)
- `I_TIMEBASE`: INTEGER (Format YYYYMM)
- `n_*`: DOUBLE (float)
- Typen werden über `json-database/config/shared/config/data_dictionary_optimized.json` bestimmt und zur Laufzeit nicht erzwungen gecastet.

---

**📅 Last Updated:** 2025-09-21
**🤖 Optimized for:** AI-Agent maintenance and usage
**🎯 Status:** Development
**🔗 Related:** docs/INPUT_ARCHITECTURE_SPECIFICATION.md