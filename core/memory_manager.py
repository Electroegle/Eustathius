import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from config_loader import config


class MemoryManager:
    def __init__(self):
        self.embedder = SentenceTransformer(config["memory"]["embedding_model"])
        self.store_dir = Path(config["memory"]["store_dir"]).expanduser()
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.store_dir / "memory.json"
        self.memory = self._load()

    def _load(self): return json.loads(self.memory_file.read_text()) if self.memory_file.exists() else []
    def _save(self): self.memory_file.write_text(json.dumps(self.memory, indent=2))

    def add_interaction(self, user, assistant, rating=None):
        emb = self.embedder.encode(user).tolist()
        self.memory.append({"user":user,"assistant":assistant,"embedding":emb,"rating":rating})
        max_depth = config["memory"].get("history_depth",20)
        if len(self.memory) > max_depth: self.memory = self.memory[-max_depth:]
        self._save()

    def retrieve_relevant(self, query, top_k=3):
        if not self.memory: return []
        qvec = self.embedder.encode(query)
        scores = []
        for mem in self.memory:
            mvec = np.array(mem["embedding"])
            sim = np.dot(qvec, mvec) / (np.linalg.norm(qvec)*np.linalg.norm(mvec)+1e-8)
            scores.append((mem, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
