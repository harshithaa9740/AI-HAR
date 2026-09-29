# AURAVISION: Supabase & PostgreSQL Architecture and Migration Guide (Step 4)

> **Operational Notice:** In accordance with space-station requirements for edge autonomy and offline resilience, **local SQLite remains the default, active operational datastore**. No cloud connections are established in this step, and no internet access is required for local operations. This document and its accompanying SQL migrations prepare AURAVISION for future ground-station synchronization.

---

## 1. Architectural Overview: Edge-First with Ground-Station Uplink

AURAVISION employs a hybrid **edge-first** architecture designed for harsh or disconnected environments (such as the International Space Station or orbital modules):

```
+-------------------------------------------------------------------------+
|                        AURAVISION LOCAL NODE (EDGE)                     |
|                                                                         |
|  [ Camera Feed / File ] -> [ RealTimeProcessor / AI Pipeline ]          |
|                                         |                               |
|                                         v                               |
|                          [ Sequence State Machine ]                     |
|                                         |                               |
|                     +-------------------+-------------------+           |
|                     v                                       v           |
|            [ SQLite Datastore ]                   [ Local Storage ]     |
|          (auravision.db - 9 tables)             (data/recordings/*.mp4) |
|                     |                                       |           |
+---------------------|---------------------------------------|-----------+
                      |                                       |
                      |   (Future Step 5 Ground Uplink)       |
                      v   (Transactional Batches with Token)  v
+-------------------------------------------------------------------------+
|                    SUPABASE CLOUD / GROUND-STATION                      |
|                                                                         |
|  [ PostgreSQL 15+ Schema ]               [ Supabase Storage Buckets ]   |
|   - 9 Mirror Tables (JSONB, TIMESTAMPTZ)  - auravision-recordings       |
|   - Row Level Security (RLS)              - auravision-artifacts        |
|   - Strict Foreign Key Cascades                                         |
+-------------------------------------------------------------------------+
```

### Key Principles:
1. **Zero Cloud Dependency for Live Procedures:** An astronaut conducting a biological air-sampler (BAS) procedure will never experience latency, buffering, or operational halts due to internet or cloud connectivity issues.
2. **Deterministic Sequence Validation:** The sequence validation state machine runs locally in Python, persisting sequence states and alert events instantly to SQLite.
3. **Lossless Synchronization:** When network uplink is restored, data will sync in dependency order using idempotent upserts and UUID correlation keys.

---

## 2. Local Database Audit (Source of Truth)

An inspection of `backend/data/auravision.db` and `backend/app/db/models.py` reveals the following active database architecture:

* **Engine:** SQLite 3.45.1
* **File Location:** `backend/data/auravision.db`
* **Total Tables:** 9 normalized tables
* **Total Live Records:** 18,434 records audited

