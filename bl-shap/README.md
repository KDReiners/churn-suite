# bl-shap - SHAP-Erklärbarkeit

**Last reviewed: 2025-09-29**

## 🎯 **Zweck**

Business-Logic für SHAP-Erklärbarkeit mit Digitalization-Segmentierung.

## 🏗️ **Architektur**

- **TreeExplainer**: Unterstützt RandomForest, XGBoost, LightGBM, CatBoost
- **Globale SHAP**: Feature-Importance-Ranking
- **Lokale SHAP**: Top-K Erklärungen pro Kunde
- **Segmentierung**: Digitalization-basierte Cluster-Analyse

## 🚀 **Quick Start**

### **Pipeline starten:**
```bash
# Über UI
http://localhost:8080/ → Experiment auswählen → "SHAP" starten

# Über API
curl -X POST http://localhost:5050/run/shap -d '{"experiment_id":1}'
```

### **Ergebnisse ansehen:**
- **Management Studio**: http://localhost:5051/sql/
- **Tabellen**: `shap_global`, `shap_local_topk`, `shap_global_by_digitalization`

## 📊 **Output-Tabellen**

- `shap_global`: Globale Feature-Importance
- `shap_local_topk`: Top-K Erklärungen pro Kunde
- `shap_global_aggregated`: Aggregierte Raw-Features
- `shap_global_by_digitalization`: Segmentierte SHAP-Analyse

## 🔧 **Features**

- **Tree-Modelle**: RandomForest, XGBoost, LightGBM, CatBoost
- **Aggregation**: Raw-Feature-Aggregation über Mapping
- **Segmentierung**: Digitalization-Cluster-Analyse
- **Persistenz**: JSON-DB und Outbox-Export

## 📚 **Dokumentation**

**Zentrale Dokumentation:** [NEXT_STEPS.md](../NEXT_STEPS.md)

**Detaillierte Anleitungen:**
- [bl-shap/nextSteps.md](nextSteps.md) - Entwicklungshinweise