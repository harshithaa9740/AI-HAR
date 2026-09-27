"""
Database setup for AURAVISION (SQLite Offline Storage)
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine
from app.core.config import settings

# Safe SQLite connection arguments for multithreaded offline operation
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG
)


# Enforce SQLite foreign key constraints
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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
    Automatically ensures the required storage directory exists and migrates new columns.
    """
    settings.ensure_directories()
    from app.db import models  # noqa: F401
    active_engine = target_engine or engine
    Base.metadata.create_all(bind=active_engine)

    # Lightweight SQLite schema migration for newly added columns
    try:
        with active_engine.connect() as conn:
            # Check system_events.session_id
            cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(system_events)").fetchall()]
            if "session_id" not in cols and len(cols) > 0:
                conn.exec_driver_sql("ALTER TABLE system_events ADD COLUMN session_id INTEGER REFERENCES experiment_sessions(id) ON DELETE CASCADE")
                conn.commit()
    except Exception:
        pass

