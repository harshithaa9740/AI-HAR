"""
Unit and Integration Tests for AURAVISION Step 5: Supabase PostgreSQL Integration & Mode Selection.
Verifies environment-based DB selection, failure handling, credential masking, offline resilience, and SQLite functionality.
"""
import os
import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import Settings, settings, DATA_DIR
from app.db.database import get_db, SessionLocal, normalize_db_url_and_args, normalize_db_url
from app.db import models, repository
from app.main import app

client = TestClient(app)


def test_01_default_database_selection_sqlite():
    """Verify that default settings select SQLite and maintain 100% offline guarantee."""
    test_settings = Settings()
    assert test_settings.DB_ENGINE == "sqlite"
    assert test_settings.OFFLINE_ONLY is True
    assert "sqlite" in test_settings.DATABASE_URL.lower()
    assert str(DATA_DIR) in test_settings.DATABASE_URL or "auravision.db" in test_settings.DATABASE_URL


def test_02_explicit_postgres_missing_credentials_raises_error():
    """
    Verify that selecting PostgreSQL/Supabase without supplying SUPABASE_DB_URL
    fails loudly with a descriptive error instead of silently falling back to SQLite.
    """
    with pytest.raises(ValueError) as excinfo:
        Settings(DB_ENGINE="postgres", SUPABASE_DB_URL=None, DATABASE_URL=None)
    
    err_msg = str(excinfo.value)
    assert "PostgreSQL/Supabase engine is explicitly selected" in err_msg
    assert "SUPABASE_DB_URL" in err_msg


def test_03_credential_masking_in_health_and_status():
    """Verify that database passwords are never exposed in logs, settings, or API health endpoints."""
    # Test property masking
    s = Settings(
        DB_ENGINE="postgres",
        SUPABASE_DB_URL="postgresql://postgres:SuperSecretPassword123@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    masked = s.sanitized_database_url
    assert "SuperSecretPassword123" not in masked
    assert "postgres:***@" in masked

    # Test /api/health endpoint
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "database_path" in data
    assert "SuperSecretPassword123" not in data["database_path"]

    # Test /api/system/status endpoint
    res_sys = client.get("/api/system/status")
    assert res_sys.status_code == 200
    sys_data = res_sys.json()
    assert "database_path" in sys_data
    assert "SuperSecretPassword123" not in sys_data["database_path"]


def test_04_normalize_db_url_and_args():
    """Verify PostgreSQL URL driver normalization for pg8000 and SSL arguments."""
    # SQLite URL
    sqlite_url, sqlite_args = normalize_db_url_and_args("sqlite:///./data/test.db")
    assert "sqlite" in sqlite_url
    assert sqlite_args.get("check_same_thread") is False

    # PostgreSQL generic URL
    raw_pg = "postgresql://user:pass@db.supabase.co:5432/postgres?sslmode=require"
    norm_pg, pg_args = normalize_db_url_and_args(raw_pg)
    assert "postgresql+pg8000://" in norm_pg or "postgresql+psycopg2://" in norm_pg
    assert "ssl_context" in pg_args or "sslmode" in pg_args


def test_05_sqlite_workflow_fully_functional():
    """
    Verify complete AURAVISION workflow operates successfully on the active database:
    - Protocol retrieval
    - Session lifecycle
    - Detections, sequence events, alerts, and artifacts persistence
    """
    db = SessionLocal()
    test_uuid = f"TEST-STEP5-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        # 1. Retrieve or create protocol
        exp = repository.get_experiment_by_name(db, "Biological Air Sampler (BAS) Validation")
        if not exp:
            exp = repository.create_experiment(
                db, name=f"Test-Exp-{test_uuid}", description="Isolated Step 5 test protocol"
            )
            step = repository.create_step(
                db, experiment_id=exp.id, step_number=1, step_code="STEP-01",
                name="Sterilize Chamber", expected_action="STERILIZE_CHAMBER",
                required_objects=["sterilizer"]
            )
        assert exp is not None
        steps = repository.get_steps_for_experiment(db, exp.id)
        assert len(steps) > 0

        # 2. Create isolated session
        session = repository.create_session(
            db, experiment_id=exp.id, session_name=f"Step 5 Test Session {test_uuid}",
            operator_label="Astronaut Specialist"
        )
        assert session.id is not None
        assert session.status == "CREATED"

        # Update session status
        session = repository.update_session(db, session.id, status="RUNNING")
        assert session.status == "RUNNING"

        # 3. Persist detection event
        det = repository.create_detection_event(
            db, session_id=session.id, protocol_step_id=steps[0].id,
            entity_type="ACTION", entity_name="STERILIZE_CHAMBER",
            confidence=0.92, source="camera_0", metadata={"step": 1}
        )
        assert det.id is not None
        assert det.session_id == session.id

        # 4. Persist sequence event
        seq = repository.create_sequence_event(
            db, session_id=session.id, protocol_step_id=steps[0].id,
            expected_step_number=1, expected_step_code="STEP-01",
            observed_step_number=1, observed_step_code="STEP-01",
            result="VALID", confidence=0.92, message="Nominal sterilization observed"
        )
        assert seq.id is not None

        # 5. Persist alert event linked to validation event
        alert = repository.create_alert_event(
            db, session_id=session.id, validation_event_id=seq.id,
            alert_type="STEP_VALIDATED", severity="INFO",
            message="Step 1 completed nominally", category="protocol"
        )
        assert alert.id is not None
        assert alert.acknowledged is False

        # Acknowledge alert
        ack_alert = repository.acknowledge_alert(db, alert.id)
        assert ack_alert.acknowledged is True
        assert ack_alert.acknowledged_at is not None

        # 6. Persist artifact reference
        art = repository.create_artifact(
            db, session_id=session.id, artifact_type="recording",
            file_path="data/recordings/test_rec.mp4", file_name="test_rec.mp4",
            mime_type="video/mp4", file_size_bytes=1048576
        )
        assert art.id is not None

        # 7. Verify session history retrieval
        dets = repository.get_session_detection_events(db, session.id)
        seqs = repository.get_session_sequence_events(db, session.id)
        alerts = repository.get_session_alert_events(db, session.id)
        arts = repository.get_session_artifacts(db, session.id)

        assert len(dets) == 1
        assert len(seqs) == 1
        assert len(alerts) == 1
        assert len(arts) == 1

        # Clean up isolated test session
        db.delete(session)
        db.commit()

    finally:
        db.close()


def test_06_connection_verifier_output():
    """Verify test_supabase_connection.py runs without crash and reports live configuration status."""
    try:
        from scripts.test_supabase_connection import run_connection_check
    except ImportError:
        from backend.scripts.test_supabase_connection import run_connection_check

    result = run_connection_check(target_url=None)
    assert isinstance(result, dict)
    assert "configured" in result
    assert "schema_applied" in result
    assert "message" in result
