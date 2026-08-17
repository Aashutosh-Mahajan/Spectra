import os
import json
import logging
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from backend.utils.chunker import chunk_file
from backend.utils.file_router import is_crucial_or_sensitive_file

logger = logging.getLogger(__name__)

class RAGContextManager:
    """
    Manages hybrid dense (FAISS/OpenAI) and sparse (BM25) codebase retrieval.
    Builds the indices once per repo and caches them locally to save API costs.
    """
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.store_dir = os.path.join(repo_path, ".spectra", "rag_store")
        self.bm25_cache_path = os.path.join(self.store_dir, "bm25_corpus.json")
        self.faiss_dir = os.path.join(self.store_dir, "faiss_index")

        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self.vectorstore: FAISS | None = None
        self.bm25: BM25Okapi | None = None
        self.documents: List[Document] = []

    def build_or_load_index(self, file_map: dict[str, list[str]]):
        """Builds the RAG index if it doesn't exist, otherwise loads from disk."""
        os.makedirs(self.store_dir, exist_ok=True)

        if os.path.exists(self.faiss_dir) and os.path.exists(self.bm25_cache_path):
            logger.info("Loading existing RAG indices from disk...")
            try:
                self.vectorstore = FAISS.load_local(self.faiss_dir, self.embeddings, allow_dangerous_deserialization=True)
                with open(self.bm25_cache_path, "r", encoding="utf-8") as f:
                    doc_dicts = json.load(f)
                    self.documents = [Document(**d) for d in doc_dicts]

                tokenized_corpus = [doc.page_content.lower().split(" ") for doc in self.documents]
                self.bm25 = BM25Okapi(tokenized_corpus)
                logger.info(f"Loaded {len(self.documents)} indexed chunks.")
                return
            except Exception as e:
                logger.warning(f"Failed to load existing RAG indices: {e}. Rebuilding...")

        logger.info("Building new RAG indices...")
        self._build_index(file_map)

    def _build_index(self, file_map: dict[str, list[str]]):
        """Reads all routed files, chunks them, and builds indices."""
        all_rel_paths = set()
        for files in file_map.values():
            all_rel_paths.update(files)

        documents = []
        for rel_path in all_rel_paths:
            if is_crucial_or_sensitive_file(rel_path):
                logger.warning(f"Skipping sensitive/crucial file {rel_path} from RAG index")
                continue

            abs_path = os.path.join(self.repo_path, rel_path)
            if is_crucial_or_sensitive_file(abs_path):
                continue

            # Use smaller chunks for retrieval context (approx 500 tokens)
            chunks = chunk_file(abs_path, max_tokens=500, overlap_tokens=50)

            for chunk in chunks:
                doc = Document(
                    page_content=chunk["content"],
                    metadata={
                        "source": rel_path,
                        "start_line": chunk["start_line"],
                        "end_line": chunk["end_line"]
                    }
                )
                documents.append(doc)

        if not documents:
            logger.warning("No documents to index.")
            return

        self.documents = documents

        # 1. Build FAISS (Dense)
        logger.info(f"Generating embeddings for {len(documents)} chunks...")
        self.vectorstore = FAISS.from_documents(documents, self.embeddings)
        self.vectorstore.save_local(self.faiss_dir)

        # 2. Build BM25 (Sparse)
        tokenized_corpus = [doc.page_content.lower().split(" ") for doc in documents]
        self.bm25 = BM25Okapi(tokenized_corpus)

        with open(self.bm25_cache_path, "w", encoding="utf-8") as f:
            json.dump([doc.model_dump() for doc in documents], f)

        logger.info("RAG indices built and saved successfully.")

    def retrieve(self, query: str, top_k: int = 3) -> str:
        """
        Retrieves context using hybrid search (Reciprocal Rank Fusion).
        Returns a formatted string of the retrieved context.
        """
        if not self.vectorstore or not self.bm25 or not self.documents:
            return ""

        # 1. Dense Search
        dense_results = self.vectorstore.similarity_search(query, k=top_k * 2)

        # 2. Sparse Search
        tokenized_query = query.lower().split(" ")
        sparse_scores = self.bm25.get_scores(tokenized_query)

        # Get top indices from sparse
        sparse_top_indices = sorted(range(len(sparse_scores)), key=lambda i: sparse_scores[i], reverse=True)[:top_k * 2]
        sparse_results = [self.documents[i] for i in sparse_top_indices]

        # 3. Reciprocal Rank Fusion (RRF)
        # Simplified: Just combine unique results from both, prioritizing dense, up to top_k
        combined_results = []
        seen_sources = set()

        for doc in dense_results + sparse_results:
            source_key = f"{doc.metadata.get('source')}:{doc.metadata.get('start_line')}"
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                combined_results.append(doc)
            if len(combined_results) >= top_k:
                break

        # Format results
        if not combined_results:
            return ""

        context_str = "## Cross-File Context (Retrieved via RAG):\n\n"
        for i, doc in enumerate(combined_results):
            source = doc.metadata.get("source", "Unknown")
            lines = f"L{doc.metadata.get('start_line')}-{doc.metadata.get('end_line')}"
            context_str += f"### Context {i+1}: `{source}` ({lines})\n```\n{doc.page_content}\n```\n\n"

        return context_str
