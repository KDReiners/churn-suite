# Next Steps - Churn Suite Development

**Last updated:** 2025-09-22  
**Status:** Pipeline vollständig funktionsfähig ✅ - DuckDB Mixed-Type Problem gelöst ✅ - Management Studio funktionsfähig ✅ - Ingestion & Lineage bereinigt ✅

## 🎯 Was wir erreicht haben

### ✅ Experiment CRUD System (KOMPLETT)

**Problem gelöst:** Keine Experimente wurden in der Web-UI angezeigt

**Implementierte Lösung:**
- **Zentrale Python-Umgebung**: Alle separaten `requirements.txt` gelöscht, eine `.venv` auf Root-Ebene
- **Import-Probleme behoben**: `tabulate` und andere Dependencies korrekt installiert und erkannt
- **CORS-Support**: Cross-Origin-Requests zwischen UI (Port 8080) und API (Port 5050) funktionieren
- **Persistenz-Bug behoben**: `json_db.save()` nach Experiment-Erstellung und -Löschung hinzugefügt
- **API-Parameter-Fix**: `id_files` vs `file_ids` Parameter-Mismatch korrigiert
- **UI konsolidiert**: Nur noch eine `experiments.html` (alte Version gelöscht)
- **DOM-Loading verbessert**: JavaScript wartet auf DOM-Ready
- **Model Type vereinfacht**: Readonly Info-Feld, fest auf "churn" gesetzt
- **Feature Set beschränkt**: Nur "standard" und "enhanced" Optionen

**Ergebnis:**
```
✅ URL: http://localhost:8080/experiments.html
✅ Funktionen: Erstellen, Anzeigen, Bearbeiten, Löschen
✅ Persistenz: Alle Änderungen werden in JSON-DB gespeichert
✅ Navigation: Von Pipeline Runner zu Experiment CRUD
```

### 🏗️ Technische Architektur

**Services:**
- **Runner-Service** (Port 5050): FastAPI mit CORS-Middleware
- **CRUD-Frontend** (Port 8080): Statischer HTTP-Server
- **JSON-Database**: Zentrale Datenhaltung mit ChurnJSONDatabase

**Datenfluss:**
```
Browser (8080) → CORS → Runner-Service (5050) → JSON-Database → Persistenz
```

### ✅ Pipeline-Integration (KOMPLETT)

**Problem gelöst:** Pipeline-UI und Experiment-Pipeline-Kopplung funktionieren vollständig

**Implementierte Lösung:**
- **Pipeline-UI repariert**: `index.html` lädt Experimente und zeigt sie an
- **Experiment-Auswahl**: Dropdown mit automatischer Form-Befüllung
- **API-Endpunkte funktional**: `/run/churn`, `/experiments/{id}/run` implementiert
- **DataAccess.load_stage0_data()**: Pipeline kann rawdata aus JSON-Database laden
- **Zentrale Architektur**: Singleton-Pattern für ChurnJSONDatabase
- **881.177 Records**: rawdata erfolgreich aus bl-input → Stage0 → Outbox → JSON-DB (2 Input-CSV-Dateien)

**Ergebnis:**
```
✅ URL: http://localhost:8080/               # Pipeline Runner
✅ Experiment-Auswahl: Dropdown mit Details
✅ Pipeline-Start: Churn-Pipeline läuft bis Enhanced Early Warning
✅ Datenfluss: CSV → Stage0 → rawdata → DataFrame (442.959 Records)
✅ Zentrale DB: Nur eine JSON-Database mit Singleton-Pattern
```

### ✅ Zentrale Architektur (KOMPLETT)

**Vollständige Zentralisierung erreicht:**
- **Pfade**: Nur eine `config/paths_config.py` (5 dezentrale gelöscht)
- **JSON-Database**: Nur eine `dynamic_system_outputs/churn_database.json` (3 dezentrale gelöscht)
- **Singleton-Pattern**: ChurnJSONDatabase als Singleton implementiert
- **Konsistente Daten**: Alle Module verwenden die gleiche Dateninstanz

