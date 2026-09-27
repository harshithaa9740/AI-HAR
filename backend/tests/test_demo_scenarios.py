"""
Integration Tests for SIH Demonstration Scenarios and Audit Logging
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.constants import DemoScenario, ValidationResult

client = TestClient(app)


def test_demo_scenarios_listing():
    res = client.get("/api/demo/scenarios")
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "DEMONSTRATION MODE"
    assert len(data["scenarios"]) >= 5
    scenario_names = [s["name"] for s in data["scenarios"]]
    assert "NORMAL" in scenario_names
    assert "SKIPPED_STEP" in scenario_names
    assert "OUT_OF_SEQUENCE" in scenario_names
    assert "LOW_CONFIDENCE" in scenario_names
    assert "UNKNOWN_ACTION" in scenario_names or "UNKNOWN_OBJECT" in scenario_names



def test_skipped_step_demo_scenario_workflow():
    # 1. Start Session
    exp_res = client.get("/api/experiments")
    sample_exp = next(e for e in exp_res.json() if e["name"] in ("Sample Astronaut Experiment", "Sample Handling Experiment"))
    exp_id = sample_exp["id"]
    code = f"DEMO-SKIP-{uuid.uuid4().hex[:6]}"
    sess_res = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": code})
    assert sess_res.status_code == 201
    session_id = sess_res.json()["id"]

    # 2. Step 1: PICK_TOOL (VALID)
    r1 = client.post("/api/validate", json={"session_id": session_id, "action_code": "PICK_TOOL", "confidence": 0.95, "observed_objects": ["tool"]})
    assert r1.json()["result"] == "VALID"
    assert r1.json()["completed_step"] == 1

    # 3. Step 2: OPEN_CONTAINER (VALID)
    r2 = client.post("/api/validate", json={"session_id": session_id, "action_code": "OPEN_CONTAINER", "confidence": 0.93, "observed_objects": ["container"]})
    assert r2.json()["result"] == "VALID"
    assert r2.json()["completed_step"] == 2

    # 4. Skip Step 3 and do Step 4: PLACE_SAMPLE (STEP_SKIPPED)
    r4 = client.post("/api/validate", json={"session_id": session_id, "action_code": "PLACE_SAMPLE", "confidence": 0.91, "observed_objects": ["sample", "container"]})
    assert r4.json()["result"] == "STEP_SKIPPED"
    assert r4.json()["expected_step"] == 3
    assert r4.json()["observed_step"] == 4

    # 5. Check generated Alerts
    alerts_res = client.get(f"/api/sessions/{session_id}/alerts")
    assert alerts_res.status_code == 200
    alert_types = [a["alert_type"] for a in alerts_res.json()]
    assert "STEP_SKIPPED" in alert_types

    # 6. Check JSONL and TXT Logs
    log_txt_res = client.get(f"/api/sessions/{session_id}/log?format=txt")
    assert log_txt_res.status_code == 200
    assert "STEP_SKIPPED" in log_txt_res.json()["content"]

    log_jsonl_res = client.get(f"/api/sessions/{session_id}/log?format=jsonl")
    assert log_jsonl_res.status_code == 200
    assert "STEP_SKIPPED" in log_jsonl_res.json()["content"]


def test_out_of_sequence_scenario_workflow():
    exp_res = client.get("/api/experiments")
    sample_exp = next(e for e in exp_res.json() if e["name"] in ("Sample Astronaut Experiment", "Sample Handling Experiment"))
    exp_id = sample_exp["id"]
    code = f"DEMO-OOS-{uuid.uuid4().hex[:6]}"
    sess_res = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": code})
    session_id = sess_res.json()["id"]

    # Step 1 & Step 2
    client.post("/api/validate", json={"session_id": session_id, "action_code": "PICK_TOOL", "confidence": 0.95, "observed_objects": ["tool"]})
    client.post("/api/validate", json={"session_id": session_id, "action_code": "OPEN_CONTAINER", "confidence": 0.93, "observed_objects": ["container"]})

    # When Step 3 is expected (TAKE_SAMPLE), observing Step 1 (PICK_TOOL) is OUT_OF_SEQUENCE
    r_oos = client.post("/api/validate", json={"session_id": session_id, "action_code": "PICK_TOOL", "confidence": 0.95, "observed_objects": ["tool"]})
    assert r_oos.json()["result"] == "OUT_OF_SEQUENCE"


def test_low_confidence_scenario_workflow():
    exp_res = client.get("/api/experiments")
    sample_exp = next(e for e in exp_res.json() if e["name"] in ("Sample Astronaut Experiment", "Sample Handling Experiment"))
    exp_id = sample_exp["id"]
    code = f"DEMO-LOWCONF-{uuid.uuid4().hex[:6]}"
    sess_res = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": code})
    session_id = sess_res.json()["id"]

    # Step 1 (VALID)
    client.post("/api/validate", json={"session_id": session_id, "action_code": "PICK_TOOL", "confidence": 0.95, "observed_objects": ["tool"]})

    # Step 2 with confidence 0.45 (< 0.70 threshold)
    r_low = client.post("/api/validate", json={"session_id": session_id, "action_code": "OPEN_CONTAINER", "confidence": 0.45, "observed_objects": ["container"]})
    assert r_low.json()["result"] == "VERIFY_REQUIRED"
