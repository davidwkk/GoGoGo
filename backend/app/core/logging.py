import os

# Set timezone to Hong Kong BEFORE importing loguru
os.environ.setdefault("TZ", "Asia/Hong_Kong")

import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    logger.remove()

    # Console sink (stdout) - human-readable (HKT timezone via TZ env var)
    logger.add(
        sys.stdout,
        colorize=True,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )

    logs_path = Path(__file__).parent.parent / "logs"
    logs_path.mkdir(exist_ok=True)

    # File sink for all logs - human-readable (HKT timezone via TZ env var)
    logger.add(
        logs_path / "app.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    )

    # Separate file sink for errors only (HKT timezone via TZ env var)
    logger.add(
        logs_path / "error.log",
        rotation="10 MB",
        retention="7 days",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    )


# Setup logging immediately at import time (before any other modules log)
setup_logging()
