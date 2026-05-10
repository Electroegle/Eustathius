import hashlib
from datetime import datetime
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from config_loader import config
from core.logger import logger

CHROMA_PATH = Path(__file__).parent / ".." / config.get("memory",{}).get("chroma_persist_dir","memory_db")
CHROMA_PATH.mkdir(parents=True, exist_ok=True)

class VectorMemory:
    def __init__(self, collection_name="eustathius_memory"):
        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH.resolve()))
        self.embedder = SentenceTransformer(config["memory"]["embedding_model"])
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add_memory(self, text, metadata=None):
        if not text:
            return
        try:
            emb = self.embedder.encode(text).tolist()
            safe_metadata = self._safe_metadata(metadata)
            memory_id = self._memory_id(text)
            self.collection.upsert(
                embeddings=[emb],
                documents=[text],
                metadatas=[safe_metadata],
                ids=[memory_id],
            )
        except Exception as exc:
            logger.error(f"Vector memory add failed: {exc}")

    def search(self, query, top_k=3):
        if not query:
            return []
        try:
            q_emb = self.embedder.encode(query).tolist()
            count = self.collection.count()
            if count == 0:
                return []
            results = self.collection.query(query_embeddings=[q_emb], n_results=min(top_k, count))
            return results.get('documents', [[]])[0]
        except Exception as exc:
            logger.error(f"Vector memory search failed: {exc}")
            return []

    def _safe_metadata(self, metadata):
        safe = metadata.copy() if isinstance(metadata, dict) else {}
        safe.setdefault("source", "eustathius")
        safe.setdefault("kind", "memory")
        safe.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        return {str(key): value for key, value in safe.items() if value is not None}

    def _memory_id(self, text):
        digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        return f"mem-{digest[:24]}"
