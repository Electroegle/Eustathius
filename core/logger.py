"""
logger.py
---------
File-only logger for Eustathius.

stdout is intentionally excluded: Rich owns the terminal. All diagnostic
output goes to logs/eustathius.log (path from config.yaml).
"""

import logging
from pathlib import Path

from config_loader import config

_LOG_FILE = Path(config.get("log_file", "logs/eustathius.log"))
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)

_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)

logging.root.handlers.clear()          # remove any handler added before us
logging.root.addHandler(_handler)
logging.root.setLevel(_level)

logger = logging.getLogger("Eustathius")
