"""
AURAVISION Bio-Astronautics Synthetic Mission Data Generator
Generates realistic space station payloads, astronaut experiment protocols,
AI perception detections, sequence validations, multi-tier alerts, and telemetry.
Populates both local SQLite and synchronizes to Supabase.
"""
import sys
import os
import json
import random
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure backend root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from app.db import models
from app.core.config import settings

def generate_synthetic_data(num_sessions: int = 5):
    print("=" * 70)
    print("AURAVISION BIO-ASTRONAUTICS SYNTHETIC DATA GENERATOR")
    print("=" * 70)

    db = SessionLocal()

    # 1. Define Core Bio-Astronautics Experiment Protocols
    protocols_data = [
        {
            "name": "BAS-EXP-01: Microgravity Blood Sample Centrifugation",
            "description": "Validation protocol for hematocrit cellular separation and plasma stabilization under microgravity.",
            "version": "2.4",
            "steps": [
                ("STEP_01", "Equip Bio-Containment Gloves", "EQUIP_GLOVES", ["safety_gloves"], 0.95),
                ("STEP_02", "Inspect Centrifuge Rotor Chamber", "INSPECT_CHAMBER", ["centrifuge_rotor"], 0.92),
                ("STEP_03", "Retrieve Blood Sample Vial", "PICK_TOOL", ["sample_vial"], 0.94),
                ("STEP_04", "Open Containment Rack", "OPEN_CONTAINER", ["container", "vial_rack"], 0.90),
                ("STEP_05", "Load Vial Into Opposing Slot", "LOAD_ROTOR", ["sample_vial", "centrifuge_rotor"], 0.93),
                ("STEP_06", "Insert Balanced Counterweight", "PLACE_SAMPLE", ["counterweight", "centrifuge_rotor"], 0.91),
                ("STEP_07", "Close & Latch Centrifuge Lid", "CLOSE_CONTAINER", ["centrifuge_lid"], 0.96),
                ("STEP_08", "Initiate 8000 RPM Spin Cycle", "START_SPIN", ["control_panel"], 0.95),
            ]
        },
        {
            "name": "BAS-EXP-02: Plant Habitat Hydroponic Nutrient Dosing",
            "description": "Vegetative crop nutritional injection and photoperiod telemetry verification in Module Node 2.",
            "version": "1.8",
            "steps": [
                ("STEP_01", "Calibrate Digital pH Sensor", "CALIBRATE_SENSOR", ["ph_probe"], 0.93),
                ("STEP_02", "Retrieve Nutrient Micro-Syringe", "PICK_TOOL", ["syringe"], 0.95),
                ("STEP_03", "Open Growth Chamber Port", "OPEN_CONTAINER", ["growth_chamber"], 0.91),
                ("STEP_04", "Inject Macro-Nutrient Solution", "INJECT_NUTRIENT", ["syringe", "root_sponge"], 0.94),
                ("STEP_05", "Record Root Membrane Telemetry", "RECORD_DATA", ["data_tablet"], 0.89),
                ("STEP_06", "Seal Growth Chamber Port", "CLOSE_CONTAINER", ["growth_chamber"], 0.97),
            ]
        },
        {
            "name": "BAS-EXP-03: Astronaut Bone Density Ultrasound Telemetry",
            "description": "Musculoskeletal acoustic velocity telemetry to monitor trabecular bone loss during extended orbital stay.",
            "version": "3.1",
            "steps": [
                ("STEP_01", "Power On Ultrasound Diagnostic Console", "POWER_ON", ["ultrasound_console"], 0.96),
                ("STEP_02", "Apply Acoustic Transmission Gel", "APPLY_GEL", ["gel_dispenser", "transducer"], 0.92),
                ("STEP_03", "Position Transducer on Tibial Plateau", "ALIGN_PROBE", ["transducer", "leg_harness"], 0.94),
                ("STEP_04", "Record High-Frequency Acoustic Pulse", "RECORD_TELEMETRY", ["transducer", "data_monitor"], 0.95),
                ("STEP_05", "Sanitize & Stow Acoustic Transducer", "CLEAN_EQUIPMENT", ["sanitizing_wipe", "transducer"], 0.90),
            ]
        },
        {
            "name": "BAS-EXP-04: Extravehicular Suit Pressure Seal Audit",
            "description": "Pre-EVA primary life support umbilical seal check and atmospheric decay audit in the Quest airlock.",
            "version": "1.5",
            "steps": [
                ("STEP_01", "Inspect Helmet Neck Ring O-Ring", "INSPECT_SEAL", ["helmet_o_ring"], 0.97),
                ("STEP_02", "Engage Primary Visor Double-Latch", "LOCK_VISOR", ["helmet_visor"], 0.96),
                ("STEP_03", "Pressurize Suit to 4.3 PSI", "REGULATE_PRESSURE", ["suit_valve"], 0.95),
                ("STEP_04", "Monitor 180s Pressure Decay Curve", "AUDIT_DECAY", ["pressure_gauge"], 0.98),
                ("STEP_05", "Authorize EVA Ingress Check", "AUTHORIZE_EVA", ["comms_panel"], 0.99),
            ]
        }
    ]

    operators = [
        "Dr. Sunita Sharma (Payload Specialist)",
        "CDR Rajesh Mohan (Mission Commander)",
        "Dr. Elena Rostova (Flight Surgeon)",
        "Specialist Marcus Vance (Robotics Engineer)",
        "Flight Engineer Maya Lin (Orbital Science)"
    ]

    cameras = ["station_cam_overhead", "payload_rack_macro", "helmet_mount_01", "airlock_cam_wide"]

    created_experiments = []
    created_sessions = []
    created_detections = []
    created_sequences = []
    created_alerts = []

    # Create / reuse Experiments and Steps
    for p_info in protocols_data:
        exp = db.query(models.Experiment).filter(models.Experiment.name == p_info["name"]).first()
        if not exp:
            exp = models.Experiment(
                name=p_info["name"],
                description=p_info["description"],
                version=p_info["version"],
                is_active=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 15))
            )
            db.add(exp)
            db.commit()
            db.refresh(exp)

            # Add Steps
            for idx, (code, s_name, action, objs, conf) in enumerate(p_info["steps"], 1):
                step = models.ExperimentStep(
                    experiment_id=exp.id,
                    step_number=idx,
                    step_code=code,
                    name=s_name,
                    description=f"Standard operating procedure for {s_name}",
                    expected_action=action,
                    required_objects=json.dumps(objs),
                    confidence_threshold=conf,
                    expected_duration_seconds=random.randint(20, 90),
                    created_at=exp.created_at
                )
                db.add(step)
            db.commit()
            print(f"[EXPERIMENT] Created protocol: {exp.name} ({len(p_info['steps'])} steps)")
        created_experiments.append(exp)

    # Generate Synthetic Astronaut Sessions
    now = datetime.now(timezone.utc)
    for i in range(num_sessions):
        exp = random.choice(created_experiments)
        db_steps = db.query(models.ExperimentStep).filter(models.ExperimentStep.experiment_id == exp.id).order_by(models.ExperimentStep.step_number).all()
        operator = random.choice(operators)
        sess_start = now - timedelta(hours=random.randint(1, 48), minutes=random.randint(5, 50))
        is_completed = random.choice([True, True, False])
        sess_end = sess_start + timedelta(minutes=random.randint(10, 45)) if is_completed else None

        status = "COMPLETED" if is_completed else random.choice(["RUNNING", "PAUSED"])
        curr_step_idx = len(db_steps) if is_completed else random.randint(1, max(1, len(db_steps) - 1))
        curr_step = db_steps[curr_step_idx - 1] if db_steps else None

        session = models.ExperimentSession(
            experiment_id=exp.id,
            session_uuid=models.generate_uuid(),
            session_name=f"ORBITAL-RUN-{exp.name.split(':')[0]}-{random.randint(100, 999)}",
            status=status,
            started_at=sess_start,
            ended_at=sess_end,
            current_step_number=curr_step_idx,
            current_step_code=curr_step.step_code if curr_step else "STEP_01",
            expected_next_step=f"{curr_step.step_code} / {curr_step.name}" if curr_step else "COMPLETED",
            operator_label=operator,
            notes=f"Synthetic BAS telemetry session recorded by {operator}. Microgravity verified.",
            recording_path=f"recordings/auravision_bas_sim_{sess_start.strftime('%Y%m%d_%H%M%S')}.mp4",
            stream_enabled=True,
            created_at=sess_start
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        created_sessions.append(session)
        print(f"[SESSION] Created execution session: {session.session_name} ({session.status})")

        # Generate Detections, Validations, and Alerts for this session
        sess_time = sess_start
        for step in db_steps[:curr_step_idx]:
            step_objs = json.loads(step.required_objects) if step.required_objects else ["tool"]
            primary_obj = step_objs[0] if step_objs else "tool"

            # 1. Detection Event
            sess_time += timedelta(seconds=random.randint(15, 45))
            bbox = [
                round(random.uniform(0.15, 0.35), 3),
                round(random.uniform(0.20, 0.40), 3),
                round(random.uniform(0.65, 0.85), 3),
                round(random.uniform(0.60, 0.80), 3)
            ]
            det = models.DetectionEvent(
                session_id=session.id,
                protocol_step_id=step.id,
                timestamp=sess_time,
                frame_number=random.randint(120, 4800),
                start_time_ms=float(random.randint(1000, 60000)),
                end_time_ms=float(random.randint(61000, 120000)),
                entity_type="ACTION",
                entity_name=step.expected_action,
                confidence=round(random.uniform(0.88, 0.99), 3),
                bbox=json.dumps(bbox),
                source=random.choice(cameras),
                metadata_json=json.dumps({
                    "synthetic": True,
                    "target_object": primary_obj,
                    "operator": operator,
                    "optical_clarity": "NOMINAL"
                })
            )
            db.add(det)
            db.commit()
            db.refresh(det)
            created_detections.append(det)

            # 2. Sequence Validation Event
            sess_time += timedelta(seconds=2)
            seq = models.SequenceEvent(
                session_id=session.id,
                protocol_step_id=step.id,
                event_type="STEP_VALIDATED",
                timestamp=sess_time,
                expected_step_number=step.step_number,
                expected_step_code=step.step_code,
                observed_step_number=step.step_number,
                observed_step_code=step.step_code,
                result="VALID",
                confidence=round(random.uniform(0.91, 0.99), 3),
                message=f"Step {step.step_number} ({step.name}) successfully completed and verified.",
                metadata_json=json.dumps({
                    "observed_objects": step_objs,
                    "tolerance_ms": 320,
                    "synthetic": True
                })
            )
            db.add(seq)
            db.commit()
            db.refresh(seq)
            created_sequences.append(seq)

            # 3. Alert Event (Step Completion)
            alert_compl = models.AlertEvent(
                session_id=session.id,
                validation_event_id=seq.id,
                timestamp=sess_time + timedelta(milliseconds=300),
                alert_type="STEP_COMPLETED",
                severity="INFO",
                category="protocol",
                message=f"Step {step.step_number} ({step.name}) completed nominally.",
                acknowledged=True,
                acknowledged_at=sess_time + timedelta(seconds=5),
                spoken=True,
                metadata_json=json.dumps({
                    "voice_prompt": f"Step {step.step_number} completed. Proceeding.",
                    "synthetic": True
                })
            )
            db.add(alert_compl)
            db.commit()
            created_alerts.append(alert_compl)

            # Occasionally generate a deviation alert (simulated skipped or warning)
            if random.random() < 0.35:
                warn_time = sess_time - timedelta(seconds=8)
                warn_alert = models.AlertEvent(
                    session_id=session.id,
                    validation_event_id=seq.id,
                    timestamp=warn_time,
                    alert_type=random.choice(["LOW_CONFIDENCE", "DEVIATION_ALERT", "OBJECT_UNVERIFIED"]),
                    severity="WARNING",
                    category="protocol",
                    message=f"Optical verification check: {primary_obj} detected with marginal contrast.",
                    acknowledged=True,
                    acknowledged_at=warn_time + timedelta(seconds=3),
                    spoken=False,
                    metadata_json=json.dumps({
                        "caution": "Lighting glare detected by neural filter",
                        "synthetic": True
                    })
                )
                db.add(warn_alert)
                db.commit()
                created_alerts.append(warn_alert)

        # Session Artifact
        artifact = models.SessionArtifact(
            session_id=session.id,
            artifact_type="recording",
            file_path=session.recording_path,
            file_name=os.path.basename(session.recording_path),
            mime_type="video/mp4",
            file_size_bytes=random.randint(15_000_000, 85_000_000),
            created_at=sess_start,
            metadata_json=json.dumps({
                "resolution": "1920x1080",
                "codec": "h264",
                "fps": 30,
                "synthetic": True
            })
        )
        db.add(artifact)

        # Audit log artifact
        audit_artifact = models.SessionArtifact(
            session_id=session.id,
            artifact_type="log_json",
            file_path=f"data/logs/audit_{session.session_uuid[:8]}.json",
            file_name=f"audit_{session.session_uuid[:8]}.json",
            mime_type="application/json",
            file_size_bytes=random.randint(4500, 18000),
            created_at=sess_start + timedelta(minutes=10),
            metadata_json=json.dumps({"hash": "sha256:7f8e8a9...", "compliance": "NASA-STD-3001"})
        )
        db.add(audit_artifact)
        db.commit()

    db.close()

    print("\n" + "=" * 70)
    print("SYNTHETIC DATA GENERATION COMPLETE (LOCAL SQLITE):")
    print(f"  - Experiments Created:  {len(created_experiments)}")
    print(f"  - Sessions Created:     {len(created_sessions)}")
    print(f"  - Detections Created:   {len(created_detections)}")
    print(f"  - Validations Created:  {len(created_sequences)}")
    print(f"  - Alerts Created:       {len(created_alerts)}")
    print("=" * 70)

    # Now synchronize new records to Supabase!
    print("\nSynchronizing newly created synthetic records to Supabase...")
    from scripts.migrate_sqlite_to_supabase import run_rest_migration
    db_file = Path(__file__).resolve().parent.parent / "data" / "auravision.db"
    if not db_file.exists():
        db_file = Path("backend/data/auravision.db")
    run_rest_migration(db_file)


if __name__ == "__main__":
    generate_synthetic_data(num_sessions=6)
