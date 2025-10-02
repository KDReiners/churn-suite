# ui-managementstudio - Management Studio

**Last reviewed: 2025-09-29**

## 🎯 **Zweck**

Web-UI für SQL-Abfragen auf JSON-Database und Pipeline-Management.

## 🏗️ **Architektur**

- **Flask-App**: Web-Interface für JSON-DB
- **SQL-Interface**: DuckDB-basierte Abfragen
- **Pipeline-Integration**: Experiment-Management und Pipeline-Trigger
- **CORS-Support**: Cross-Origin-Requests für Frontend

## 🚀 **Quick Start**

### **Service starten:**
```bash
cd /Users/klaus.reiners/Dokumente/Projekte/churn-suite
source .venv/bin/activate
python ui-managementstudio/app.py
```

### **URLs:**
- **SQL-Interface**: http://localhost:5051/sql/
- **Pipeline Runner**: http://localhost:8080/ (über ui-crud)
- **Experiment CRUD**: http://localhost:8080/experiments.html

## 📊 **Features**

### **SQL-Interface:**
- DuckDB-basierte Abfragen auf JSON-Database
- Tabellen-Übersicht und Schema-Info
- Query-History und Export-Funktionen

### **Pipeline-Management:**
- Experiment-Erstellung und -Verwaltung
- Pipeline-Trigger (Churn, Cox, SHAP, CF)
- Live-Log-Streaming und Status-Monitoring

## 🔧 **Konfiguration**

- **Port**: 5051 (Standard)
- **JSON-DB**: Automatische Erkennung über `config/paths_config.py`
- **CORS**: Cross-Origin-Requests für Frontend-Integration

## 📚 **Dokumentation**

**Zentrale Dokumentation:** [NEXT_STEPS.md](../NEXT_STEPS.md)

**Detaillierte Anleitungen:**
- [ui-managementstudio/RUNBOOK.md](RUNBOOK.md) - Betriebsabläufe