| Table Name | Primary Key | Foreign Keys | Key Columns & Indexes | Row Count |
|---|---|---|---|---|
| `experiments` | `id` (INTEGER, PK autoincrement) | None | `name` (UNIQUE), `version`, `is_active`, `created_at`, `updated_at` | 1,086 |
| `experiment_steps` | `id` (INTEGER, PK autoincrement) | `experiment_id` -> `experiments.id` (ON DELETE CASCADE) | `step_number`, `step_code`, `expected_action`, `required_objects` (JSON), `confidence_threshold`, `validation_rules` (JSON), `expected_duration_seconds`. UNIQUE(`experiment_id`, `step_number`) | 4,129 |
| `experiment_sessions` | `id` (INTEGER, PK autoincrement) | `experiment_id` -> `experiments.id` (ON DELETE CASCADE) | `session_uuid` (VARCHAR(64), UNIQUE), `session_name`, `status`, `started_at`, `ended_at`, `current_step_number`, `operator_label`, `notes`, `recording_path`, `stream_enabled` | 2,260 |
| `detection_events` | `id` (INTEGER, PK autoincrement) | `session_id` -> `experiment_sessions.id` (CASCADE), `protocol_step_id` -> `experiment_steps.id` (SET NULL) | `timestamp`, `frame_number`, `start_time_ms`, `end_time_ms`, `entity_type`, `entity_name`, `confidence`, `bbox` (JSON), `source`, `metadata` (JSON) | 1,167 |
| `sequence_events` | `id` (INTEGER, PK autoincrement) | `session_id` -> `experiment_sessions.id` (CASCADE), `protocol_step_id` -> `experiment_steps.id` (SET NULL) | `event_type`, `timestamp`, `expected_step_number`, `expected_step_code`, `observed_step_number`, `observed_step_code`, `result`, `confidence`, `message`, `metadata` (JSON) | 2,105 |
| `alert_events` | `id` (INTEGER, PK autoincrement) | `session_id` -> `experiment_sessions.id` (CASCADE), `validation_event_id` -> `sequence_events.id` (SET NULL) | `timestamp`, `alert_type`, `severity`, `category`, `message`, `acknowledged`, `acknowledged_at`, `spoken`, `metadata` (JSON) | 1,421 |
| `session_artifacts` | `id` (INTEGER, PK autoincrement) | `session_id` -> `experiment_sessions.id` (CASCADE) | `artifact_type`, `file_path`, `file_name`, `mime_type`, `file_size_bytes`, `created_at`, `metadata` (JSON) | 36 |
| `system_settings` | `id` (INTEGER, PK autoincrement) | None | `setting_key` (VARCHAR(100), UNIQUE), `setting_value` (TEXT), `updated_at` | 2 |
| `system_events` | `id` (INTEGER, PK autoincrement) | `session_id` -> `experiment_sessions.id` (CASCADE) | `timestamp`, `event_type`, `severity`, `message`, `component`, `metadata` (JSON) | 6,228 |

---

## 3. PostgreSQL & Supabase Compatibility Analysis

### Confirmed Incompatibilities & Resolutions:

1. **Schema Introspection in `database.py:init_db()`**
   * *Issue:* The original database setup used `PRAGMA table_info(...)` to detect missing columns. In PostgreSQL, `PRAGMA` statements trigger syntax errors.
   * *Resolution:* Replaced SQLite-specific pragmas with SQLAlchemy's dialect-agnostic `inspect(active_engine).get_columns(table_name)`, making introspection work identically across SQLite, PostgreSQL, and MySQL.

2. **SQLite Connection PRAGMAs**
   * *Issue:* `@event.listens_for(Engine, "connect")` executed `PRAGMA foreign_keys=ON` on every connection. While required for SQLite, PostgreSQL throws an error on `PRAGMA`.
   * *Resolution:* Guarded the listener with an explicit dialect check (`is_sqlite = "sqlite" in settings.DATABASE_URL.lower()`), ensuring foreign keys are activated for SQLite without interfering with PostgreSQL.

3. **Data Types: JSONB vs TEXT, TIMESTAMPTZ vs DATETIME, BOOLEAN vs INTEGER**
   * *JSON Storage:* In SQLite, JSON fields (`metadata`, `required_objects`, `validation_rules`, `bbox`) are stored as `TEXT`. In PostgreSQL/Supabase, native `JSONB` is used to allow indexing and deep-path queries. We introduced `app.db.serializers` (`ensure_json_obj`, `ensure_json_str`) to make payload conversion transparent.
   * *Timestamps:* In SQLite, timestamps are ISO-8601 strings. In Supabase, `TIMESTAMPTZ` with UTC enforcement is required. `format_utc_iso()` was introduced to ensure valid UTC strings with explicit 'Z' or '+00:00' offsets.
   * *Booleans:* In SQLite, booleans are integers (0 or 1). PostgreSQL uses native `BOOLEAN` (`true`/`false`).

4. **Primary Key Auto-generation vs Identity Sync**
   * *Issue:* If PostgreSQL used `BIGINT GENERATED ALWAYS AS IDENTITY`, attempting to insert existing local records with their local `id` numbers during migration would fail.
   * *Resolution:* In `backend/migrations/001_initial_supabase_schema.sql`, we specify `BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY`. This allows the migration script to preserve the exact local IDs, and sequence values are reset via `SELECT setval(...)` afterwards. Furthermore, `session_uuid` provides a globally unique, conflict-free synchronization key.

