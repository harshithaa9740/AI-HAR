"""
Logging configuration for AURAVISION Offline System
"""
import sys
import logging
from pathlib import Path
from app.core.config import LOGS_DIR, settings


def setup_logger(name: str = "auravision") -> logging.Logger:
    """Setup structured logger with console and file handlers."""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # Local file handler
    log_file_path = LOGS_DIR / "system.log"
    file_handler = logging.FileHandler(str(log_file_path), encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
