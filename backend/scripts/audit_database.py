"""
AURAVISION Database Audit Script
Inspects SQLite engine version, tables, columns, types, keys, constraints, and indexes.
"""
import sqlite3
import json
from pathlib import Path

db_path = Path(__file__).resolve().parent.parent / "data" / "auravision.db"
if not db_path.exists():
    db_path = Path("backend/data/auravision.db")
if not db_path.exists():
    db_path = Path("data/auravision.db")

if not db_path.exists():
    print(f"Error: {db_path} does not exist.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"=== AURAVISION LOCAL DATABASE AUDIT ===")
print(f"Database Path: {db_path.resolve()}")
print(f"SQLite Version: {sqlite3.sqlite_version}")

cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
tables = cursor.fetchall()
print(f"Total Tables: {len(tables)}\n")

for table_name, create_sql in tables:
    print(f"==================================================")
    print(f"TABLE: {table_name}")
    print(f"==================================================")
    
    # Row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    count = cursor.fetchone()[0]
    print(f"Row count: {count}")
    
    # Columns
    cursor.execute(f"PRAGMA table_info({table_name});")
    cols = cursor.fetchall()
    print("\nColumns:")
    for col in cols:
        cid, name, col_type, notnull, dflt_value, pk = col
        pk_str = f" [PK, pos={pk}]" if pk else ""
        nn_str = " NOT NULL" if notnull else " NULL"
        df_str = f" DEFAULT {dflt_value}" if dflt_value is not None else ""
        print(f"  - {name}: {col_type}{nn_str}{df_str}{pk_str}")
        
    # Foreign Keys
    cursor.execute(f"PRAGMA foreign_key_list({table_name});")
    fks = cursor.fetchall()
    if fks:
        print("\nForeign Keys:")
        for fk in fks:
            fkid, seq, to_table, from_col, to_col, on_upd, on_del, match = fk
            print(f"  - {from_col} -> {to_table}({to_col}) ON UPDATE {on_upd} ON DELETE {on_del}")
    else:
        print("\nForeign Keys: None")
        
    # Indexes
    cursor.execute(f"PRAGMA index_list({table_name});")
    idxs = cursor.fetchall()
    if idxs:
        print("\nIndexes:")
        for idx in idxs:
            seq, idx_name, unique, origin, partial = idx
            cursor.execute(f"PRAGMA index_info({idx_name});")
            idx_cols = [c[2] for c in cursor.fetchall()]
            u_str = "UNIQUE " if unique else ""
            print(f"  - {idx_name}: {u_str}({', '.join(idx_cols)}) [origin: {origin}]")
    else:
        print("\nIndexes: None")
    print()

conn.close()
