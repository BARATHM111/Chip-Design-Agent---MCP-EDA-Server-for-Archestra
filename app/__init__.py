"""
MCP EDA Server — Application Package

Configures structured logging on import.
"""

import logging
import sys

from .config import LOG_LEVEL

logging.basicConfig(
    stream=sys.stderr,
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
