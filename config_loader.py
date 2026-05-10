"""
config_loader.py
----------------
Loads config.yaml from the project root.

The module-level `config` dict is the single shared reference used throughout
the codebase. When agent.reload_config() calls importlib.reload(config_loader),
this module re-executes, _cfg is reset, and the file is re-read.

Note: modules that imported `from config_loader import config` keep the old
reference until they re-import. Use `import config_loader; config_loader.config`
for hot-reload correctness in long-lived components.
"""

import sys
from pathlib import Path

import yaml

_config_path = Path(__file__).parent / "config.yaml"
_cfg = None


def load_config() -> dict:
    global _cfg
    _cfg = None  # always re-read (supports reload)
    if not _config_path.exists():
        print(
            f"[Eustathius] ERROR: config.yaml not found at {_config_path}\n"
            "Copy config.yaml into the project root and restart.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        with open(_config_path, encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        print(
            f"[Eustathius] ERROR: config.yaml is invalid YAML:\n{exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    if not isinstance(loaded, dict):
        print(
            "[Eustathius] ERROR: config.yaml must be a YAML mapping.",
            file=sys.stderr,
        )
        sys.exit(1)
    return loaded


config = load_config()
