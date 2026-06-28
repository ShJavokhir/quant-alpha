"""Agent memory: Voyage embeddings + a store with MongoDB-Atlas and local backends.

The store keeps three logical collections:
  * alphas       — every alpha ever born (live or dead), with its embedding + history
  * experiments  — every proposal + verdict (the data behind the memory-ablation chart)
  * events       — a flat journal of what happened each generation (for the UI feed)

MongoDB Atlas is used when reachable (sponsor path, Atlas Vector Search supported);
otherwise a local JSON-backed store with numpy cosine search is used so the demo is
fully offline-capable. Both expose the same interface. Embeddings are cached on disk
so replays cost zero Voyage tokens.
"""
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from .. import config

config.load_env()

# ----------------------------- embeddings -----------------------------
_EMBED_CACHE_FILE = config.DATA / "embed_cache.json"


class Embedder:
    """Voyage embeddings with a persistent on-disk cache (sha1(text) -> vector)."""

    def __init__(self, model=config.VOYAGE_MODEL):
        self.model = model
        self._cache = {}
        if _EMBED_CACHE_FILE.exists():
            try:
                self._cache = json.loads(_EMBED_CACHE_FILE.read_text())
            except Exception:
                self._cache = {}
        self._client = None
        self._dirty = False

    def _voyage(self):
        if self._client is None:
            import voyageai
            self._client = voyageai.Client(api_key=config.os.environ.get("VOYAGE_API_KEY"))
        return self._client

    @staticmethod
    def _key(text):
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def embed(self, texts, input_type="document"):
        if isinstance(texts, str):
            texts = [texts]
        out = [None] * len(texts)
        missing, miss_idx = [], []
        for i, t in enumerate(texts):
            k = self._key(t)
            if k in self._cache:
                out[i] = self._cache[k]
            else:
                missing.append(t)
                miss_idx.append(i)
        if missing:
            vecs = self._voyage().embed(missing, model=self.model, input_type=input_type).embeddings
            for j, i in enumerate(miss_idx):
                out[i] = vecs[j]
                self._cache[self._key(texts[i])] = vecs[j]
            self._dirty = True
            self.flush()
        return np.asarray(out, dtype=np.float32)

    def embed_one(self, text, input_type="document"):
        return self.embed([text], input_type)[0]

    def flush(self):
        if self._dirty:
            _EMBED_CACHE_FILE.write_text(json.dumps(self._cache))
            self._dirty = False


def alpha_text(formula, family="", rationale=""):
    """The text we embed for an alpha — formula dominates, with light context."""
    return f"family: {family}\nrationale: {rationale}\nformula: {formula}"


def _cosine(mat: np.ndarray, vec: np.ndarray) -> np.ndarray:
    if len(mat) == 0:
        return np.array([])
    mn = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)
    vn = vec / (np.linalg.norm(vec) + 1e-12)
    return mn @ vn


# ----------------------------- stores -----------------------------
class LocalStore:
    backend = "local"

    def __init__(self, run_id):
        self.run_id = run_id
        self.dir = config.RUNS / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.alphas = {}        # name -> doc
        self.experiments = []   # list of docs
        self.events = []        # list of docs
        self._emb_mat = None
        self._emb_names = []

    # --- alphas ---
    def upsert_alpha(self, doc):
        self.alphas[doc["name"]] = doc
        self._emb_mat = None

    def get_alpha(self, name):
        return self.alphas.get(name)

    def all_alphas(self, status=None):
        vals = list(self.alphas.values())
        return [a for a in vals if status is None or a.get("status") == status]

    def _rebuild_emb(self, status=None):
        docs = self.all_alphas(status)
        mat, names = [], []
        for d in docs:
            if d.get("embedding") is not None:
                mat.append(d["embedding"]); names.append(d["name"])
        self._emb_mat = np.asarray(mat, dtype=np.float32) if mat else np.zeros((0, config.EMBED_DIM))
        self._emb_names = names

    def search_similar(self, embedding, k=5, status=None, exclude=None):
        self._rebuild_emb(status)
        if len(self._emb_names) == 0:
            return []
        sims = _cosine(self._emb_mat, np.asarray(embedding, dtype=np.float32))
        order = np.argsort(-sims)
        res = []
        for i in order:
            name = self._emb_names[i]
            if exclude and name in exclude:
                continue
            res.append((self.alphas[name], float(sims[i])))
            if len(res) >= k:
                break
        return res

    # --- experiments / events ---
    def log_experiment(self, doc):
        self.experiments.append(doc)

    def log_event(self, doc):
        self.events.append(doc)

    def flush(self):
        (self.dir / "alphas.json").write_text(json.dumps(list(self.alphas.values()), default=_je))
        (self.dir / "experiments.json").write_text(json.dumps(self.experiments, default=_je))
        (self.dir / "events.json").write_text(json.dumps(self.events, default=_je))


