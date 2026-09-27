"""
Manual verification script for STEP 5: Mock AI Pipeline
Tests end-to-end integration of Mock Detector, Mock Activity Model, Demo Service, and Sequence Validator.
"""
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.core.constants import DemoScenario, ValidationResult, SessionStatus

client = TestClient(app)

def run_verification():
    print("=" * 70)
    print("AURAVISION STEP 5: MOCK AI PIPELINE VERIFICATION")
    print("=" * 70)

    # 1. Create a clean test experiment protocol
    exp_name = f"Step 5 Verification Protocol {uuid.uuid4().hex[:6]}"
    exp_payload = {
        "name": exp_name,
        "description": "5-step deterministic protocol for mock AI verification",
        "version": "1.0",
        "is_active": True,
        "steps": [
            {
                "step_number": 1,
                "step_code": "STEP_01",
                "name": "Pick Tool",
                "expected_action": "PICK_TOOL",
                "required_objects": ["tool"],
                "confidence_threshold": 0.80
            },
            {
                "step_number": 2,
                "step_code": "STEP_02",
                "name": "Open Container",
                "expected_action": "OPEN_CONTAINER",
                "required_objects": ["container"],
                "confidence_threshold": 0.80
            },
            {
                "step_number": 3,
                "step_code": "STEP_03",
                "name": "Take Sample",
                "expected_action": "TAKE_SAMPLE",
                "required_objects": ["sample"],
                "confidence_threshold": 0.80
            },
            {
                "step_number": 4,
                "step_code": "STEP_04",
                "name": "Place Sample",
                "expected_action": "PLACE_SAMPLE",
                "required_objects": ["sample", "container"],
                "confidence_threshold": 0.80
            },
            {
                "step_number": 5,
                "step_code": "STEP_05",
                "name": "Close Container",
                "expected_action": "CLOSE_CONTAINER",
                "required_objects": ["container"],
                "confidence_threshold": 0.80
            }
        ]
    }
    exp_res = client.post("/api/experiments", json=exp_payload)
    assert exp_res.status_code == 201, f"Failed to create experiment: {exp_res.text}"
    exp_data = exp_res.json()
    exp_id = exp_data["id"]
    print(f"[OK] Created test experiment ID: {exp_id} ({exp_name})")

    # -------------------------------------------------------------
    # 2. Test NORMAL Scenario
    # -------------------------------------------------------------
    print("\n--- Testing NORMAL Scenario Flow ---")
    sess_res = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": f"NORMAL-{uuid.uuid4().hex[:4]}"})
    assert sess_res.status_code == 201
    sess_id = sess_res.json()["id"]

    # Start NORMAL demo
    start_res = client.post("/api/demo/start", json={"session_id": sess_id, "scenario": DemoScenario.NORMAL.value})
    assert start_res.status_code == 200
    assert start_res.json()["active"] is True
    print(f"[OK] Demo started with scenario: NORMAL on session {sess_id}")

    # Execute 5 steps
    expected_actions = ["PICK_TOOL", "OPEN_CONTAINER", "TAKE_SAMPLE", "PLACE_SAMPLE", "CLOSE_CONTAINER"]
    for i, exp_act in enumerate(expected_actions, 1):
        step_res = client.post("/api/demo/step", json={"session_id": sess_id})
        assert step_res.status_code == 200
        step_data = step_res.json()
        obs = step_data["observation"]
        val = step_data["validation"]
        print(f"  Step {i}: Observed {obs['action_code']} ({obs['confidence']:.2f}) -> Result: {val['result']}, Next Step: {val['next_step_number']}")
        assert obs["action_code"] == exp_act
        if i < 5:
            assert val["result"] == ValidationResult.VALID.value
        else:
            assert val["result"] == ValidationResult.EXPERIMENT_COMPLETE.value
            assert val["completed"] is True

    # Check status
    status_res = client.get(f"/api/demo/status/{sess_id}")
    assert status_res.json()["completed"] is True
    assert status_res.json()["observations_generated"] == 5
    print("[OK] NORMAL scenario reached EXPERIMENT_COMPLETE successfully.")

    # -------------------------------------------------------------
    # 3. Test SKIPPED_STEP Scenario
    # -------------------------------------------------------------
    print("\n--- Testing SKIPPED_STEP Scenario Flow ---")
    sess_res = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": f"SKIP-{uuid.uuid4().hex[:4]}"})
    sess_id = sess_res.json()["id"]

    client.post("/api/demo/start", json={"session_id": sess_id, "scenario": DemoScenario.SKIPPED_STEP.value})

    # Step 1: PICK_TOOL -> VALID
    res1 = client.post("/api/demo/step", json={"session_id": sess_id}).json()
    assert res1["validation"]["result"] == ValidationResult.VALID.value

    # Step 2: TAKE_SAMPLE (skipped step 2 OPEN_CONTAINER) -> STEP_SKIPPED
    res2 = client.post("/api/demo/step", json={"session_id": sess_id}).json()
    assert res2["validation"]["result"] == ValidationResult.STEP_SKIPPED.value
    print(f"[OK] SKIPPED_STEP correctly flagged by Sequence Validator: {res2['validation']['result']}")

    # -------------------------------------------------------------
    # 4. Test OUT_OF_SEQUENCE Scenario
    # -------------------------------------------------------------
    print("\n--- Testing OUT_OF_SEQUENCE Scenario Flow ---")
    sess_res = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": f"OOS-{uuid.uuid4().hex[:4]}"})
    sess_id = sess_res.json()["id"]

    client.post("/api/demo/start", json={"session_id": sess_id, "scenario": DemoScenario.OUT_OF_SEQUENCE.value})

    # Step 1: PICK_TOOL -> VALID
    client.post("/api/demo/step", json={"session_id": sess_id})
    # Step 2: OPEN_CONTAINER -> VALID
    client.post("/api/demo/step", json={"session_id": sess_id})
    # Step 3: PICK_TOOL (repeating step 1 while step 3 is expected) -> OUT_OF_SEQUENCE
    res3 = client.post("/api/demo/step", json={"session_id": sess_id}).json()
    assert res3["validation"]["result"] in (ValidationResult.OUT_OF_SEQUENCE.value, ValidationResult.STEP_SKIPPED.value)
    print(f"[OK] OUT_OF_SEQUENCE correctly flagged by Sequence Validator: {res3['validation']['result']}")

    # -------------------------------------------------------------
    # 5. Test LOW_CONFIDENCE Scenario
    # -------------------------------------------------------------
    print("\n--- Testing LOW_CONFIDENCE Scenario Flow ---")
    sess_res = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": f"CONF-{uuid.uuid4().hex[:4]}"})
    sess_id = sess_res.json()["id"]

    client.post("/api/demo/start", json={"session_id": sess_id, "scenario": DemoScenario.LOW_CONFIDENCE.value})
    res_low = client.post("/api/demo/step", json={"session_id": sess_id}).json()
    assert res_low["validation"]["result"] == ValidationResult.VERIFY_REQUIRED.value
    print(f"[OK] LOW_CONFIDENCE correctly flagged as VERIFY_REQUIRED (confidence: {res_low['observation']['confidence']})")

    # -------------------------------------------------------------
    # 6. Test UNKNOWN_ACTION Scenario
    # -------------------------------------------------------------
    print("\n--- Testing UNKNOWN_ACTION Scenario Flow ---")
    sess_res = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": f"UNK-{uuid.uuid4().hex[:4]}"})
    sess_id = sess_res.json()["id"]

    client.post("/api/demo/start", json={"session_id": sess_id, "scenario": DemoScenario.UNKNOWN_ACTION.value})
    res_unk = client.post("/api/demo/step", json={"session_id": sess_id}).json()
    assert res_unk["validation"]["result"] == ValidationResult.UNKNOWN_ACTION.value
    print(f"[OK] UNKNOWN_ACTION correctly flagged as UNKNOWN_ACTION: {res_unk['validation']['result']}")

    # -------------------------------------------------------------
    # 7. Test MISSING_OBJECT Scenario
    # -------------------------------------------------------------
    print("\n--- Testing MISSING_OBJECT Scenario Flow ---")
    sess_res = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": f"MISSOBJ-{uuid.uuid4().hex[:4]}"})
    sess_id = sess_res.json()["id"]

    client.post("/api/demo/start", json={"session_id": sess_id, "scenario": DemoScenario.MISSING_OBJECT.value})
    res_mis = client.post("/api/demo/step", json={"session_id": sess_id}).json()
    assert res_mis["validation"]["result"] in (
        ValidationResult.VERIFY_REQUIRED.value,
        ValidationResult.STEP_SKIPPED.value,
        ValidationResult.OUT_OF_SEQUENCE.value,
    )
    print(f"[OK] MISSING_OBJECT scenario handled properly: {res_mis['validation']['result']}")

    print("\n" + "=" * 70)
    print("ALL STEP 5 MOCK AI PIPELINE MANUAL VERIFICATIONS PASSED CLEANLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()
