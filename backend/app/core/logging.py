import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    logger.remove()

    # Console sink (stdout) - human-readable
    logger.add(
        sys.stdout,
        colorize=True,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )

    logs_path = Path(__file__).parent.parent / "logs"
    logs_path.mkdir(exist_ok=True)

    # File sink for all logs - human-readable, with multiprocessing support
    logger.add(
        logs_path / "app.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        enqueue=True,  # Required for multiprocessing safety
    )

    # Separate file sink for errors only
    logger.add(
        logs_path / "error.log",
        rotation="10 MB",
        retention="7 days",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        enqueue=True,
    )


# Setup logging immediately at import time (before any other modules log)
setup_logging()