class MongoStore:
    backend = "mongo"

    def __init__(self, run_id, client):
        self.run_id = run_id
        self.db = client["alpha_evolution"]
        self.c_alphas = self.db["alphas"]
        self.c_exp = self.db["experiments"]
        self.c_evt = self.db["events"]
        self._local_mirror = LocalStore(run_id)  # also keep a local copy for offline replay

    def _q(self, extra=None):
        q = {"run_id": self.run_id}
        if extra:
            q.update(extra)
        return q

    def upsert_alpha(self, doc):
        doc = {**doc, "run_id": self.run_id}
        self.c_alphas.replace_one(self._q({"name": doc["name"]}), doc, upsert=True)
        self._local_mirror.upsert_alpha(doc)

    def get_alpha(self, name):
        return self.c_alphas.find_one(self._q({"name": name}))

    def all_alphas(self, status=None):
        q = self._q({"status": status} if status else None)
        return list(self.c_alphas.find(q))

    def search_similar(self, embedding, k=5, status=None, exclude=None):
        # Try Atlas $vectorSearch; fall back to local cosine on the mirror.
        try:
            pipeline = [{
                "$vectorSearch": {
                    "index": "alpha_vec", "path": "embedding",
                    "queryVector": list(map(float, embedding)),
                    "numCandidates": 200, "limit": k + (len(exclude) if exclude else 0),
                    "filter": self._q({"status": status} if status else None),
                }
            }, {"$addFields": {"_score": {"$meta": "vectorSearchScore"}}}]
            res = list(self.c_alphas.aggregate(pipeline))
            if res:
                out = []
                for d in res:
                    if exclude and d.get("name") in exclude:
                        continue
                    out.append((d, float(d.get("_score", 0.0))))
                return out[:k]
        except Exception:
            pass
        self._local_mirror.alphas = {a["name"]: a for a in self.all_alphas()}
        self._local_mirror._emb_mat = None
        return self._local_mirror.search_similar(embedding, k, status, exclude)

    def log_experiment(self, doc):
        doc = {**doc, "run_id": self.run_id}
        self.c_exp.insert_one(dict(doc))
        self._local_mirror.log_experiment(doc)

    def log_event(self, doc):
        doc = {**doc, "run_id": self.run_id}
        self.c_evt.insert_one(dict(doc))
        self._local_mirror.log_event(doc)

    def flush(self):
        self._local_mirror.flush()


def _je(o):
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def open_memory(run_id, prefer_mongo=True, timeout_ms=6000):
    """Return (store, backend_name). Tries Atlas; falls back to local."""
    if prefer_mongo:
        uri = config.os.environ.get("MONGO_URI")
        if uri:
            try:
                from pymongo import MongoClient
                cli = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
                cli.admin.command("ping")
                return MongoStore(run_id, cli), "mongo"
            except Exception as e:  # noqa: BLE001
                print(f"[memory] Atlas unreachable ({type(e).__name__}); using local store.")
    return LocalStore(run_id), "local"
