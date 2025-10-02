#!/usr/bin/env python3
"""
Data Ingestion Script für Churn Suite
Verarbeitet CSV-Dateien: CSV → Stage0 → Outbox → rawdata
"""

import sys
import os
from pathlib import Path

# Projekt-Root ermitteln
repo_root = Path(__file__).resolve().parent

# Python-Pfad erweitern
sys.path.extend([
    str(repo_root / 'bl-input'),
    str(repo_root / 'bl-churn'),
    str(repo_root / 'json-database')
])

# Outbox-Root setzen (korrigiert für tatsächlichen Pfad)
os.environ['OUTBOX_ROOT'] = str(repo_root / 'dynamic_system_outputs' / 'outbox')

# Ausgabeverzeichnisse erstellen
(repo_root / 'dynamic_system_outputs' / 'stage0_cache').mkdir(parents=True, exist_ok=True)
(repo_root / 'dynamic_system_outputs' / 'outbox').mkdir(parents=True, exist_ok=True)

try:
    from input_ingestion import InputIngestionService
    from bl.json_database.churn_json_database import ChurnJSONDatabase
    from config.paths_config import ProjectPaths
    
    print("Starting data ingestion (CSV → Stage0 → Outbox → rawdata)...")
    
    # Services initialisieren
    service = InputIngestionService()
    db = ChurnJSONDatabase()
    
    # Korrigiere Outbox-Pfad für ProjectPaths
    original_outbox = ProjectPaths.outbox_directory()
    correct_outbox = repo_root / 'dynamic_system_outputs' / 'outbox'
    print(f"Original outbox path: {original_outbox}")
    print(f"Correct outbox path: {correct_outbox}")
    
    # Temporär den korrekten Pfad setzen
    import config.paths_config
    config.paths_config._outbox_directory = str(correct_outbox)
    
    # CSV-Dateien finden
    csv_dir = repo_root / 'bl-input' / 'input_data'
    all_csvs = sorted([p for p in csv_dir.glob('*.csv')])
    
    # Bereits registrierte Dateien ermitteln
    files_tbl = (db.data.get('tables', {}).get('files', {}).get('records', []) or [])
    registered_input = {
        (r.get('file_name') or '') 
        for r in files_tbl 
        if (r.get('source_type') or '').lower() == 'input_data'
    }
    
    print(f'Found {len(all_csvs)} CSV files')
    print(f'Already registered: {len(registered_input)} files')
    
    # CSV-Dateien verarbeiten
    for csv_path in all_csvs:
        file_name = csv_path.name
        if file_name not in registered_input:
            print(f'Processing: {file_name}')
            try:
                stage0_path, results = service.ingest_csv_to_stage0(
                    csv_path, 
                    register_in_json_db=True, 
                    export_to_outbox=True
                )
                print(f'  → Stage0: {stage0_path}')
                print(f'  → Outbox: {results.get("outbox_path")}')
            except Exception as e:
                print(f'  ❌ Error processing {file_name}: {e}')
        else:
            print(f'Already registered: {file_name}')
            # Prüfe, ob Stage0-Datei existiert
            try:
                stage0_path, results = service.ingest_csv_to_stage0(
                    csv_path, 
                    register_in_json_db=False,  # Nicht erneut registrieren
                    export_to_outbox=True
                )
                print(f'  → Stage0: {stage0_path}')
                print(f'  → Outbox: {results.get("outbox_path")}')
            except Exception as e:
                print(f'  ⚠️ Could not reprocess {file_name}: {e}')
    
    # rawdata-Tabelle aktualisieren
    print('Updating rawdata table...')
    try:
        # Importiere Daten aus der Outbox in die rawdata-Tabelle
        records_added = db.import_from_outbox_stage0_union(replace=True)
        print(f'✅ Imported {records_added} records into rawdata table')
        # Normalisierung: Stage0→CSV-Verknüpfung und FK-Setzung
        try:
            link_res = db.link_stage0_parent_and_normalize_rawdata()
            print(f"🔗 Normalized rawdata.file_id to CSV parent: {link_res}")
        except Exception as e:
            print(f"⚠️ Normalization warning (rawdata.file_id): {e}")
        # Migration: Experiments/Rawdata → file_id, optional Entfernen alter id_files
        try:
            mig_res = db.migrate_files_to_fk(remove_id_files=True)
            print(f"🛠️ Migrated experiments/rawdata to file_id: {mig_res}")
        except Exception as e:
            print(f"⚠️ Migration warning (file_id): {e}")
        
        # Datenbank speichern
        if db.save():
            print('✅ Database saved successfully')
        else:
            print('⚠️ Warning: Database save failed')
            
        print('✅ Data ingestion completed!')
    except Exception as e:
        print(f'⚠️ Warning: Could not update rawdata table: {e}')
        print('✅ Data ingestion completed (without rawdata update)!')
    
except ImportError as e:
    print(f'❌ Import error: {e}')
    print('Make sure all required modules are available in the Python path.')
    sys.exit(1)
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
