"""
Database setup for AURAVISION (SQLite Offline Storage)
Robust connection management with foreign key enforcement and automatic schema migrations.
"""
import os
import ssl
from pathlib import Path
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine
from app.core.config import settings


def normalize_db_url_and_args(url: str):
    """
    Ensure database URL and connection arguments are properly configured for the active engine.
    - For SQLite: check_same_thread=False
    - For PostgreSQL: auto-select pg8000 (pure-Python) or psycopg2, configure SSL context
    """
    if not url:
        return url, {}

    clean_url = url.strip()
    if clean_url.startswith("postgres://"):
        clean_url = "postgresql://" + clean_url[11:]

    is_sqlite = "sqlite" in clean_url.lower()
    connect_args = {}

    if is_sqlite:
        connect_args["check_same_thread"] = False
        return clean_url, connect_args

    # PostgreSQL / Supabase handling
    if clean_url.startswith("postgresql://"):
        try:
            import pg8000  # noqa: F401
            clean_url = "postgresql+pg8000://" + clean_url[13:]
        except ImportError:
            try:
                import psycopg2  # noqa: F401
                clean_url = "postgresql+psycopg2://" + clean_url[13:]
            except ImportError:
                pass

    if "pg8000" in clean_url:
        if "sslmode=" in clean_url:
            clean_url = clean_url.replace("?sslmode=require", "").replace("&sslmode=require", "").replace("sslmode=require", "")
            if clean_url.endswith("?"):
                clean_url = clean_url[:-1]
        try:
            connect_args["ssl_context"] = ssl.create_default_context()
        except Exception:
            pass
    else:
        if "sslmode" not in clean_url.lower():
            connect_args["sslmode"] = "require"

    return clean_url, connect_args


def normalize_db_url(url: str) -> str:
    """Return normalized URL string."""
    norm_url, _ = normalize_db_url_and_args(url)
    return norm_url


# Determine active dialect and resolved URL
active_db_url, connect_args = normalize_db_url_and_args(settings.DATABASE_URL)
is_sqlite = "sqlite" in active_db_url.lower()

engine_kwargs = {
    "connect_args": connect_args,
    "echo": settings.DEBUG
}

if not is_sqlite:
    # Production PostgreSQL / Supabase connection pool tuning
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_engine(active_db_url, **engine_kwargs)


# Enforce SQLite foreign key constraints (only on SQLite engines)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        # Check dialect via engine connection record or global setting
        if is_sqlite:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    except Exception:
        pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for obtaining a database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None):
    """
    Initialize database tables idempotently without dropping existing records.
    Automatically creates all tables, indexes, constraints, and migrates new columns.
    Portable across both SQLite and PostgreSQL engines.
    """
    settings.ensure_directories()
    from app.db import models  # noqa: F401
    active_engine = target_engine or engine
    Base.metadata.create_all(bind=active_engine)

    # Dialect-portable schema migration for newly added columns
    migrations = [
        ("system_events", "session_id", "INTEGER REFERENCES experiment_sessions(id) ON DELETE CASCADE"),
        ("experiment_steps", "validation_rules", "TEXT"),
        ("experiment_steps", "expected_duration_seconds", "INTEGER"),
        ("experiment_sessions", "session_name", "VARCHAR(255)"),
        ("experiment_sessions", "operator_label", "VARCHAR(100) DEFAULT 'Astronaut Specialist'"),
        ("experiment_sessions", "notes", "TEXT"),
        ("experiment_sessions", "updated_at", "DATETIME"),
        ("detection_events", "protocol_step_id", "INTEGER REFERENCES experiment_steps(id) ON DELETE SET NULL"),
        ("detection_events", "start_time_ms", "FLOAT"),
        ("detection_events", "end_time_ms", "FLOAT"),
        ("sequence_events", "protocol_step_id", "INTEGER REFERENCES experiment_steps(id) ON DELETE SET NULL"),
        ("sequence_events", "event_type", "VARCHAR(50)"),
        ("alert_events", "validation_event_id", "INTEGER REFERENCES sequence_events(id) ON DELETE SET NULL"),
        ("alert_events", "category", "VARCHAR(50) DEFAULT 'protocol'"),
        ("alert_events", "acknowledged_at", "DATETIME"),
    ]

    try:
        inspector = inspect(active_engine)
        existing_tables = set(inspector.get_table_names())
        
        with active_engine.connect() as conn:
            for table_name, col_name, col_def in migrations:
                if table_name in existing_tables:
                    try:
                        cols = [c["name"] for c in inspector.get_columns(table_name)]
                        if col_name not in cols:
                            conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")
                            conn.commit()
                    except Exception:
                        pass
    except Exception:
        pass
