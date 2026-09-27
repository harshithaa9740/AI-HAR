"""
Integration Tests for AURAVISION REST API Endpoints
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["offline_mode"] is True
    assert "app_version" in data


def test_system_status_endpoint():
    response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["offline_mode"] is True
    assert data["database_connected"] is True
    assert "ai_mode" in data
    assert "confidence_threshold" in data


def test_list_and_create_experiment():
    # 1. List experiments (seeded default should be present)
    response = client.get("/api/experiments")
    assert response.status_code == 200
    experiments = response.json()
    assert len(experiments) >= 1
    assert any(e["name"] in ("Sample Astronaut Experiment", "Sample Handling Experiment") for e in experiments)

    # 2. Create custom experiment
    import uuid
    exp_name = f"Custom Protocol {uuid.uuid4().hex[:6]}"
    payload = {
        "name": exp_name,
        "description": "Geological spectral scanning procedure",
        "version": "1.2.0",
        "steps": [
            {
                "step_number": 1,
                "action_code": "ALIGN_SPECTROMETER",
                "display_name": "Align Spectrometer",
                "expected_objects": ["spectrometer"]
            },
            {
                "step_number": 2,
                "action_code": "ACTIVATE_BEAM",
                "display_name": "Activate Beam",
                "expected_objects": ["spectrometer", "sample"]
            }
        ]
    }
    create_res = client.post("/api/experiments", json=payload)
    assert create_res.status_code == 201
    created_exp = create_res.json()
    assert created_exp["name"] == payload["name"]
    assert len(created_exp["steps"]) == 2

    # 3. Get experiment by ID
    get_res = client.get(f"/api/experiments/{created_exp['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == created_exp["id"]


def test_session_lifecycle_and_validation():
    # 1. Get default experiment
    exp_res = client.get("/api/experiments")
    sample_exp = next(e for e in exp_res.json() if e["name"] in ("Sample Astronaut Experiment", "Sample Handling Experiment"))
    exp_id = sample_exp["id"]

    # 2. Start session
    import uuid
    sess_code = f"TEST-SESSION-{uuid.uuid4().hex[:6]}"
    start_res = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": sess_code})
    assert start_res.status_code == 201
    session = start_res.json()
    session_id = session["id"]
    assert session["status"] in ("ACTIVE", "RUNNING")

    # 3. Validate Step 1 (PICK_TOOL)
    val1 = client.post("/api/validate", json={
        "session_id": session_id,
        "action_code": "PICK_TOOL",
        "confidence": 0.95,
        "observed_objects": ["tool"]
    })
    assert val1.status_code == 200
    res1_data = val1.json()
    assert res1_data["result"] == "VALID"
    assert res1_data["completed_step"] == 1
    assert res1_data["next_step"] == 2

    # 4. Check Alerts endpoint
    alerts_res = client.get(f"/api/sessions/{session_id}/alerts")
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert len(alerts) >= 1

    # 5. Check Log endpoint
    log_res = client.get(f"/api/sessions/{session_id}/log?format=txt")
    assert log_res.status_code == 200
    log_data = log_res.json()
    assert "STEP_01" in log_data["content"]
    assert "PICK_TOOL" in log_data["content"]

    # 6. Stop session
    stop_res = client.post(f"/api/sessions/{session_id}/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] in ("COMPLETED", "STOPPED")


def test_models_status_endpoint():
    response = client.get("/api/models/status")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) >= 3


def test_settings_get_and_update():
    # GET settings
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200
    settings_data = get_res.json()
    assert settings_data["offline_only"] is True

    # POST settings update
    update_res = client.post("/api/settings", json={
        "confidence_threshold": 0.75,
        "log_level": "INFO"
    })
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["settings"]["confidence_threshold"] == 0.75
