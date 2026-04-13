import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import pickle

# -----------------------------
# MODEL
# -----------------------------
model = SentenceTransformer("all-mpnet-base-v2")

def embed(text):
    v = model.encode([text])[0]
    return (v / np.linalg.norm(v)).astype("float32")


# -----------------------------
# CACHE
# -----------------------------
class FaissCache:

    def __init__(self, dim=384):
        self.dim = dim

        # default empty
        self.index = faiss.IndexFlatIP(dim)
        self.id_to_data = {}
        self.next_id = 0

        # load if exists
        self.load()

    # -------------------------
    # SAVE
    # -------------------------
    def save(self):
        faiss.write_index(self.index, "faiss.index")

        with open("meta.pkl", "wb") as f:
            pickle.dump({
                "id_to_data": self.id_to_data,
                "next_id": self.next_id
            }, f)

    # -------------------------
    # LOAD
    # -------------------------
    def load(self):
        if os.path.exists("faiss.index"):
            self.index = faiss.read_index("faiss.index")

        if os.path.exists("meta.pkl"):
            with open("meta.pkl", "rb") as f:
                data = pickle.load(f)
                self.id_to_data = data["id_to_data"]
                self.next_id = data["next_id"]

    # -------------------------
    # ADD
    # -------------------------
    def add(self, company, question, answer):
        vec = embed(question)

        self.index.add(vec.reshape(1, -1))

        self.id_to_data[self.next_id] = {
            "company": company,
            "question": question,
            "answer": answer
        }

        self.next_id += 1
        self.save() 

    # -------------------------
    # SEARCH
    # -------------------------
    def search(self, company, query, threshold=0.75, top_k=10):

        if self.index.ntotal == 0:
            return None

        q = embed(query).reshape(1, -1)

        D, I = self.index.search(q, top_k * 10)

        candidates = []

        for score, idx in zip(D[0], I[0]):
            if idx == -1:
                continue

            data = self.id_to_data.get(idx)
            if not data:
                continue

            if data["company"] == company:
                candidates.append((idx, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)

        best_id, best_score = candidates[0]

        if best_score >= threshold:
            return {
                "answer": self.id_to_data[best_id]["answer"],
                "score": float(best_score)
            }

        return None


# -----------------------------
# USAGE
# -----------------------------
cache = FaissCache()


# def ask(company, question):

#     result = cache.search(company, question)

#     if result:
#         print("CACHE HIT")
#         return result["answer"]

#     print("CACHE MISS")

#     answer = f"LLM answer for: {question}"

#     cache.add(company, question, answer)

#     return answer


# # -----------------------------
# # TEST
# # -----------------------------
# print(ask("123", "What is company status?"))
# print(ask("123", "What is the status of company?"))
# print(ask("456", "What is company status?"))