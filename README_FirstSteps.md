# 🚀 Churn Suite - Erste Schritte

## 📋 Voraussetzungen

- **macOS** (getestet auf macOS 24.6.0)
- **Python 3.9+** (aktuell: Python 3.9.6)
- **Git** (für Submodule)

## 🔧 Umgebung aktivieren

### 1. Virtuelle Umgebung aktivieren
```bash
cd /Users/klaus.reiners/Dokumente/Projekte/churn-suite
source .venv/bin/activate
```

### 2. Aktivierung bestätigen
```bash
# Python-Version prüfen
python --version

# Wichtige Pakete testen
python -c "import pandas, numpy, sklearn, catboost; print('✅ Umgebung bereit!')"
```

### 3. Umgebung deaktivieren (wenn fertig)
```bash
deactivate
```

## 🛠️ Make-Optionen

### Haupt-Makefile (Root-Verzeichnis)

#### Service-Management
```bash
# Alle Services starten
make start

# Services stoppen
make stop

# Services neu starten
make restart

# Datenbank komplett leeren
make cleanDB

# Service-Status prüfen
make status

# Alle Services herunterfahren
make down
make shutdown
```

#### Logs
```bash
# Log-Verzeichnis erstellen
make logs
```

### Service-Ports
- **Runner-Service**: Port 5050
- **Management Studio**: Port 5051 (liefert auch UI-CRUD unter /crud)
- **UI-CRUD**: Port 5051 (Pfad: /crud)

### Workspace-Makefile (bl-workspace/)

#### Entwicklungsumgebung
```bash
# Entwicklungsumgebung starten
make up

# Management Studio öffnen
make mgmt

# CRUD-Interface öffnen
make crud

# Churn-Analyse ausführen
make churn ARGS="--help"

# Umgebungsvariablen anzeigen
make env

# Entwicklungsumgebung stoppen
make down

# Browser öffnen
make open

# Daten importieren (CSV → Stage0 → Outbox → rawdata)
make ingest

# Daten importieren mit spezifischer Datei
make ingest ARGS="--override churn_Data_cleaned.csv"
```

## 📊 Datenverarbeitung

### Input-Daten verarbeiten
```bash
# Option 1: Vom Root-Verzeichnis (empfohlen)
make ingest

# Option 2: Vom bl-workspace-Verzeichnis
cd bl-workspace
make ingest

# Spezifische CSV-Datei verarbeiten
make ingest ARGS="--override churn_Data_cleaned.csv"

# Datenbank komplett leeren (ACHTUNG: Löscht alle Daten!)
make cleanDB

# Churn-Analyse ausführen
cd bl-workspace
make churn ARGS="--help"
```

### Datenverarbeitungs-Pipeline
1. **CSV-Dateien** (`bl-input/input_data/`) werden analysiert
2. **Stage0-JSON** wird in `dynamic_system_outputs/stage0_cache/` erstellt
3. **Outbox-Export** nach `dynamic_system_outputs/outbox/stage0_cache/`
4. **JSON-Datenbank** wird mit `rawdata` (Union) aktualisiert

## 🌐 Services aufrufen

Nach dem Start der Services:

### Runner-Service (Port 5050)
- **Health-Check**: http://localhost:5050/health
- **API-Dokumentation**: http://localhost:5050/docs
- **Root**: http://localhost:5050/

### Management Studio (Port 5051)
- **Hauptseite**: http://localhost:5051
- **SQL-Interface**: http://localhost:5051/sql
- **Datenbank-Management**: http://localhost:5051/db

### UI-CRUD & Pipeline Runner (über Management Studio, Port 5051)
- **Hauptseite**: http://localhost:5051/crud
- **Debug-Interface**: http://localhost:5051/crud/debug
- **Experimente**: http://localhost:5051/crud/experiments.html
- **Pipeline Runner**: http://localhost:5051/crud/index.html

## 📁 Projektstruktur

