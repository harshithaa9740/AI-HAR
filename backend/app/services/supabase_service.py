"""
Supabase Integration Service for AURAVISION (Step 5)
Provides project connectivity diagnostics, table readiness audits, and cloud synchronization helpers.
Works alongside local offline SQLite without breaking offline resilience.
"""
from typing import Dict, Any, List, Optional
import urllib.request
import json
from app.core.config import settings

EXPECTED_TABLES = [
    "experiments",
    "experiment_steps",
    "experiment_sessions",
    "detection_events",
    "sequence_events",
    "alert_events",
    "session_artifacts",
    "system_settings",
    "system_events",
]


class SupabaseService:
    """Service for interacting with Supabase cloud infrastructure."""

    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.anon_key = settings.SUPABASE_ANON_KEY

    @property
    def is_configured(self) -> bool:
        """Returns True if project URL and key are configured."""
        return bool(self.url and self.anon_key)

    def check_connection(self) -> Dict[str, Any]:
        """
        Verify connectivity to Supabase and check whether schema tables exist.
        Non-destructive, read-only health probe.
        """
        if not self.is_configured:
            return {
                "configured": False,
                "project_url": None,
                "rest_reachable": False,
                "schema_applied": False,
                "active_db_engine": settings.DB_ENGINE,
                "message": "Supabase project URL and API key are not configured.",
            }

        url_base = self.url.rstrip("/") + "/rest/v1/"
        headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
        }

        tables_status: Dict[str, str] = {}
        rest_reachable = False
        all_tables_found = True

        for table in EXPECTED_TABLES:
            req = urllib.request.Request(f"{url_base}{table}?limit=1", headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    rest_reachable = True
                    tables_status[table] = "FOUND"
            except urllib.error.HTTPError as e:
                rest_reachable = True  # We received a valid HTTP response from Supabase PostgREST
                try:
                    body = e.read().decode("utf-8")
                    if "PGRST205" in body:
                        tables_status[table] = "MISSING_TABLE"
                        all_tables_found = False
                    else:
                        tables_status[table] = f"ERROR_{e.code}"
                        all_tables_found = False
                except Exception:
                    tables_status[table] = f"ERROR_{e.code}"
                    all_tables_found = False
            except Exception as e:
                tables_status[table] = f"UNREACHABLE"
                all_tables_found = False

        return {
            "configured": True,
            "project_url": self.url,
            "rest_reachable": rest_reachable,
            "schema_applied": all_tables_found,
            "tables": tables_status,
            "direct_postgres_configured": bool(settings.SUPABASE_DB_URL),
            "active_db_engine": settings.DB_ENGINE,
            "message": "Schema ready for synchronization" if all_tables_found else "Schema migration required in Supabase SQL Editor",
        }

    def forward_entity(self, table_name: str, payload: Dict[str, Any], fk_fields: Optional[List[str]] = None):
        """
        Asynchronously stream any newly created entity to Supabase in real-time.
        Features automatic JSON serialization, ISO timestamp conversion, and resilient FK fallback.
        """
        if not self.is_configured:
            return
        import threading
        from datetime import datetime

        def _send():
            clean_payload = {}
            for k, v in payload.items():
                if v is None:
                    clean_payload[k] = None
                elif isinstance(v, datetime):
                    iso_v = v.isoformat()
                    if not iso_v.endswith("Z") and "+" not in iso_v:
                        iso_v += "Z"
                    clean_payload[k] = iso_v
                elif isinstance(v, (dict, list)):
                    clean_payload[k] = v
                elif isinstance(v, str) and (k in ("metadata", "metadata_json", "required_objects", "bbox")):
                    target_k = "metadata" if k == "metadata_json" else k
                    if not v or v.strip() in ("", "None", "null"):
                        clean_payload[target_k] = None if k == "bbox" else {}
                    else:
                        try:
                            clean_payload[target_k] = json.loads(v)
                        except Exception:
                            clean_payload[target_k] = None if k == "bbox" else v
                elif isinstance(v, (bool, int, float)):
                    clean_payload[k] = v
                else:
                    clean_payload[k] = str(v)

            url = self.url.rstrip("/") + f"/rest/v1/{table_name}"
            headers = {
                "apikey": self.anon_key,
                "Authorization": f"Bearer {self.anon_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
            data = json.dumps(clean_payload, default=str).encode("utf-8")
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=4):
                    return
            except Exception:
                # If foreign key violation, check if parent session needs to be synced first
                if fk_fields and "session_id" in fk_fields and clean_payload.get("session_id"):
                    try:
                        sess_id = clean_payload["session_id"]
                        from app.db.database import SessionLocal
                        from app.db import models
                        with SessionLocal() as db:
                            sess = db.query(models.ExperimentSession).filter(models.ExperimentSession.id == sess_id).first()
                            if sess:
                                sess_payload = {
                                    "id": sess.id,
                                    "experiment_id": sess.experiment_id,
                                    "session_uuid": sess.session_uuid,
                                    "session_name": sess.session_name,
                                    "status": sess.status,
                                    "stream_enabled": sess.stream_enabled,
                                    "current_step_number": sess.current_step_number,
                                    "current_step_code": sess.current_step_code,
                                    "expected_next_step": sess.expected_next_step,
                                    "operator_label": sess.operator_label,
                                    "notes": sess.notes,
                                    "recording_path": sess.recording_path,
                                    "started_at": sess.started_at.isoformat() if sess.started_at else None,
                                    "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
                                    "created_at": sess.created_at.isoformat() if sess.created_at else None,
                                    "updated_at": sess.updated_at.isoformat() if getattr(sess, "updated_at", None) else None
                                }
                                s_req = urllib.request.Request(
                                    self.url.rstrip("/") + "/rest/v1/experiment_sessions",
                                    data=json.dumps(sess_payload, default=str).encode("utf-8"),
                                    headers=headers,
                                    method="POST"
                                )
                                with urllib.request.urlopen(s_req, timeout=4):
                                    pass
                                # Retry original entity insert
                                req_retry = urllib.request.Request(url, data=data, headers=headers, method="POST")
                                with urllib.request.urlopen(req_retry, timeout=4):
                                    return
                    except Exception:
                        pass

                # If still failing, set nullable FK fields to None and retry
                if fk_fields:
                    try:
                        fallback = dict(clean_payload)
                        for f in fk_fields:
                            fallback[f] = None
                        data_fb = json.dumps(fallback, default=str).encode("utf-8")
                        req_fb = urllib.request.Request(url, data=data_fb, headers=headers, method="POST")
                        with urllib.request.urlopen(req_fb, timeout=4):
                            return
                    except Exception:
                        pass
        threading.Thread(target=_send, daemon=True).start()

    def forward_alert(self, payload: Dict[str, Any]):
        """Non-blocking fire-and-forget push of alert to Supabase cloud with FK fallback."""
        self.forward_entity("alert_events", payload, fk_fields=["session_id", "validation_event_id"])

    def push_records(self, table_name: str, records: List[Dict[str, Any]]) -> bool:
        """Batch insert records into a Supabase table via PostgREST."""
        if not self.is_configured or not records:
            return False
        url = self.url.rstrip("/") + f"/rest/v1/{table_name}"
        headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates"
        }
        data = json.dumps(records, default=str).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status in (200, 201)
        except Exception as e:
            return False



supabase_service = SupabaseService()

