"""
Session Audit Logging Service (Human-Readable TXT & Structured JSONL)
"""
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union
from app.core.config import LOGS_DIR
from app.core.logging import logger


class SessionLoggingService:
    """Handles persistent lightweight audit logs for experiment sessions."""

    @staticmethod
    def get_log_paths(session_id: Union[int, str], session_code: str) -> Dict[str, Path]:
        sess_id_str = str(session_id)
        clean_code = "".join(c for c in str(session_code) if c.isalnum() or c in ("-", "_"))
        txt_path = LOGS_DIR / f"session_{clean_code}_{sess_id_str[:8]}.log"
        jsonl_path = LOGS_DIR / f"session_{clean_code}_{sess_id_str[:8]}.jsonl"
        return {"txt": txt_path, "jsonl": jsonl_path}

    @staticmethod
    def log_step_event(
        session_id: Union[int, str],
        session_code: str,
        step_number: Optional[int],
        action_code: str,
        result: str,
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        paths = SessionLoggingService.get_log_paths(session_id, session_code)
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        step_str = f"STEP_{step_number:02d}" if step_number is not None else "STEP_NA"

        # 1. Human-Readable TXT Log line
        # e.g.: 2026-09-19T10:31:02Z | STEP_01 | PICK_TOOL | COMPLETED | confidence=0.96
        status_label = "COMPLETED" if result == "VALID" else result
        txt_line = f"{now_iso} | {step_str} | {action_code} | {status_label} | confidence={confidence:.2f}\n"

        try:
            with open(paths["txt"], "a", encoding="utf-8") as f:
                f.write(txt_line)
        except Exception as e:
            logger.error(f"Failed to write TXT session log: {e}")

        # 2. Structured JSONL line
        jsonl_entry = {
            "timestamp": now_iso,
            "session_id": str(session_id),
            "session_code": str(session_code),
            "step_number": step_number,
            "action_code": action_code,
            "result": result,
            "confidence": confidence,
            "metadata": metadata or {}
        }

        try:
            with open(paths["jsonl"], "a", encoding="utf-8") as f:
                f.write(json.dumps(jsonl_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write JSONL session log: {e}")

    @staticmethod
    def read_log(session_id: Union[int, str], session_code: str, format_type: str = "txt") -> str:
        paths = SessionLoggingService.get_log_paths(session_id, session_code)
        target_path = paths["jsonl"] if format_type == "jsonl" else paths["txt"]
        
        if not target_path.exists():
            return f"# Log for session {session_code} is empty or not yet generated."
        
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read session log: {e}")
            return f"Error reading log: {str(e)}"
