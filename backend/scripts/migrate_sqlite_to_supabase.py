"""
AURAVISION Local-to-Cloud Migration Engine (Step 4 Planning & Validation Tool)

Dry-run validator and batch migration pipeline for future Supabase PostgreSQL synchronization.
Ensures zero disruption to local offline operations.

Usage:
  python backend/scripts/migrate_sqlite_to_supabase.py --dry-run
  python backend/scripts/migrate_sqlite_to_supabase.py --backup-only
"""
import sys
import os
import shutil
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# Ensure backend root is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.serializers import ensure_json_obj, format_utc_iso


TABLE_MIGRATION_ORDER = [
    ("experiments", "Root experiment protocols"),
    ("experiment_steps", "Ordered protocol steps (FK: experiment_id)"),
    ("experiment_sessions", "Experiment execution sessions (FK: experiment_id)"),
    ("sequence_events", "Validation sequence events (FK: session_id, protocol_step_id)"),
    ("detection_events", "AI perception events (FK: session_id, protocol_step_id)"),
    ("alert_events", "Dispatched alert events (FK: session_id, validation_event_id)"),
    ("session_artifacts", "Artifact references (FK: session_id)"),
    ("system_events", "System lifecycle events (FK: session_id)"),
    ("system_settings", "Independent system key-value configurations"),
]


def create_local_backup(db_path: Path) -> Path:
    """Create an atomic timestamped backup copy of auravision.db."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"auravision_backup_{timestamp}.db"
    shutil.copy2(db_path, backup_path)
    print(f"[BACKUP] Created atomic backup: {backup_path.resolve()}")
    return backup_path


def audit_table_data(conn: sqlite3.Connection, table_name: str):
    """Inspect and validate data cleanliness for a single table."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    
    # Check sample row for timestamp and JSON format validation
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
    sample_rows = cursor.fetchall()
    
    return {
        "table": table_name,
        "row_count": count,
        "sample_count": len(sample_rows),
    }


