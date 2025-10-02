# Erste Schritte - Churn Suite

**Last reviewed: 2025-10-02**

## 🚀 **Schnellstart**

### **1. Services starten (Make):**
```bash
cd /Users/klaus.reiners/Dokumente/Projekte/churn-suite
make start          # Runner (5050) + Management Studio (5051)
# make restart / make status / make down
```

### **2. URLs öffnen:**
- **Pipeline Runner**: http://localhost:8080/
- **Experiment CRUD**: http://localhost:8080/experiments.html  
- **Management Studio**: http://localhost:5051/sql/
- **API Docs**: http://localhost:5050/docs

### **3. Erste Schritte:**
1. **Experiment erstellen**: http://localhost:8080/experiments.html
2. **Pipeline starten**: http://localhost:8080/ → Experiment auswählen → "Churn" starten
3. **Ergebnisse ansehen**: http://localhost:5051/sql/ → Tabellen durchsuchen

### **4. Daten laden (CSV → Stage0 → rawdata):**
```bash
make ingest
```
Dabei wird automatisch normalisiert:
- `files.parent_file_id`: Stage0‑JSON verweist auf das zugehörige CSV.
- `experiments.file_id`: FK → CSV (`id_files` entfällt).
- `rawdata.file_id`: FK → CSV, keine `id_files` mehr.

Beispiel‑Join von Experiment zu Rohdaten:
```sql
SELECT r.*
FROM experiments e
JOIN rawdata r ON r.file_id = e.file_id
WHERE e.experiment_id = 1;
```

### **5. Datenbank leeren:**
```bash
make cleanDB                 # Tabellen leeren, Views bleiben erhalten
make cleanDB DROP_VIEWS=1    # Tabellen UND Views löschen
```

## 📊 **Verfügbare Pipelines**

- **Churn**: Enhanced Early Warning Model
- **Cox**: Survival-Analyse mit Prioritization
- **SHAP**: Feature-Erklärbarkeit 
## 📚 **Dokumentation**

**Zentrale Dokumentation:** [NEXT_STEPS.md](NEXT_STEPS.md)

**Detaillierte Anleitungen:**
- [README.md](README.md) - Vollständige Systemübersicht
- [bl-churn/README.md](bl-churn/README.md) - Churn-Pipeline
- [bl-cox/README.md](bl-cox/README.md) - Cox-Analyse
- [bl-counterfactuals/README.md](bl-counterfactuals/README.md) - Counterfactuals
- [bl-shap/README.md](bl-shap/README.md) - SHAP-Erklärbarkeit