### ✅ Churn-Pipeline Vollständig Funktionsfähig (KOMPLETT)

**Problem gelöst:** Pipeline läuft vollständig durch mit korrekten Ergebnissen

**Behobene Kritische Fehler:**
1. **`'dict' object has no attribute 'data_dictionary'`** ✅ BEHOBEN
   - `data_schema.py` korrigiert: `DataSchema`-Objekt statt Dictionary zurückgeben
   - `enhanced_early_warning.py` erhält jetzt korrektes Schema-Objekt

2. **`TypeError: unhashable type: 'list'` bei `nunique()`** ✅ BEHOBEN
   - Technische Metadaten-Spalten (`id`, `id_files`, `dt_inserted`) werden beim Laden ausgeschlossen
   - `data_access_layer.py` filtert problematische Listen-Spalten sofort heraus

3. **`KeyError: "None of [Index([-2, -2, ...])] are in the [columns]"`** ✅ BEHOBEN
   - Boolean-Logik in `enhanced_early_warning.py` korrigiert
   - `~customer_future[target_col]` → `customer_future[target_col] == 0`
   - `I_Alive` jetzt konsistent als Integer (0=churned, 1=aktiv)

4. **Management Studio Type-Mismatch-Errors** ✅ BEHOBEN
   - `I_ALIVE` und alle `Predicted_*` Felder als Integer (0/1) statt Boolean
   - SQL-Validierung korrigiert (Word-Boundaries für `GROUP BY`/`ORDER BY`)
   - `customer_details` → `customer_churn_details` umbenannt

**Pipeline-Performance (mit 10% Kunden-Reduktion):**
- **Laufzeit**: 121.1s (deutlich beschleunigt)
- **AUC**: 1.0000 (Perfect Score)
- **Precision**: 0.8235
- **Recall**: 1.0000  
- **F1-Score**: 0.9032

**Vollständige Tabellen-Ergebnisse (Clean Import):**
- `rawdata`: **881,177** Records ✅
- `backtest_results`: **474** Records ✅  
- `customer_churn_details`: **1,089** Records ✅
- `experiment_kpis`: **4** Records ✅
- `churn_threshold_metrics`: **3** Records ✅
- `churn_model_metrics`: **2** Records ✅

## ✅ Management Studio Frontend - DuckDB Mixed-Type Problem GELÖST

### 🎉 Problem erfolgreich behoben

**Root Cause identifiziert und behoben:**
- ❌ **Problem**: `pd.get_dummies()` erzeugte Boolean-Spalten die mit Float-Spalten in DuckDB kollidierten
- ❌ **Fehler**: "Mismatch Type Error: Type BOOLEAN does not match with DOUBLE"
- ✅ **Lösung**: Explizite `.astype(int)` Konvertierung für alle One-Hot-Features in `enhanced_early_warning.py`
- ✅ **Zusätzlich**: Boolean→Integer Konvertierung in `sql_query_interface.py` für DuckDB-Kompatibilität

**Erfolgreiche Fixes:**
- ✅ `enhanced_early_warning.py`: Alle `pd.get_dummies()` Outputs als Integer (0/1)
- ✅ `sql_query_interface.py`: Mixed-Type-Handling für DuckDB-Registrierung  
- ✅ `data_dictionary_optimized.json`: Schema-Konsistenz (Boolean→Integer)
- ✅ `churn_json_database.py`: Explizite Type-Casting für `I_ALIVE` und `Predicted_*`

**Ergebnis:**
- ✅ **customer_churn_details**: 474 Records, 292 Spalten - vollständig funktionsfähig
- ✅ **Management Studio**: `http://localhost:5001/sql/` zeigt alle Daten korrekt an
- ✅ **SQL-Queries**: Alle Tabellen ohne Type-Mismatch-Errors abrufbar

## 🎯 Nächste Aufgabe: Cox-Integration (Runner · Persistenz · UI)

