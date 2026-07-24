"""RAG — Retrieval-Augmented Generation com ChromaDB e sentence-transformers.

Carrega todos os arquivos Markdown de backend/knowledge/ para um banco vetorial
local. Na análise, recupera os trechos mais relevantes dado os componentes e
categorias STRIDE detectados.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from backend.config import (
    CHROMA_DB_DIR,
    KNOWLEDGE_DIR,
    RAG_COLLECTION_NAME,
    RAG_EMBEDDING_MODEL,
    RAG_TOP_K,
)

_embedding_model: SentenceTransformer | None = None
_embedding_error: str | None = None
_chroma_client: chromadb.Client | None = None
_collection = None
_lexical_chunks: list[dict] = []


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        print(f"[rag] Loading embedding model {RAG_EMBEDDING_MODEL} ...")
        _embedding_model = SentenceTransformer(RAG_EMBEDDING_MODEL)
        print("[rag] Embedding model ready.")
    return _embedding_model


def _get_collection():
    global _chroma_client, _collection
    if _collection is not None:
        return _collection
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(
        path=str(CHROMA_DB_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    _collection = _chroma_client.get_or_create_collection(
        name=RAG_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def _chunk_markdown(text: str, source: str) -> list[dict]:
    """Divide um documento Markdown em chunks por parágrafo/seção."""
    chunks = []
    current_section = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("## ") or line.startswith("### "):
            if current_lines:
                content = "\n".join(current_lines).strip()
                if len(content) > 80:
                    chunks.append({"text": content, "section": current_section, "source": source})
            current_section = line.lstrip("# ").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if len(content) > 80:
            chunks.append({"text": content, "section": current_section, "source": source})

    return chunks


def _load_knowledge_chunks() -> list[dict]:
    global _lexical_chunks
    if _lexical_chunks:
        return _lexical_chunks
    if not KNOWLEDGE_DIR.exists():
        return []
    chunks: list[dict] = []
    for md_file in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        source = md_file.relative_to(KNOWLEDGE_DIR).as_posix()
        chunks.extend(_chunk_markdown(md_file.read_text(encoding="utf-8"), source))
    _lexical_chunks = chunks
    return chunks


def _normalize_terms(value: str) -> list[str]:
    normalized = re.sub(r"[_/-]+", " ", value.lower())
    return re.findall(r"[a-z0-9]+", normalized)


def _query_lexical(query_parts: list[str], top_k: int) -> list[str]:
    phrases = [" ".join(_normalize_terms(part)) for part in query_parts]
    phrases = [phrase for phrase in phrases if phrase]
    query_terms = {term for phrase in phrases for term in phrase.split()}
    ranked: list[tuple[float, int, dict]] = []
    for index, chunk in enumerate(_load_knowledge_chunks()):
        searchable = " ".join((chunk["source"], chunk["section"], chunk["text"]))
        normalized = " ".join(_normalize_terms(searchable))
        tokens = set(normalized.split())
        phrase_hits = sum(1 for phrase in phrases if phrase in normalized)
        term_hits = len(query_terms & tokens)
        score = phrase_hits * 4.0 + term_hits
        if score > 0:
            ranked.append((score, -index, chunk))
    ranked.sort(reverse=True, key=lambda item: (item[0], item[1]))
    docs = []
    for _, _, chunk in ranked[:top_k]:
        header = f"[{chunk['source']}] {chunk['section']}".strip()
        docs.append(f"**{header}**\n{chunk['text']}")
    return docs


def _doc_id(source: str, index: int, text: str) -> str:
    key = f"{source}:{index}:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def initialize_rag() -> None:
    """Carrega a knowledge base no ChromaDB. Seguro para chamar múltiplas vezes."""
    global _embedding_error
    collection = _get_collection()
    chunks = _load_knowledge_chunks()
    if not chunks:
        print("[rag] Knowledge directory not found — skipping RAG initialization.")
        return
    try:
        model = _get_embedding_model()
        _embedding_error = None
    except Exception as exc:
        _embedding_error = type(exc).__name__
        print(f"[rag] Embedding model unavailable ({_embedding_error}); lexical fallback ready.")
        return

    all_texts: list[str] = []
    all_ids: list[str] = []
    all_metas: list[dict] = []

    source_counts: dict[str, int] = {}
    for chunk in chunks:
        source = chunk["source"]
        index = source_counts.get(source, 0)
        source_counts[source] = index + 1
        doc_id = _doc_id(source, index, chunk["text"])
        all_ids.append(doc_id)
        all_texts.append(chunk["text"])
        all_metas.append({"source": source, "section": chunk["section"]})

    if not all_ids:
        print("[rag] No chunks generated from knowledge files.")
        return

    desired_ids = set(all_ids)
    existing = set(collection.get()["ids"])
    stale_ids = sorted(existing - desired_ids)
    if stale_ids:
        collection.delete(ids=stale_ids)
        print(f"[rag] Removed {len(stale_ids)} stale chunks.")

    new_ids = [item_id for item_id in all_ids if item_id not in existing]
    if not new_ids:
        print(f"[rag] All {len(all_ids)} chunks already indexed.")
        return

    new_texts = [t for i, t in zip(all_ids, all_texts) if i in new_ids]
    new_metas = [m for i, m in zip(all_ids, all_metas) if i in new_ids]

    print(f"[rag] Indexing {len(new_ids)} new chunks ...")
    embeddings = model.encode(new_texts, show_progress_bar=False).tolist()
    collection.add(ids=new_ids, embeddings=embeddings, documents=new_texts, metadatas=new_metas)
    print(f"[rag] RAG ready — {collection.count()} total chunks in collection.")


def query(
    component_types: list[str],
    stride_categories: list[str] | None = None,
    top_k: int = RAG_TOP_K,
) -> list[str]:
    """Recupera os trechos mais relevantes para os componentes e categorias STRIDE."""
    query_parts = component_types[:]
    if stride_categories:
        query_parts.extend(stride_categories)

    query_text = " ".join(query_parts).strip()
    if not query_text:
        return []
    collection = _get_collection()
    try:
        model = _get_embedding_model()
        if collection.count() == 0:
            return _query_lexical(query_parts, top_k)
        query_embedding = model.encode([query_text], show_progress_bar=False)[0].tolist()
    except Exception:
        return _query_lexical(query_parts, top_k)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas"],
    )

    docs: list[str] = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        source_label = meta.get("source", "knowledge")
        section_label = meta.get("section", "")
        header = f"[{source_label}] {section_label}".strip()
        docs.append(f"**{header}**\n{doc}")

    return docs


def status() -> dict:
    collection = _get_collection()
    lexical_count = len(_load_knowledge_chunks())
    vector_ready = collection.count() > 0 and _embedding_model is not None
    return {
        "ready": vector_ready or lexical_count > 0,
        "chunks": max(collection.count(), lexical_count),
        "embeddingModel": RAG_EMBEDDING_MODEL,
        "retrievalMode": "vector" if vector_ready else "lexical",
        "embeddingError": _embedding_error,
        "contentAddressedIds": True,
    }
