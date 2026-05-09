import yaml
from pathlib import Path
_config_path = Path(__file__).parent / "config.yaml"
_cfg = None
def load_config():
    global _cfg
    if _cfg is None:
        with open(_config_path) as f:
            _cfg = yaml.safe_load(f)
    return _cfg
config = load_config()
