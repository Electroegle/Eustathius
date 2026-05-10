import json
from pathlib import Path

from config_loader import config

OPT_DIR = Path(config.get("prompt_optimizer", {}).get("store_dir", "~/.eustathius_optimized_prompts")).expanduser()
OPT_DIR.mkdir(parents=True, exist_ok=True)
OPT_FILE = OPT_DIR / "optimized.json"

class PromptOptimizer:
    def __init__(self):
        self.data = json.loads(OPT_FILE.read_text()) if OPT_FILE.exists() else {}

    def get_optimized_prompt(self, skill_name, default_prompt):
        return self.data.get(skill_name, default_prompt)

    def update_from_feedback(self, skill_name, original_prompt, improvement):
        self.data[skill_name] = original_prompt
        OPT_FILE.write_text(json.dumps(self.data, indent=2))
