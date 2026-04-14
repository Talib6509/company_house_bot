import os
import os 
import warnings 
import logging 
import streamlit as st
# ---- Transformers ---- 
os.environ["TRANSFORMERS_VERBOSITY"] = "error" 
# ---- Python warnings ---- 
warnings.filterwarnings("ignore") 
# ---- Disable logging globally ---- 
logging.disable(logging.CRITICAL)


import hashlib
from sentence_transformers import SentenceTransformer
from upstash_vector import Index
from dotenv import load_dotenv
from functools import lru_cache


@st.cache_resource
def load_model():
    return SentenceTransformer("all-mpnet-base-v2")

load_dotenv()

model = load_model()


@lru_cache(maxsize=256)
def embed(text):
    return model.encode(text, normalize_embeddings=True).tolist()

def make_id(company: str, question: str) -> str:
    return hashlib.md5(
        f"{company}:{question.strip().lower()}".encode()
    ).hexdigest()

index = Index(
    url=os.getenv("UPSTASH_VECTOR_REST_URL"),
    token=os.getenv("UPSTASH_VECTOR_REST_TOKEN")
)


class UpstashVectorCache:

    def add(self, company, question, answer):
        print(f"\nAdding to cache index company={company!r}  question={question!r}")

        vec = embed(question)
        vector_id = make_id(company, question)

        index.upsert(
            namespace=company,
            vectors=[{
                "id":       vector_id,
                "vector":   vec,
                "metadata": {
                    "question":      question,
                    "question_norm": question.strip().lower(),
                    "answer":        answer
                }
            }]
        )

    def search(self, company, query, threshold=0.95, top_k=5):
        print(f"\nSearching in cache vector: query={query!r}  company={company!r}")

        vec = embed(query)

        results = index.query(
            namespace=company,
            vector=vec,
            top_k=top_k,
            include_metadata=True
        )

        if not results:
            print("SEARCH No results returned.")
            return None

        for result in results:
            score = result.score
            meta  = result.metadata

            print(f"  score={score:.4f}  question_norm={meta.get('question_norm')!r}")

            if score >= threshold:
                print(f"SEARCH: Cache hit! score={score:.4f}")
                return {
                    "answer": meta["answer"],
                    "score":  float(score)
                }

        print("SEARCH: Cache miss.")
        return None


cache = UpstashVectorCache()
