import os
from loguru import logger

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger.remove()
logger.add(
    os.path.join(LOG_DIR, "yuki.log"),
    rotation="10 MB", retention=7, level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
)
logger.add(
    lambda m: print(m, end=""),
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {name} - {message}",
    colorize=True,
)

__all__ = ["logger"]
