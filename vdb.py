import os
import warnings
import logging

# ---- Transformers ----
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

# ---- Python warnings ----
warnings.filterwarnings("ignore")

# ---- Disable logging globally ----
logging.disable(logging.CRITICAL)


import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os
import pickle

import warnings
warnings.filterwarnings("ignore")

# -----------------------------
# MODEL
# -----------------------------
model = SentenceTransformer("all-mpnet-base-v2")

def embed(text):
    return model.encode(text, normalize_embeddings=True).astype("float32")


# -----------------------------
# CACHE
# -----------------------------
class FaissCache:

    def __init__(self):
        self.dim = model.get_embedding_dimension()
        self._reset()
        self.load()

    def _reset(self):
        self.index = faiss.IndexFlatIP(self.dim)
        self.id_to_data = {}   # faiss_row_id -> {company, question, answer}
        self.next_id = 0

    # -------------------------
    def save(self):
        faiss.write_index(self.index, "faiss.index")
        with open("meta.pkl", "wb") as f:
            pickle.dump({
                "id_to_data": self.id_to_data,
                "next_id": self.next_id
            }, f)

    # -------------------------
    def load(self):
        index_ok = os.path.exists("faiss.index")
        meta_ok  = os.path.exists("meta.pkl")

        # Both files must exist and be consistent — otherwise start fresh
        if not (index_ok and meta_ok):
            print("[LOAD] Missing files, starting fresh.")
            return

        index = faiss.read_index("faiss.index")

        if index.d != self.dim:
            print("[LOAD] Dimension mismatch, starting fresh.")
            return

        with open("meta.pkl", "rb") as f:
            data = pickle.load(f)

        # Sanity-check: FAISS vector count must match our metadata count
        if index.ntotal != data["next_id"]:
            print(
                f"[LOAD] ID mismatch: faiss has {index.ntotal} vectors "
                f"but next_id={data['next_id']}. Starting fresh."
            )
            return

        self.index    = index
        self.id_to_data = data["id_to_data"]
        self.next_id  = data["next_id"]
        print(f"[LOAD] Loaded {self.index.ntotal} entries from disk.")

    # -------------------------
    def add(self, company, question, answer):
        print(f"\n[ADD] company={company!r}  question={question!r}")
        vec = embed(question).reshape(1, -1)

        self.index.add(vec)                          # FAISS assigns row = next_id
        self.id_to_data[self.next_id] = {
            "company":  company,
            "question": question,
            "answer":   answer
        }
        self.next_id += 1
        self.save()
        print(f"[ADD] Cache now has {self.index.ntotal} entries.")

    # -------------------------
    def search(self, company, query, threshold=0.75, top_k=5):
        if self.index.ntotal == 0:
            print("[SEARCH] Index is empty.")
            return None

        q = embed(query).reshape(1, -1)

        # Fetch enough results to have top_k hits after company filtering
        fetch_k = min(self.index.ntotal, top_k * 10)
        D, I = self.index.search(q, fetch_k)

        print(f"\n[SEARCH] query={query!r}  company={company!r}")
        print(f"[SEARCH] Raw FAISS results (idx, score):")

        best_score, best_id = -1, None

        for score, idx in zip(D[0], I[0]):
            if idx == -1:
                continue

            data = self.id_to_data.get(idx)
            if data is None:
                # This would indicate the ID sync bug — log it clearly
                print(f"  idx={idx}  score={score:.4f}  !! NOT IN id_to_data !!")
                continue

            print(f"  idx={idx}  score={score:.4f}  company={data['company']!r}"
                  f"  q={data['question']!r}")

            if data["company"] != company:
                continue

            if score > best_score:
                best_score, best_id = score, idx

        if best_id is None:
            print("[SEARCH] No candidates after company filter.")
            return None

        print(f"[SEARCH] Best match: score={best_score:.4f}  threshold={threshold}")

        if best_score >= threshold:
            return {
                "answer": self.id_to_data[best_id]["answer"],
                "score":  float(best_score)
            }

        print("[SEARCH] Below threshold — cache miss.")
        return None


cache = FaissCache()
