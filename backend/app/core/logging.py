import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        colorize=True,
        level=settings.LOG_LEVEL,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    logs_path = Path(__file__).parent.parent / "logs"
    logs_path.mkdir(exist_ok=True)
    logger.add(
        logs_path / "app.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        serialize=True,
    )