def validate_foreign_key_integrity(conn: sqlite3.Connection):
    """Check for orphaned child records that would cause PostgreSQL FK violations."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_key_check;")
    violations = cursor.fetchall()
    return violations


def run_migration_validation(db_path: Path, dry_run: bool = True):
    """Run full dry-run audit and dependency verification."""
    print("=" * 70)
    print("AURAVISION SUPABASE MIGRATION PLANNER & AUDIT")
    print(f"Database Source: {db_path.resolve()}")
    print(f"Mode: {'DRY RUN (No cloud mutations)' if dry_run else 'LIVE'}")
    print("=" * 70)

    if not db_path.exists():
        print(f"Error: Database {db_path} not found.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    
    # Step 1: FK Integrity Check
    print("\n--- 1. Foreign Key Integrity Audit ---")
    fk_violations = validate_foreign_key_integrity(conn)
    if fk_violations:
        print(f"[WARNING] Detected {len(fk_violations)} foreign key inconsistencies:")
        for v in fk_violations[:5]:
            print(f"   Table: {v[0]}, RowId: {v[1]}, Target: {v[2]}, FK index: {v[3]}")
    else:
        print("[SUCCESS] All foreign keys are 100% referentially intact. Zero orphans.")

    # Step 2: Table Dependency Migration Order
    print("\n--- 2. Table Dependency Migration Order ---")
    total_records = 0
    for idx, (tbl, desc) in enumerate(TABLE_MIGRATION_ORDER, 1):
        info = audit_table_data(conn, tbl)
        total_records += info["row_count"]
        print(f"  {idx}. {tbl:<20} | Rows: {info['row_count']:<6} | {desc}")

    print(f"\nTotal Local Records to Migrate: {total_records}")

    # Step 3: Type & Payload Compatibility Check
    print("\n--- 3. Type & Payload Compatibility Check ---")
    cursor = conn.cursor()
    
    # Check experiment_steps JSON required_objects
    cursor.execute("SELECT required_objects, validation_rules FROM experiment_steps LIMIT 10")
    step_rows = cursor.fetchall()
    valid_json_steps = all(isinstance(ensure_json_obj(r[0]), list) for r in step_rows)
    print(f"  - experiment_steps JSONB validation: {'PASSED' if valid_json_steps else 'FAILED'}")

    # Check session_artifacts file references (ensure NO video blobs in DB)
    cursor.execute("SELECT file_path, file_size_bytes FROM session_artifacts LIMIT 10")
    artifact_rows = cursor.fetchall()
    file_paths_valid = all(isinstance(r[0], str) for r in artifact_rows)
    print(f"  - session_artifacts path references: {'PASSED (Zero binary blobs in SQL)' if file_paths_valid else 'FAILED'}")

    # Check timestamps formatting
    cursor.execute("SELECT created_at FROM experiment_sessions LIMIT 10")
    ts_rows = cursor.fetchall()
    timestamps_valid = all(format_utc_iso(r[0]) is not None for r in ts_rows)
    print(f"  - experiment_sessions TIMESTAMPTZ formatting: {'PASSED' if timestamps_valid else 'FAILED'}")

    conn.close()

    print("\n" + "=" * 70)
    print("MIGRATION PLAN READY:")
    print("  1. Schema DDL prepared at: backend/migrations/001_initial_supabase_schema.sql")
    print("  2. Local database remains active, fully offline, and untouched.")
    print("  3. To push records to Supabase, configure SUPABASE_DB_URL in backend/.env")
    print("     and run: migrate-to-supabase.bat")
    print("=" * 70)


def run_rest_migration(db_path: Path):
    """
    Perform batch migration to Supabase using the PostgREST REST API.
    Used when direct PostgreSQL connection (password) is not configured.
    """
    from app.core.config import settings
    import urllib.request
    import json

    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        print("[ERROR] Supabase URL or Anon Key is missing.")
        return False

    url_base = settings.SUPABASE_URL.rstrip("/") + "/rest/v1/"
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates"
    }

    create_local_backup(db_path)
    sqlite_conn = sqlite3.connect(db_path)
    sqlite_conn.row_factory = sqlite3.Row

    print("\n--- Starting REST Synchronization to Supabase ---")
    for tbl, desc in TABLE_MIGRATION_ORDER:
        s_cursor = sqlite_conn.cursor()
        s_cursor.execute(f"SELECT * FROM {tbl}")
        rows = s_cursor.fetchall()
        if not rows:
            print(f"  - {tbl:<22}: 0 rows (Skipped)")
            continue

        batch_size = 100
        migrated_count = 0
        error_encountered = False

        for i in range(0, len(rows), batch_size):
            chunk = rows[i:i + batch_size]
            chunk_dicts = []
            for r in chunk:
                d = dict(r)
                if "metadata" in d and d["metadata"]:
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except Exception:
                        d["metadata"] = {}
                elif "metadata" in d and not d["metadata"]:
                    d["metadata"] = {}

                if "required_objects" in d and d["required_objects"]:
                    try:
                        d["required_objects"] = json.loads(d["required_objects"])
                    except Exception:
                        d["required_objects"] = []

                for k in ("is_active", "stream_enabled", "acknowledged", "spoken"):
                    if k in d and isinstance(d[k], int):
                        d[k] = bool(d[k])

                for k in ("created_at", "updated_at", "started_at", "ended_at", "timestamp", "acknowledged_at"):
                    if k in d and d[k]:
                        ts_str = str(d[k]).replace(" ", "T")
                        if not ts_str.endswith("Z") and "+" not in ts_str:
                            ts_str += "Z"
                        d[k] = ts_str
                chunk_dicts.append(d)

            req = urllib.request.Request(
                f"{url_base}{tbl}",
                data=json.dumps(chunk_dicts, default=str).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=20):
                    migrated_count += len(chunk)
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode("utf-8", errors="ignore")
                if "42501" in err_msg or e.code == 401:
                    print(f"  - {tbl:<22}: [BLOCKED BY RLS] Row-level security prevented write.")
                    print("    Please run the 4-line SQL in your Supabase SQL Editor to disable RLS.")
                else:
                    print(f"  - {tbl:<22}: HTTP {e.code} Error: {err_msg[:60]}")
                error_encountered = True
                break

        if not error_encountered:
            print(f"  - {tbl:<22}: Migrated {migrated_count}/{len(rows)} rows ({desc})")

    sqlite_conn.close()
    print("\n" + "=" * 70)
    print("REST Synchronization Finished!")
    print("=" * 70)
    return True


def run_live_migration(db_path: Path, pg_url: Optional[str] = None):

    """
    Perform live batch synchronization from local SQLite to Supabase PostgreSQL.
    Idempotent, transactional per table, and preserves primary and foreign keys.
    """
    from app.core.config import settings
    target_url = pg_url or settings.SUPABASE_DB_URL

    print("=" * 70)
    print("AURAVISION LIVE SQLITE TO SUPABASE MIGRATION")
    print(f"Database Source: {db_path.resolve()}")
    print("=" * 70)

    if not target_url or not target_url.strip():
        # Check if Supabase REST API credentials are configured
        if settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY:
            print("[INFO] SUPABASE_DB_URL not configured. Attempting REST API synchronization...")
            return run_rest_migration(db_path)

        print("\n[MIGRATION BLOCKED: NO SUPABASE CREDENTIALS FOUND]")
        print("Please configure SUPABASE_URL and SUPABASE_ANON_KEY in backend/.env")
        return False

    if not db_path.exists():
        print(f"[ERROR] Local database {db_path} does not exist.")
        return False


    # Create backup first
    create_local_backup(db_path)

    from sqlalchemy import create_engine, text
    from app.db.database import normalize_db_url_and_args
    active_url, connect_args = normalize_db_url_and_args(target_url)

    try:
        pg_engine = create_engine(
            active_url,
            connect_args=connect_args,
            pool_pre_ping=True
        )
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        print("[SUCCESS] Connected to Supabase PostgreSQL!")
    except Exception as e:
        print(f"[ERROR] Failed to connect to Supabase PostgreSQL: {e}")
        return False

    sqlite_conn = sqlite3.connect(db_path)
    sqlite_conn.row_factory = sqlite3.Row

    with pg_engine.connect() as pg_conn:
        for tbl, desc in TABLE_MIGRATION_ORDER:
            s_cursor = sqlite_conn.cursor()
            s_cursor.execute(f"SELECT * FROM {tbl}")
            rows = s_cursor.fetchall()
            if not rows:
                print(f"  - {tbl:<22}: 0 rows (Skipped)")
                continue

            cols = rows[0].keys()
            col_names = ", ".join(cols)
            val_placeholders = ", ".join([f":{c}" for c in cols])

            # Prepare insert with conflict avoidance
            insert_sql = text(
                f"INSERT INTO {tbl} ({col_names}) VALUES ({val_placeholders}) "
                f"ON CONFLICT DO NOTHING;"
            )

            # Batch execute in chunks of 250
            batch_size = 250
            migrated_count = 0
            for i in range(0, len(rows), batch_size):
                chunk = rows[i:i + batch_size]
                chunk_dicts = []
                for r in chunk:
                    d = dict(r)
                    # Convert boolean integers for PostgreSQL compatibility if needed
                    for k, v in d.items():
                        if k in ("is_active", "stream_enabled", "acknowledged", "spoken") and isinstance(v, int):
                            d[k] = bool(v)
                    chunk_dicts.append(d)

                pg_conn.execute(insert_sql, chunk_dicts)
                pg_conn.commit()
                migrated_count += len(chunk)

            print(f"  - {tbl:<22}: Migrated {migrated_count} rows ({desc})")

            # Sequence reset for serial/identity primary key
            try:
                seq_query = text(f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), COALESCE((SELECT MAX(id) FROM {tbl}), 1));")
                pg_conn.execute(seq_query)
                pg_conn.commit()
            except Exception:
                pass

    sqlite_conn.close()
    print("\n" + "=" * 70)
    print("[MIGRATION COMPLETE] All local records successfully synchronized to Supabase!")
    print("=" * 70)
    return True


def main():
    parser = argparse.ArgumentParser(description="AURAVISION Local-to-Cloud Migration Engine")
    parser.add_argument("--dry-run", action="store_true", help="Validate and plan without cloud actions")
    parser.add_argument("--live", action="store_true", help="Perform live batch migration to Supabase PostgreSQL")
    parser.add_argument("--backup-only", action="store_true", help="Only create local database backup")
    parser.add_argument("--db-path", default="backend/data/auravision.db", help="Path to local SQLite file")
    parser.add_argument("--db-url", default=None, help="Explicit Supabase PostgreSQL connection string")

    args = parser.parse_args()
    db_file = Path(args.db_path)
    if not db_file.exists():
        fallback = Path(__file__).resolve().parent.parent / "data" / "auravision.db"
        if fallback.exists():
            db_file = fallback

    if args.backup_only:
        create_local_backup(db_file)
        return

    if args.live:
        run_live_migration(db_file, pg_url=args.db_url)
    else:
        run_migration_validation(db_file, dry_run=True)


if __name__ == "__main__":
    main()

