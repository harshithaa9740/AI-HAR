"""
Script to inspect frontend app.js and backend write paths for alert_events, detection_events, etc.
"""
import os
import re
from pathlib import Path

app_js = Path("app.js")
if app_js.exists():
    text = app_js.read_text(encoding="utf-8")
    print(f"app.js total lines: {len(text.splitlines())}")
    
    # Check alert creation
    alerts_matches = [line.strip() for line in text.splitlines() if "alert" in line.lower()][:15]
    print(f"\nSample lines with 'alert' in app.js:")
    for line in alerts_matches[:8]:
        print(f"  {line[:90]}")
        
    # Check network calls
    fetch_lines = [line.strip() for line in text.splitlines() if "fetch(" in line or "http" in line or "/api" in line]
    print(f"\nNetwork calls in app.js ({len(fetch_lines)} lines):")
    for line in fetch_lines:
        print(f"  {line[:100]}")

print("\n--- Checking backend active configuration ---")
from app.core.config import settings
print(f"DB_ENGINE: {settings.DB_ENGINE}")
print(f"DATABASE_URL: {settings.DATABASE_URL}")
print(f"SUPABASE_URL: {settings.SUPABASE_URL}")
print(f"SUPABASE_DB_URL: {settings.SUPABASE_DB_URL}")
print(f"SUPABASE_ANON_KEY set: {bool(settings.SUPABASE_ANON_KEY)}")