### 📋 TODO: Cox-Integration End-to-End

#### Priorität: HOCH – Vollständige End-to-End Integration (Runner → JSON‑DB → UI)

**Ziel:** Cox-Pipeline lauffähig machen (Runner-API, Persistenz in JSON‑DB, Anzeige im Management Studio, optionaler UI‑Trigger)

#### Schritte:
1. **Runner-API erweitern**:
   ```bash
   # Neue Endpunkte / Routen
   # - POST /run/cox (direkter Start)
   # - POST /experiments/{id}/run  (pipeline="cox")
   # - Parameter: cutoff_exclusive (YYYYMM) via experiments.hyperparameters
   ```

2. **Persistenz in JSON‑DB**:
   ```bash
   # Tabellen befüllen/anlegen:
   # - cox_survival
   # - cox_prioritization_results
   # Materialisierung im Mgmt‑Studio:
   # - customer_cox_details_{experiment_id}
   # Fusion‑View:
   # - churn_cox_fusion (join auf experiment_id & Kunde)
   ```

3. **UI (optional)**:
   ```bash
   # UI-Trigger auf index.html
   # - Sektion „Cox Survival“: Button → POST /experiments/{id}/run?pipeline=cox
   # - Anzeige: letzte Cox-Metriken im Statusbereich
   ```

4. **Data Quality Validierung**:
   ```bash
   # Cox-Tabellen in Mgmt‑Studio prüfen:
   # - survival records ≈ Anzahl Testkunden
   # - prioritization scores vorhanden
   # Fusion-View liefert je Kunde Priorität & p_event_* zusammen mit Churn‑Prob.
   ```

### 🔁 Idempotenz-Kriterien (Churn + Cox):
- Mehrfacher Start der gleichen Pipeline (gleiche `experiment_id` und Zeiträume) erzeugt keine Duplikate in:
  - Churn: `backtest_results` (replace je Experiment), `customer_churn_details`
  - Cox: `cox_survival`, `cox_prioritization_results` (replace/append konsistent je Experiment)

#### Erwartete Ergebnisse:
- ✅ **Pipeline-Start**: Über UI erfolgreich initiierbar
- ✅ **Vollständiger Durchlauf**: Ohne Fehler bis zum Ende
- ✅ **Tabellen-Generation**: Alle 6 Tabellen korrekt gefüllt
- ✅ **Management Studio**: Sofortige Verfügbarkeit der Ergebnisse
- ✅ **Performance**: Stabile Laufzeiten (~2-3 Minuten)

#### Success Criteria:
```bash
✅ Pipeline über http://localhost:8080/ erfolgreich gestartet
✅ Experiment-Dropdown funktioniert und befüllt Form automatisch
✅ Churn-Pipeline läuft vollständig durch (SUCCESS-Status)
✅ Management Studio zeigt alle Churn- und Cox-Tabellen korrekt an
✅ Keine DuckDB Type-Mismatch-Errors
✅ Churn: AUC ≥ 0.8; Cox: sinnvolle Prioritization‑Verteilung
✅ Idempotenz: Zweiter Lauf erzeugt keine Duplikate in Ergebnistabellen
```

### 📊 Aktueller Workflow-Status

**Pipeline-Workflow (Churn VOLLSTÄNDIG, Cox in Arbeit):**
```
1. Experiment erstellen (experiments.html) ✅ KOMPLETT
2. Pipeline starten (index.html) ✅ KOMPLETT  
3. Pipeline vollständig durchlaufen ✅ KOMPLETT (SUCCESS, alle Tabellen gefüllt)
4. Data Quality über SQL-API ✅ KOMPLETT (verlässliche Schnittstelle)
5. Ergebnisse analysieren (Management Studio) ✅ CHURN KOMPLETT · COX in Arbeit
```