```
churn-suite/
├── .venv/                    # Zentrale virtuelle Umgebung
├── requirements.txt          # Python-Abhängigkeiten
├── Makefile                  # Service-Management
├── bl-workspace/
│   ├── Makefile             # Entwicklungsumgebung
│   └── dev                  # Entwicklungs-Skript
├── bl-churn/                # Churn-Analyse-Module
├── bl-cox/                  # Cox-Regression-Module
├── bl-counterfactuals/      # Counterfactual-Analyse
├── json-database/           # JSON-Datenbank-Interface
├── ui-managementstudio/     # Management Studio
├── ui-crud/                 # CRUD-Interface
└── runner-service/          # Service-Orchestrator
```

## ⚠️ Bekannte Probleme

### XGBoost & LightGBM
Diese Pakete benötigen OpenMP auf macOS:

```bash
# Homebrew installieren (falls nicht vorhanden)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# OpenMP installieren
brew install libomp
```

### Alternative: Nur grundlegende Pakete verwenden
```bash
# Test ohne XGBoost/LightGBM
python -c "import pandas, numpy, sklearn, catboost; print('✅ Grundlegende Pakete funktionieren!')"
```

## 🔄 Typischer Workflow

1. **Umgebung aktivieren**
   ```bash
   cd /Users/klaus.reiners/Dokumente/Projekte/churn-suite
   source .venv/bin/activate
   ```

2. **Services starten**
   ```bash
   make start
   ```

3. **Status prüfen**
   ```bash
   make status
   ```

4. **Daten verarbeiten** (optional)
   ```bash
   make ingest
   ```

5. **Arbeiten**
   - Runner-Service: http://localhost:5050/health
   - Management Studio: http://localhost:5051/sql
   - CRUD-Interface: http://localhost:5051/crud
   - Pipeline Runner: http://localhost:5051/crud/index.html

6. **Services stoppen**
   ```bash
   make stop
   ```

7. **Umgebung deaktivieren**
   ```bash
   deactivate
   ```

## 🔁 Git‑Workflow (einfach, ohne Branches)

Du arbeitest direkt auf `main` und sicherst alles mit einem Befehl nach Remote.

1) Sicherstellen, dass du auf `main` bist (nur einmal nötig):
```bash
git switch main
```

2) Änderungen speichern und pushen:
```bash
# a) Alles committen (inkl. untracked Dateien)
make save m="feat: deine Nachricht"

# b) Push auf Remote
make push

# c) Beides in einem Schritt
make savepush m="feat: deine Nachricht"
```

Hinweise:
- Die Auto‑PR‑Automatisierung greift nur bei Nicht‑`main`‑Branches. Auf `main` gibt es keine PR‑Pflicht.
- Wenn du später mit Branches arbeiten willst: Branch erstellen und pushen → PR wird automatisch erstellt.

## ⚠️ **Datenbank-Management**

### Datenbank komplett leeren
```bash
# ACHTUNG: Löscht ALLE Daten in der Datenbank!
make cleanDB

# Danach Daten neu laden
make ingest
```

### Workflow für sauberen Neustart
```bash
# 1. Services stoppen
make stop

# 2. Datenbank leeren
make cleanDB

# 3. Services starten
make start

# 4. Daten neu laden
make ingest
```

## 📞 Hilfe

- **Service-Status**: `make status`
- **Logs anzeigen**: `tail -f logs/runner.log`
- **Alle Logs**: `ls -la logs/`
- **Ports prüfen**: 
  - Runner-Service: `lsof -i :5050`
  - Management Studio: `lsof -i :5051`
  - UI-CRUD: `lsof -i :5052`

### Prozesse manuell beenden (Beispiel)

```bash
# 1) PID ermitteln (Beispiel: Runner-Service auf Port 5050)
lsof -ti tcp:5050

# 2) Prozess beenden (PID aus Schritt 1 einsetzen)
kill -TERM <PID>   # sauberer Stopp
# Falls nötig (hart beenden):
kill -9 <PID>

# Einzeiler (ohne manuelles Einsetzen der PID):
lsof -ti tcp:5050 | xargs -n 1 kill
```

---

**🎯 Sie sind bereit!** Aktivieren Sie die Umgebung und starten Sie die Services.
