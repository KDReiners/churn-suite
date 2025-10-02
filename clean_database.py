#!/usr/bin/env python3
"""
Database Cleaner für Churn Suite
Löscht alle Einträge in allen Tabellen der JSON-Datenbank
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

try:
from bl.json_database.churn_json_database import ChurnJSONDatabase
    
    drop_views = ("--drop-views" in sys.argv) or (os.environ.get("CLEANDB_DROP_VIEWS") in ("1","true","True","yes","YES"))
    print("⚠️  WARNING: This will delete ALL data in the database!")
    print("Clearing all tables in the JSON database...")
    print("=" * 50)
    
    # Datenbank laden
    db = ChurnJSONDatabase()
    
    # Alle Tabellen durchgehen
    tables = db.data.get('tables', {})
    total_records = 0
    
    print("=== CLEARING DATABASE ===")
    if not drop_views:
        print("(Views werden NICHT gelöscht. Mit --drop-views oder CLEANDB_DROP_VIEWS=1 löschen.)")
    for table_name, table_data in tables.items():
        if not drop_views and table_name == "views":
            # Views behalten (logische Views)
            print(f"Skipping {table_name}: preserve logical views (records={len(table_data.get('records', []))})")
            continue
        records = table_data.get('records', [])
        record_count = len(records)
        total_records += record_count
        print(f"Clearing {table_name}: {record_count} records")
        table_data['records'] = []
    
    print(f"\nTotal records cleared: {total_records}")
    
    # Datenbank speichern
    if db.save():
        print("✅ Database cleared and saved successfully")
    else:
        print("❌ Error saving cleared database")
    
    print("\n⚠️  Database is now empty (ohne Views)!")
    print("Run 'make ingest' to reload data from CSV files.")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure all required modules are available in the Python path.")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
