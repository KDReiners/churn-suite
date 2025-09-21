# Input System - Business Logic Module

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

## 🚀 **QUICK START FOR AI-AGENTS**

### **Basic Usage (direct ingestion):**
```bash
# Environment setup
source churn_prediction_env/bin/activate
cd /Users/klaus.reiners/Projekte/Cursor\ ChurnPrediction\ -\ Reengineering

# Ingestion der neuesten CSV → Stage0 (mit JSON-DB-Registrierung)
python -c "from bl.Input import ingest_csv_to_stage0; from config.paths_config import ProjectPaths as P; p=P.main_churn_data_file(); print(ingest_csv_to_stage0(p, register_in_json_db=True)[0])"
```

### **Alternative (über DataAccessLayer mit Auto-Ingestion):**
```bash
# Lädt Stage0; erzeugt sie automatisch aus der neuesten CSV, falls nicht vorhanden
python -c "from config.data_access_layer import load_latest_stage0_data; df=load_latest_stage0_data(); print(df.shape)"
```

### **Programmatic API:**
```python
from bl.Input.input_ingestion import InputIngestionService

# Initialize component
service = InputIngestionService()
stage0_path, results = service.ensure_stage0_for_latest_input(register_in_json_db=True)
print(stage0_path)
```

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
  solution: "Check config file paths and dependencies"

data_processing_errors:
  symptom: "Processing fails with data errors"
  solution: "Validate input data format and completeness"

integration_errors:
  symptom: "Database or external integration failures"
  solution: "Check connection parameters and permissions"
```

## 📋 **AI-AGENT MAINTENANCE CHECKLIST**

### **After Code Changes:**
```yaml
validation_steps:
  - "Test: Basic functionality with sample data"
  - "Verify: All dependencies still accessible"
  - "Check: Integration points function correctly"
  - "Validate: Performance within expected ranges"

update_requirements:
  - "API changes → Update programmatic examples in this README"
  - "Performance changes → Update metrics section"
  - "New dependencies → Update dependencies section"
  - "Configuration changes → Update config examples"
```

---

**📅 Last Updated:** 2025-09-21
**🤖 Optimized for:** AI-Agent maintenance and usage
**🎯 Status:** Development
**🔗 Related:** docs/INPUT_ARCHITECTURE_SPECIFICATION.md