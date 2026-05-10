import re

from config_loader import config


class SafetyFilter:
    def __init__(self):
        self.enabled = config.get("safety", {}).get("enabled", True)
        self.keywords = config.get("safety", {}).get("filter_keywords", [])
        if not self.keywords:
            self.keywords = ["kill yourself", "bomb", "illegal", "hack the government"]

    def check(self, text: str):
        if not self.enabled: return True, text
        for kw in self.keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
                return False, f"Content blocked: {kw}"
        return True, text

    def filter(self, text): ok, filtered = self.check(text); return filtered if ok else "[Blocked]"