5. **Avoiding Binary Video Blobs in Database Tables**
   * *Issue:* Storing video recordings as raw bytes in PostgreSQL tables causes severe performance degradation, storage bloat, and connection timeouts.
   * *Resolution:* The schema explicitly stores metadata only in `session_artifacts` (`file_path`, `file_name`, `mime_type`, `file_size_bytes`). Video files will be uploaded directly to a dedicated Supabase Storage bucket (`auravision-recordings`) via signed URLs, never through SQL `INSERT` statements.

---

## 4. Proposed Supabase PostgreSQL Schema

The schema migration DDL is located at:
[backend/migrations/001_initial_supabase_schema.sql](file:///c:/Users/Harshitha/Desktop/SIH/backend/migrations/001_initial_supabase_schema.sql)

It establishes:
* All 9 tables matching local models.
* B-tree indexes for fast session timeline queries and step ordering.
* GIN indexes on `metadata` and `required_objects` for rapid JSONB querying.
* Automated `updated_at` trigger functions.
* Row Level Security (RLS) policies enforcing backend privileged access (`service_role`) and read-only protocol access for anonymous clients.

---

## 5. Local-to-Cloud Migration Plan

### Table Migration Order (Strict FK Dependency Sequence):
```
1. experiments          (Root parent; protocols)
      |
      +---> 2. experiment_steps     (Ordered steps; depends on experiments)
      |
      +---> 3. experiment_sessions  (Sessions; depends on experiments)
                  |
                  +---> 4. sequence_events   (Validation logs; depends on sessions & steps)
                  |           |
                  |           +---> 6. alert_events (Alerts; depends on sessions & sequence_events)
                  |
                  +---> 5. detection_events  (AI perception; depends on sessions & steps)
                  |
                  +---> 7. session_artifacts (File references; depends on sessions)
                  |
                  +---> 8. system_events     (System events; depends on sessions)

9. system_settings      (Independent system configurations)
```

### Idempotency and Deduplication Strategy:
* **Experiments:** Upsert using `ON CONFLICT (name) DO UPDATE`.
* **Experiment Steps:** Upsert using `ON CONFLICT (experiment_id, step_number) DO UPDATE`.
* **Experiment Sessions:** Upsert using `ON CONFLICT (session_uuid) DO UPDATE`.
* **Sequence, Detection, & Alert Events:** Synced in atomic transaction blocks per session.
* **System Settings:** Upsert using `ON CONFLICT (setting_key) DO UPDATE`.

### Rollback & Disaster Recovery:
1. **Pre-Migration Snapshot:** Before executing any migration, `create_local_backup()` creates a timestamped copy: `auravision_backup_YYYYMMDD_HHMMSS.db`.
2. **Local Isolation:** SQLite remains completely active locally. If an upload or network failure occurs during batch sync, the local database is untouched, and the batch will resume from the last synced watermark upon reconnection.

---

## 6. Secure Configuration Management

### Environment Variables (.env):
```bash
# Offline Database (Active local engine)
DATABASE_URL=sqlite:///./data/auravision.db

# Future Supabase Ground-Station (Step 4: Disabled by default)
# SUPABASE_URL=https://your-project-id.supabase.co
# SUPABASE_ANON_KEY=eyJhbGci... (Public key, safe for frontend if needed)
# SUPABASE_SERVICE_ROLE_KEY=eyJhbGci... (Privileged secret: BACKEND ONLY, NEVER FRONTEND)
# SUPABASE_DB_URL=postgresql://postgres.your-project-id:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
# SUPABASE_SYNC_ENABLED=false
# SUPABASE_STORAGE_BUCKET_RECORDINGS=auravision-recordings
# SUPABASE_STORAGE_BUCKET_ARTIFACTS=auravision-artifacts
```

### Security Directives:
* **Never Expose `service_role`:** The Supabase `service_role` secret key bypasses Row Level Security and must **never** be exposed in client code, committed to Git, or sent over unencrypted channels.
* **Backend Gateway:** The frontend will communicate exclusively with the local FastAPI backend. Only the backend interacts with Supabase using authenticated credentials.
* **Zero Hardcoding:** No API keys, passwords, or cloud endpoints are hardcoded anywhere in the codebase.
