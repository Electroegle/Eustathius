import logging, sys
from pathlib import Path
from config_loader import config
LOG_FILE = Path(config.get("log_file", "logs/eustathius.log"))
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
logging.basicConfig(level=level,format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    handlers=[logging.FileHandler(LOG_FILE),logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("Eustathius")
