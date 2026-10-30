"""
Semantic embedding service using Sentence Transformers.
Defaults to allenai/specter2_base (768-dimensional L2-normalized embeddings).
Provides cached vector generation and cosine similarity calculation.
"""
import os
import hashlib
from typing import List, Union, Dict, Optional
import numpy as np
from app.core.logging import get_logger

logger = get_logger(__name__)

EXPECTED_EMBEDDING_DIMENSION = 768
_MODEL_NAME = "allenai/specter2_base"
_MODEL_INSTANCE = None
_EMBEDDING_CACHE: Dict[str, np.ndarray] = {}


class EmbeddingServiceError(RuntimeError):
    """Raised when semantic embedding model fails to initialize or generate embeddings."""
    pass


def get_embedding_model():
    """
    Lazy loader for Sentence Transformer model.
    Strictly enforces configured model and expected dimension (768).
    Never falls back to an incompatible dimension model.
    """
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        logger.info("Loading semantic embedding model: %s", _MODEL_NAME)
        try:
            from sentence_transformers import SentenceTransformer
            loaded = SentenceTransformer(_MODEL_NAME)
            
            # Validate output dimension
            dim_getter = getattr(loaded, "get_embedding_dimension", getattr(loaded, "get_sentence_embedding_dimension", lambda: None))
            dim = dim_getter()
            if dim is not None and dim != EXPECTED_EMBEDDING_DIMENSION:
                raise EmbeddingServiceError(
                    f"Configured embedding model '{_MODEL_NAME}' has dimension {dim}, "
                    f"but {EXPECTED_EMBEDDING_DIMENSION} is required for the FAISS index."
                )
            _MODEL_INSTANCE = loaded
            logger.info("Semantic embedding model '%s' loaded successfully (dim=%d).", _MODEL_NAME, dim or EXPECTED_EMBEDDING_DIMENSION)
        except Exception as e:
            _MODEL_INSTANCE = None
            if isinstance(e, EmbeddingServiceError):
                raise
            logger.error("Failed to initialize SentenceTransformer for '%s': %s", _MODEL_NAME, e)
            raise EmbeddingServiceError(
                f"Failed to load semantic embedding model '{_MODEL_NAME}'. "
                f"Service is currently unable to compute embeddings: {e}"
            ) from e
    return _MODEL_INSTANCE


def generate_embedding(text: str) -> np.ndarray:
    """Generate normalized L2 embedding vector for text."""
    if not text:
        text = "Empty query"
    cache_key = hashlib.md5(text.encode("utf-8")).hexdigest()
    if cache_key in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[cache_key]

    model = get_embedding_model()
    try:
        emb = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        emb = np.asarray(emb, dtype=np.float32)
        if emb.shape[-1] != EXPECTED_EMBEDDING_DIMENSION:
            raise EmbeddingServiceError(
                f"Generated embedding dimension {emb.shape[-1]} does not match "
                f"expected dimension {EXPECTED_EMBEDDING_DIMENSION}."
            )
    except Exception as e:
        if isinstance(e, EmbeddingServiceError):
            raise
        logger.error("Failed to generate embedding: %s", e)
        raise EmbeddingServiceError(f"Embedding generation failed: {e}") from e

    _EMBEDDING_CACHE[cache_key] = emb
    return emb


def generate_batch_embeddings(texts: List[str]) -> np.ndarray:
    """Batch generate normalized L2 embeddings."""
    results = []
    texts_to_compute = []
    idx_map = []

    for i, t in enumerate(texts):
        key = hashlib.md5((t or "Empty").encode("utf-8")).hexdigest()
        if key in _EMBEDDING_CACHE:
            results.append((i, _EMBEDDING_CACHE[key]))
        else:
            texts_to_compute.append(t or "Empty")
            idx_map.append(i)

    if texts_to_compute:
        model = get_embedding_model()
        try:
            computed = model.encode(texts_to_compute, convert_to_numpy=True, normalize_embeddings=True, batch_size=16)
            for original_idx, emb in zip(idx_map, computed):
                emb_f32 = np.asarray(emb, dtype=np.float32)
                if emb_f32.shape[-1] != EXPECTED_EMBEDDING_DIMENSION:
                    raise EmbeddingServiceError(
                        f"Generated batch embedding dimension {emb_f32.shape[-1]} does not match "
                        f"expected dimension {EXPECTED_EMBEDDING_DIMENSION}."
                    )
                key = hashlib.md5(texts[original_idx].encode("utf-8")).hexdigest()
                _EMBEDDING_CACHE[key] = emb_f32
                results.append((original_idx, emb_f32))
        except Exception as e:
            if isinstance(e, EmbeddingServiceError):
                raise
            logger.error("Failed to generate batch embeddings: %s", e)
            raise EmbeddingServiceError(f"Batch embedding generation failed: {e}") from e

    results.sort(key=lambda x: x[0])
    return np.vstack([r[1] for r in results])


def compute_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Compute cosine similarity between two normalized vectors."""
    dot = float(np.dot(vec1, vec2))
    return max(0.0, min(1.0, dot))

