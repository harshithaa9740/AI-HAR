"""
Unit and Integration Tests for AURAVISION Step 4: Supabase PostgreSQL Preparation.
Verifies dialect-safe database initialization, serializers, configuration, and migration assets.
"""
import os
import json
from pathlib import Path
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, inspect

from app.core.config import settings
from app.db.database import init_db, is_sqlite, engine
from app.db.serializers import (
    ensure_json_str,
    ensure_json_obj,
    format_utc_iso,
    parse_utc_datetime,
)


def test_01_supabase_settings_defaults():
    """Verify Supabase settings are present, defaulted, and safe for offline operation."""
    assert hasattr(settings, "SUPABASE_URL")
    assert hasattr(settings, "SUPABASE_ANON_KEY")
    assert hasattr(settings, "SUPABASE_SERVICE_ROLE_KEY")
    assert hasattr(settings, "SUPABASE_DB_URL")
    assert hasattr(settings, "SUPABASE_SYNC_ENABLED")
    assert hasattr(settings, "SUPABASE_STORAGE_BUCKET_RECORDINGS")
    assert hasattr(settings, "SUPABASE_STORAGE_BUCKET_ARTIFACTS")

    # Cloud sync MUST be disabled by default for offline edge operation
    assert settings.SUPABASE_SYNC_ENABLED is False
    assert settings.OFFLINE_ONLY is True
    assert "sqlite" in settings.DATABASE_URL.lower()


def test_02_dialect_portable_init_db(tmp_path):
    """Verify init_db initializes cleanly on a fresh engine using SQLAlchemy inspect."""
    test_db_file = tmp_path / "test_step4_auravision.db"
    test_engine = create_engine(f"sqlite:///{test_db_file}", connect_args={"check_same_thread": False})

    # Run idempotent initialization
    init_db(target_engine=test_engine)

    # Inspect tables created
    insp = inspect(test_engine)
    table_names = set(insp.get_table_names())
    
    expected_tables = {
        "experiments",
        "experiment_steps",
        "experiment_sessions",
        "detection_events",
        "sequence_events",
        "alert_events",
        "session_artifacts",
        "system_settings",
        "system_events",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"

    # Verify column migration was executed
    alert_cols = {c["name"] for c in insp.get_columns("alert_events")}
    assert "category" in alert_cols
    assert "validation_event_id" in alert_cols
    assert "acknowledged_at" in alert_cols

    # Re-running init_db should be idempotent without error
    init_db(target_engine=test_engine)
    test_engine.dispose()


def test_03_json_serialization_helpers():
    """Verify serializers handle both SQLite TEXT and PostgreSQL JSONB formats seamlessly."""
    # Test ensure_json_str
    assert ensure_json_str({"key": "val"}) == '{"key": "val"}'
    assert ensure_json_str(["item1", "item2"]) == '["item1", "item2"]'
    assert ensure_json_str('{"existing": true}') == '{"existing": true}'
    assert ensure_json_str(None, default="[]") == "[]"
    assert ensure_json_str("", default="{}") == "{}"

    # Test ensure_json_obj
    assert ensure_json_obj('{"a": 1, "b": 2}') == {"a": 1, "b": 2}
    assert ensure_json_obj({"already": "dict"}) == {"already": "dict"}
    assert ensure_json_obj('["sample", "container"]') == ["sample", "container"]
    assert ensure_json_obj(["already", "list"]) == ["already", "list"]
    assert ensure_json_obj(None, default={}) == {}
    assert ensure_json_obj("invalid json {{{", default={"fallback": True}) == {"fallback": True}


def test_04_timestamp_formatting_helpers():
    """Verify UTC ISO-8601 formatting for PostgreSQL TIMESTAMPTZ compatibility."""
    now_utc = datetime(2026, 9, 28, 12, 30, 45, tzinfo=timezone.utc)
    formatted = format_utc_iso(now_utc)
    assert "2026-09-28T12:30:45" in formatted

    # Test naive datetime gets treated as UTC
    naive_dt = datetime(2026, 9, 28, 12, 30, 45)
    formatted_naive = format_utc_iso(naive_dt)
    assert "2026-09-28T12:30:45" in formatted_naive

    # Test parse_utc_datetime
    parsed = parse_utc_datetime("2026-09-28T12:30:45Z")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.year == 2026
    assert parsed.month == 9

    # Test None handling
    assert format_utc_iso(None) is None
    assert parse_utc_datetime(None) is None
    assert parse_utc_datetime("invalid-date") is None


def test_05_supabase_sql_migration_file_exists():
    """Verify 001_initial_supabase_schema.sql exists and contains valid DDL definitions."""
    candidate_paths = [
        Path("backend/migrations/001_initial_supabase_schema.sql"),
        Path("migrations/001_initial_supabase_schema.sql"),
        Path(__file__).resolve().parent.parent / "migrations" / "001_initial_supabase_schema.sql"
    ]
    migration_file = next((p for p in candidate_paths if p.exists()), None)
    assert migration_file is not None, "Migration SQL file not found"
    
    content = migration_file.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS" in content
    assert "CREATE TABLE IF NOT EXISTS experiments" in content
    assert "CREATE TABLE IF NOT EXISTS experiment_steps" in content
    assert "CREATE TABLE IF NOT EXISTS experiment_sessions" in content
    assert "CREATE TABLE IF NOT EXISTS detection_events" in content
    assert "CREATE TABLE IF NOT EXISTS sequence_events" in content
    assert "CREATE TABLE IF NOT EXISTS alert_events" in content
    assert "CREATE TABLE IF NOT EXISTS session_artifacts" in content
    assert "CREATE TABLE IF NOT EXISTS system_settings" in content
    assert "CREATE TABLE IF NOT EXISTS system_events" in content
    assert "ENABLE ROW LEVEL SECURITY" in content
    assert "TIMESTAMPTZ" in content
    assert "JSONB" in content
    assert "GENERATED BY DEFAULT AS IDENTITY" in content


def test_06_migration_audit_script():
    """Verify migrate_sqlite_to_supabase.py runs and validates database integrity."""
    try:
        from backend.scripts.migrate_sqlite_to_supabase import audit_table_data, TABLE_MIGRATION_ORDER
    except ModuleNotFoundError:
        import sys
        backend_dir = Path(__file__).resolve().parent.parent
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from scripts.migrate_sqlite_to_supabase import audit_table_data, TABLE_MIGRATION_ORDER
    import sqlite3

    db_paths = [
        Path("backend/data/auravision.db"),
        Path("data/auravision.db"),
        Path(__file__).resolve().parent.parent / "data" / "auravision.db"
    ]
    db_path = next((p for p in db_paths if p.exists()), None)
    if db_path and db_path.exists():
        conn = sqlite3.connect(db_path)
        for tbl, _ in TABLE_MIGRATION_ORDER:
            info = audit_table_data(conn, tbl)
            assert info["row_count"] >= 0
            assert info["table"] == tbl
        conn.close()