**Erreichte Ziele:**
- ✅ Experimente können direkt aus der UI gestartet werden
- ✅ Pipeline läuft vollständig durch (876.436 Records → 6 gefüllte Tabellen)
- ✅ Zentrale Architektur mit Singleton-Pattern
- ✅ Enhanced Early Warning Fehler behoben (alle 4 kritischen Bugs gefixt)
- ✅ Pipeline liefert SUCCESS mit perfekten Metriken (AUC 1.0)
- ✅ Data Quality über SQL-API verlässlich verfügbar
- ✅ Artefakte (Modelle, Backtest-Results) korrekt persistiert
- ✅ **DuckDB Mixed-Type Problem gelöst** (Boolean→Integer Konvertierung)
- ✅ **Management Studio vollständig funktionsfähig** (474 Records, 292 Spalten)

**Nächster Schritt:**
- 🎯 **UI-Pipeline End-to-End Test** (Vollständige Integration validieren)

## 🔧 Development Environment

**Setup:**
```bash
# Services starten
cd /Users/klaus.reiners/Projekte/churn-suite
source .venv/bin/activate
python runner-service/app.py &
cd ui-crud && python3 -m http.server 8080 &
python ../ui-managementstudio/app.py &

# URLs
http://localhost:8080/experiments.html  # Experiment CRUD ✅
http://localhost:8080/                  # Pipeline Runner ✅ (NÄCHSTER TEST)
http://localhost:5001/sql/              # Management Studio ✅
http://localhost:5050/docs             # API Documentation ✅
```

**Key Files:**
- `runner-service/app.py` - FastAPI Backend ✅
- `ui-crud/experiments.html` - Experiment CRUD ✅
- `ui-crud/index.html` - Pipeline Runner ✅ (NÄCHSTER TEST)
- `ui-managementstudio/app.py` - Management Studio ✅
- `json-database/bl/json_database/churn_json_database.py` - Data Layer ✅

## 📝 Lessons Learned

1. **Python Environment Management**: Zentrale `.venv` ist kritisch für Dependency-Konsistenz
2. **CORS Configuration**: Cross-Origin-Requests müssen explizit erlaubt werden
3. **DOM Loading**: JavaScript muss auf DOM-Ready warten
4. **API Consistency**: Parameter-Namen zwischen Frontend und Backend müssen übereinstimmen
5. **Persistenz**: `save()` Aufrufe sind essentiell für Datenbeständigkeit

6. **DuckDB Type System**: Mixed Boolean/Float Columns führen zu Type-Mismatch-Errors
7. **One-Hot Encoding**: `pd.get_dummies()` muss explizit zu Integer konvertiert werden  
8. **Root Cause Analysis**: Systematische Problem-Lösung verhindert Workarounds
9. **Type Consistency**: Schema-Definition muss mit Implementation übereinstimmen

---

**Next Session Focus:** UI-Pipeline End-to-End Test → Idempotenz verifizieren 🎯

**Aktueller Stand:** 
- ✅ Pipeline-Integration: KOMPLETT
- ✅ Zentrale Architektur: KOMPLETT  
- ✅ Datenfluss: KOMPLETT (881.177 Records → Tabellen korrekt gefüllt)
- ✅ Pipeline: KOMPLETT (SUCCESS mit AUC 1.0)
- ✅ Data Quality API: KOMPLETT (verlässliche SQL-Schnittstelle)
- ✅ Management Studio: KOMPLETT (DuckDB Mixed-Type Problem gelöst)
- 🎯 **NÄCHSTER TEST**: UI-Pipeline End-to-End Validierung (Idempotenz)

---

## 🧭 Lineage & Files (bereinigt)

- `files` enthält ausschließlich `input_data` (Ursprungs-CSV-Dateien)
- `rawdata.id_files` referenziert die Input-File-IDs (nicht Stage0/Backtest)
- Backtest-JSONs und Stage0-JSONs werden nicht in `files` gezählt
- Clean Import Validierung: `files=2`, `rawdata=881.177`, Verteilung pro `id_files`: `1 → 442.959`, `3 → 438.218`
