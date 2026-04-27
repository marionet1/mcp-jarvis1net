from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from rag.config import get_rag_config


@dataclass
class RagChunk:
    doc_id: str
    chunk_id: str
    title: str
    content: str
    metadata: dict[str, Any]


class RagVectorStore:
    def __init__(self) -> None:
        self.cfg = get_rag_config()
        self.backend = self.cfg.backend
        self.collection = self.cfg.qdrant_collection
        self.ready = False
        self._qdrant_client = None
        self._vector_store = None
        self._embed_model = None
        self._index = None
        self._init_error = ""
        if self.backend == "qdrant":
            self._init_qdrant()

    def _init_qdrant(self) -> None:
        try:
            from llama_index.core import Settings, StorageContext, VectorStoreIndex
            from llama_index.embeddings.openai import OpenAIEmbedding
            from llama_index.vector_stores.qdrant import QdrantVectorStore
            from qdrant_client import QdrantClient
        except Exception as exc:  # pragma: no cover - dependency gate
            self._init_error = f"Missing RAG dependencies for qdrant backend: {exc}"
            return

        qdrant_url = self.cfg.qdrant_url
        qdrant_api_key = os.getenv("QDRANT_API_KEY", "").strip() or None
        embedding_model = self.cfg.embed_model
        openrouter_api_key = (
            os.getenv("RAG_EMBED_API_KEY", "").strip()
            or os.getenv("OPENROUTER_API_KEY", "").strip()
        )
        openrouter_base_url = self.cfg.openrouter_base_url

        if not openrouter_api_key:
            self._init_error = (
                "OPENROUTER_API_KEY (or RAG_EMBED_API_KEY) "
                "is required when RAG_BACKEND=qdrant."
            )
            return

        try:
            self._qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=20.0)
            self._vector_store = QdrantVectorStore(
                client=self._qdrant_client,
                collection_name=self.collection,
            )
            self._embed_model = OpenAIEmbedding(
                model=embedding_model,
                api_key=openrouter_api_key,
                api_base=openrouter_base_url,
            )
            Settings.embed_model = self._embed_model
            storage_context = StorageContext.from_defaults(vector_store=self._vector_store)
            self._index = VectorStoreIndex(nodes=[], storage_context=storage_context)
            self.ready = True
        except Exception as exc:  # pragma: no cover - runtime connectivity
            self._init_error = f"Failed to initialize qdrant backend: {exc}"
            self.ready = False

    @property
    def init_error(self) -> str:
        return self._init_error

    def upsert_chunks(self, chunks: list[RagChunk]) -> dict[str, Any]:
        if self.backend != "qdrant":
            return {"ok": True, "backend": self.backend, "upserted": 0, "note": "Vector backend disabled."}
        if not self.ready:
            return {"ok": False, "backend": self.backend, "error": self._init_error or "Vector backend not ready."}
        try:
            from llama_index.core import Document
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "backend": self.backend, "error": f"Unable to import LlamaIndex Document: {exc}"}

        documents = []
        for chunk in chunks:
            metadata = dict(chunk.metadata)
            metadata["doc_id"] = chunk.doc_id
            metadata["chunk_id"] = chunk.chunk_id
            metadata["title"] = chunk.title
            metadata["content"] = chunk.content
            documents.append(
                Document(
                    id_=chunk.chunk_id,
                    text=chunk.content,
                    metadata=metadata,
                )
            )
        try:
            from llama_index.core import StorageContext, VectorStoreIndex

            storage_context = StorageContext.from_defaults(vector_store=self._vector_store)
            VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                embed_model=self._embed_model,
                show_progress=False,
            )
            return {"ok": True, "backend": self.backend, "upserted": len(chunks), "collection": self.collection}
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "backend": self.backend, "error": f"Qdrant upsert failed: {exc}"}

    def search(
        self,
        query: str,
        top_k: int,
        metadata_filters: dict[str, str],
    ) -> dict[str, Any]:
        if self.backend != "qdrant":
            return {"ok": True, "backend": self.backend, "results": []}
        if not self.ready:
            return {"ok": False, "backend": self.backend, "error": self._init_error or "Vector backend not ready.", "results": []}
        try:
            from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, FilterOperator
            from llama_index.core.vector_stores.types import VectorStoreQuery
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "backend": self.backend, "error": f"Unable to import vector query types: {exc}", "results": []}

        filters = []
        for key, value in metadata_filters.items():
            if value:
                filters.append(MetadataFilter(key=key, operator=FilterOperator.EQ, value=value))
        metadata_obj = MetadataFilters(filters=filters) if filters else None
        try:
            embedding = self._embed_model.get_query_embedding(query)
            query_obj = VectorStoreQuery(
                query_embedding=embedding,
                similarity_top_k=max(1, min(top_k, 20)),
                filters=metadata_obj,
            )
            result = self._vector_store.query(query_obj)
            rows = []
            for idx, node in enumerate(result.nodes or []):
                score = 0.0
                if result.similarities and idx < len(result.similarities):
                    score = float(result.similarities[idx] or 0.0)
                meta = dict(node.metadata or {})
                rows.append(
                    {
                        "score": round(score, 6),
                        "doc_id": meta.get("doc_id", ""),
                        "chunk_id": meta.get("chunk_id", ""),
                        "tool_family": meta.get("tool_family", ""),
                        "tool_name": meta.get("tool_name", ""),
                        "doc_type": meta.get("doc_type", ""),
                        "provider": meta.get("provider", ""),
                        "source_url": meta.get("source_url", ""),
                        "title": meta.get("title", ""),
                        "snippet": str(getattr(node, "text", ""))[:600],
                    }
                )
            return {"ok": True, "backend": self.backend, "results": rows}
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "backend": self.backend, "error": f"Qdrant search failed: {exc}", "results": []}
