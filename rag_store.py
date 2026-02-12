from __future__ import annotations
import os
import shutil
from functools import lru_cache
from typing import List, Dict

import chromadb
from chromadb.config import Settings

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

PERSIST_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION = "research_notes"


@lru_cache(maxsize=1)
def _embeddings():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def _chroma_client():
    # Explicit embedded client + persistence avoids tenant issues
    return chromadb.PersistentClient(
        path=PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )


@lru_cache(maxsize=1)
def get_vectorstore():
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=_embeddings(),
        client=_chroma_client(),
    )


def reset_db():
    # Handy if you want to wipe memory
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR, ignore_errors=True)
    _chroma_client.cache_clear()
    get_vectorstore.cache_clear()
    _embeddings.cache_clear()


def add_note(text: str, source: str, query: str | None = None):
    vs = get_vectorstore()
    meta = {"source": source}
    if query:
        meta["query"] = query
    vs.add_texts([text], metadatas=[meta])


def retrieve(query: str, k: int = 4) -> List[Dict]:
    vs = get_vectorstore()
    docs = vs.similarity_search(query, k=k)
    return [{"content": d.page_content, "source": d.metadata.get("source", "memory")} for d in docs]
