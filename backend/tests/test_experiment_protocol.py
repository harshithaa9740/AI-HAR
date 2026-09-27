"""
Integration and Unit Tests for AURAVISION Experiment Protocol Layer
Covers all 17 mandatory test cases specified in STEP 3.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal, Base, engine
from app.db import models
from app.services.experiment_service import experiment_service, ProtocolValidationError
from app.schemas.experiment import ExperimentCreate, ExperimentStepCreate

client = TestClient(app)


def unique_name(prefix: str = "Exp") -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"


# =====================================================================
# TEST 1: Create a valid experiment.
# =====================================================================
def test_1_create_valid_experiment():
    name = unique_name("Valid Single Step")
    payload = {
        "name": name,
        "description": "Valid single-step astronaut protocol",
        "version": "1.0",
        "is_active": True,
        "steps": [
            {
                "step_number": 1,
                "step_code": "STEP_01",
                "name": "Pick Tool",
                "expected_action": "PICK_TOOL",
                "required_objects": ["tool"],
                "confidence_threshold": 0.70
            }
        ]
    }
    res = client.post("/api/experiments", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == name
    assert data["version"] == "1.0"
    assert data["is_active"] is True
    assert len(data["steps"]) == 1
    assert data["steps"][0]["step_code"] == "STEP_01"


# =====================================================================
# TEST 2: Create an experiment with multiple ordered steps.
# =====================================================================
def test_2_create_experiment_with_multiple_ordered_steps():
    name = unique_name("Multi-Step Protocol")
    payload = {
        "name": name,
        "description": "Multi-step payload operation",
        "version": "1.1",
        "is_active": True,
        "steps": [
            {
                "step_number": 1,
                "step_code": "STEP_01",
                "name": "Pick Tool",
                "expected_action": "PICK_TOOL",
                "required_objects": ["tool"],
                "confidence_threshold": 0.75
            },
            {
                "step_number": 2,
                "step_code": "STEP_02",
                "name": "Open Container",
                "expected_action": "OPEN_CONTAINER",
                "required_objects": ["container"],
                "confidence_threshold": 0.70
            },
            {
                "step_number": 3,
                "step_code": "STEP_03",
                "name": "Take Sample",
                "expected_action": "TAKE_SAMPLE",
                "required_objects": ["sample"],
                "confidence_threshold": 0.80
            }
        ]
    }
    res = client.post("/api/experiments", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert len(data["steps"]) == 3
    assert [s["step_number"] for s in data["steps"]] == [1, 2, 3]


# =====================================================================
# TEST 3: Retrieve experiment and confirm steps are ordered.
# =====================================================================
def test_3_retrieve_experiment_and_confirm_steps_ordered():
    name = unique_name("Step Order Verification")
    payload = {
        "name": name,
        "steps": [
            {"step_number": 1, "step_code": "STEP_01", "name": "One", "expected_action": "ACT_1"},
            {"step_number": 2, "step_code": "STEP_02", "name": "Two", "expected_action": "ACT_2"},
            {"step_number": 3, "step_code": "STEP_03", "name": "Three", "expected_action": "ACT_3"}
        ]
    }
    create_res = client.post("/api/experiments", json=payload)
    assert create_res.status_code == 201
    exp_id = create_res.json()["id"]

    # Retrieve experiment
    get_res = client.get(f"/api/experiments/{exp_id}")
    assert get_res.status_code == 200
    steps = get_res.json()["steps"]
    assert [s["step_number"] for s in steps] == [1, 2, 3]

    # Retrieve steps sub-resource
    steps_res = client.get(f"/api/experiments/{exp_id}/steps")
    assert steps_res.status_code == 200
    sub_steps = steps_res.json()
    assert [s["step_number"] for s in sub_steps] == [1, 2, 3]


# =====================================================================
# TEST 4: Reject an experiment with no steps.
# =====================================================================
def test_4_reject_experiment_with_no_steps():
    name = unique_name("No Steps Protocol")
    payload = {
        "name": name,
        "description": "Invalid empty protocol",
        "steps": []
    }
    res = client.post("/api/experiments", json=payload)
    assert res.status_code == 400
    errors = res.json()["detail"]["errors"]
    assert any("at least one step" in err.lower() for err in errors)


# =====================================================================
# TEST 5: Reject duplicate step numbers.
# =====================================================================
def test_5_reject_duplicate_step_numbers():
    name = unique_name("Duplicate Step Number")
    payload = {
        "name": name,
        "steps": [
            {"step_number": 1, "step_code": "STEP_01", "name": "Step 1A", "expected_action": "ACT_1"},
            {"step_number": 1, "step_code": "STEP_02", "name": "Step 1B", "expected_action": "ACT_2"}
        ]
    }
    res = client.post("/api/experiments", json=payload)
    assert res.status_code == 400
    errors = res.json()["detail"]["errors"]
    assert any("duplicate step_number" in err.lower() for err in errors)


# =====================================================================
# TEST 6: Reject non-sequential step numbers.
# =====================================================================
def test_6_reject_non_sequential_step_numbers():
    name = unique_name("Non Sequential Steps")
    payload = {
        "name": name,
        "steps": [
            {"step_number": 1, "step_code": "STEP_01", "name": "Step 1", "expected_action": "ACT_1"},
            {"step_number": 2, "step_code": "STEP_02", "name": "Step 2", "expected_action": "ACT_2"},
            {"step_number": 4, "step_code": "STEP_04", "name": "Step 4", "expected_action": "ACT_4"},
            {"step_number": 5, "step_code": "STEP_05", "name": "Step 5", "expected_action": "ACT_5"}
        ]
    }
    res = client.post("/api/experiments", json=payload)
    assert res.status_code == 400
    errors = res.json()["detail"]["errors"]
    assert any("strictly sequential" in err.lower() for err in errors)


# =====================================================================
# TEST 7: Reject duplicate step codes.
# =====================================================================
def test_7_reject_duplicate_step_codes():
    name = unique_name("Duplicate Step Code")
    payload = {
        "name": name,
        "steps": [
            {"step_number": 1, "step_code": "STEP_SAME", "name": "Step 1", "expected_action": "ACT_1"},
            {"step_number": 2, "step_code": "STEP_SAME", "name": "Step 2", "expected_action": "ACT_2"}
        ]
    }
    res = client.post("/api/experiments", json=payload)
    assert res.status_code == 400
    errors = res.json()["detail"]["errors"]
    assert any("duplicate step_code" in err.lower() for err in errors)


# =====================================================================
# TEST 8: Reject missing expected_action.
# =====================================================================
def test_8_reject_missing_expected_action():
    name = unique_name("Missing Action")
    payload = {
        "name": name,
        "steps": [
            {"step_number": 1, "step_code": "STEP_01", "name": "Step 1", "expected_action": ""}
        ]
    }
    res = client.post("/api/experiments", json=payload)
    assert res.status_code in (400, 422)


# =====================================================================
# TEST 9: Reject confidence_threshold below 0.
# =====================================================================
def test_9_reject_confidence_threshold_below_zero():
    name = unique_name("Negative Confidence")
    payload = {
        "name": name,
        "steps": [
            {
                "step_number": 1,
                "step_code": "STEP_01",
                "name": "Step 1",
                "expected_action": "ACT_1",
                "confidence_threshold": -0.5
            }
        ]
    }
    res = client.post("/api/experiments", json=payload)
    assert res.status_code in (400, 422)


# =====================================================================
# TEST 10: Reject confidence_threshold above 1.
# =====================================================================
def test_10_reject_confidence_threshold_above_one():
    name = unique_name("Overflow Confidence")
    payload = {
        "name": name,
        "steps": [
            {
                "step_number": 1,
                "step_code": "STEP_01",
                "name": "Step 1",
                "expected_action": "ACT_1",
                "confidence_threshold": 1.5
            }
        ]
    }
    res = client.post("/api/experiments", json=payload)
    assert res.status_code in (400, 422)


# =====================================================================
# TEST 11: Add a step.
# =====================================================================
def test_11_add_step():
    name = unique_name("Add Step Test")
    payload = {
        "name": name,
        "steps": [
            {"step_number": 1, "step_code": "STEP_01", "name": "Initial", "expected_action": "ACT_1"}
        ]
    }
    exp_res = client.post("/api/experiments", json=payload)
    exp_id = exp_res.json()["id"]

    # Add step 2
    step2_payload = {
        "step_number": 2,
        "step_code": "STEP_02",
        "name": "Appended Step",
        "expected_action": "ACT_2",
        "required_objects": ["tool"],
        "confidence_threshold": 0.85
    }
    add_res = client.post(f"/api/experiments/{exp_id}/steps", json=step2_payload)
    assert add_res.status_code == 201
    assert add_res.json()["step_number"] == 2
    assert add_res.json()["step_code"] == "STEP_02"

    # Verify experiment has 2 steps now
    exp_check = client.get(f"/api/experiments/{exp_id}")
    assert len(exp_check.json()["steps"]) == 2


# =====================================================================
# TEST 12: Update a step.
# =====================================================================
def test_12_update_step():
    name = unique_name("Update Step Test")
    payload = {
        "name": name,
        "steps": [
            {"step_number": 1, "step_code": "STEP_01", "name": "Step 1", "expected_action": "OLD_ACTION"}
        ]
    }
    exp_res = client.post("/api/experiments", json=payload)
    exp_id = exp_res.json()["id"]
    step_id = exp_res.json()["steps"][0]["id"]

    # Update step 1
    update_payload = {
        "name": "Renamed Step 1",
        "expected_action": "NEW_ACTION",
        "confidence_threshold": 0.90
    }
    put_res = client.put(f"/api/experiments/{exp_id}/steps/{step_id}", json=update_payload)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["name"] == "Renamed Step 1"
    assert updated["expected_action"] == "NEW_ACTION"
    assert updated["confidence_threshold"] == 0.90


# =====================================================================
# TEST 13: Delete a step and verify protocol validation.
# =====================================================================
def test_13_delete_step_and_verify_protocol_validation():
    name = unique_name("Delete Step Test")
    payload = {
        "name": name,
        "steps": [
            {"step_number": 1, "step_code": "STEP_01", "name": "Step 1", "expected_action": "ACT_1"},
            {"step_number": 2, "step_code": "STEP_02", "name": "Step 2", "expected_action": "ACT_2"}
        ]
    }
    exp_res = client.post("/api/experiments", json=payload)
    exp_id = exp_res.json()["id"]
    steps = exp_res.json()["steps"]

    # Deleting Step 1 leaves only Step 2 (non-sequential 1..N violation)
    del_step1_res = client.delete(f"/api/experiments/{exp_id}/steps/{steps[0]['id']}")
    assert del_step1_res.status_code == 400

    # Deleting Step 2 leaves Step 1 (valid 1..1 sequence)
    del_step2_res = client.delete(f"/api/experiments/{exp_id}/steps/{steps[1]['id']}")
    assert del_step2_res.status_code == 204

    # Verify 1 step remaining
    rem_res = client.get(f"/api/experiments/{exp_id}/steps")
    assert len(rem_res.json()) == 1
    assert rem_res.json()[0]["step_number"] == 1


# =====================================================================
# TEST 14: Update experiment metadata without losing steps.
# =====================================================================
def test_14_update_experiment_metadata_without_losing_steps():
    name = unique_name("Meta Update Test")
    payload = {
        "name": name,
        "description": "Original description",
        "version": "1.0",
        "steps": [
            {"step_number": 1, "step_code": "STEP_01", "name": "Step 1", "expected_action": "ACT_1"},
            {"step_number": 2, "step_code": "STEP_02", "name": "Step 2", "expected_action": "ACT_2"}
        ]
    }
    create_res = client.post("/api/experiments", json=payload)
    exp_id = create_res.json()["id"]

    # Update metadata only (omit steps)
    update_res = client.put(f"/api/experiments/{exp_id}", json={
        "description": "Updated description without steps payload",
        "version": "2.0"
    })
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["description"] == "Updated description without steps payload"
    assert updated_data["version"] == "2.0"
    assert len(updated_data["steps"]) == 2
    assert [s["step_number"] for s in updated_data["steps"]] == [1, 2]


# =====================================================================
# TEST 15: Retrieve protocol endpoint.
# =====================================================================
def test_15_retrieve_protocol_endpoint():
    name = unique_name("Protocol Inspection")
    payload = {
        "name": name,
        "version": "1.0",
        "steps": [
            {
                "step_number": 1,
                "step_code": "STEP_01",
                "name": "Pick Tool",
                "expected_action": "PICK_TOOL",
                "required_objects": ["tool"]
            },
            {
                "step_number": 2,
                "step_code": "STEP_02",
                "name": "Open Container",
                "expected_action": "OPEN_CONTAINER",
                "required_objects": ["container"]
            }
        ]
    }
    create_res = client.post("/api/experiments", json=payload)
    exp_id = create_res.json()["id"]

    proto_res = client.get(f"/api/experiments/{exp_id}/protocol")
    assert proto_res.status_code == 200
    proto = proto_res.json()
    assert proto["experiment_id"] == exp_id
    assert proto["name"] == name
    assert proto["step_count"] == 2
    assert len(proto["steps"]) == 2
    assert proto["steps"][0]["step_code"] == "STEP_01"
    assert proto["steps"][0]["expected_action"] == "PICK_TOOL"


# =====================================================================
# TEST 16: Verify invalid protocol transaction does not leave partially-created database records.
# =====================================================================
def test_16_invalid_protocol_atomic_rollback():
    name = unique_name("Rollback Test Protocol")
    # Step 1 is valid, Step 2 is invalid (conf > 1.0)
    payload = {
        "name": name,
        "steps": [
            {"step_number": 1, "step_code": "STEP_01", "name": "Valid Step 1", "expected_action": "ACT_1"},
            {"step_number": 3, "step_code": "STEP_03", "name": "Invalid Gap Step", "expected_action": "ACT_3"}
        ]
    }

    res = client.post("/api/experiments", json=payload)
    assert res.status_code == 400

    # Ensure experiment was not persisted in database
    with SessionLocal() as db:
        exp = db.query(models.Experiment).filter(models.Experiment.name == name).first()
        assert exp is None

        step = db.query(models.ExperimentStep).filter(models.ExperimentStep.name == "Valid Step 1").first()
        assert step is None


# =====================================================================
# TEST 17: Verify nonexistent experiment returns the correct API error.
# =====================================================================
def test_17_nonexistent_experiment_404():
    res = client.get("/api/experiments/99999999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

    res_steps = client.get("/api/experiments/99999999/steps")
    assert res_steps.status_code == 404

    res_proto = client.get("/api/experiments/99999999/protocol")
    assert res_proto.status_code == 404
