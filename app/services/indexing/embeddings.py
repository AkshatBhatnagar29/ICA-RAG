from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    provider: str
    model: str
    dimension: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def _validate_vector(vector: Sequence[float], dimension: int) -> list[float]:
    values = [float(value) for value in vector]
    if len(values) != dimension:
        raise ValueError(f"Embedding dimension mismatch: expected {dimension}, got {len(values)}")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Embedding vector contains a non-finite value")
    return values


class LocalE5EmbeddingProvider:
    provider = "fastembed"

    def __init__(self, settings: Settings) -> None:
        self.model = settings.embedding_model
        self.dimension = settings.embedding_dimension
        self.batch_size = settings.embedding_batch_size
        self.cache_path = settings.embedding_cache_path
        self.threads = settings.embedding_threads
        self._encoder: object | None = None

    def _load(self) -> object:
        if self._encoder is None:
            try:
                from fastembed import TextEmbedding
                from fastembed.common.model_description import ModelSource, PoolingType

                supported = {item["model"].lower() for item in TextEmbedding.list_supported_models()}
                if self.model.lower() not in supported:
                    TextEmbedding.add_custom_model(
                        model=self.model,
                        pooling=PoolingType.MEAN,
                        normalization=True,
                        sources=ModelSource(hf=self.model),
                        dim=self.dimension,
                        model_file="onnx/model.onnx",
                        additional_files=[
                            "onnx/config.json",
                            "onnx/sentencepiece.bpe.model",
                            "onnx/special_tokens_map.json",
                            "onnx/tokenizer.json",
                            "onnx/tokenizer_config.json",
                        ],
                    )

                self._encoder = TextEmbedding(model_name=self.model, cache_dir=self.cache_path,
                                              threads=self.threads, cuda=False)
            except Exception as exc:
                raise RuntimeError("The local embedding model could not be loaded") from exc
        return self._encoder

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        encoder = self._load()
        try:
            encoded = encoder.embed(  # type: ignore[attr-defined]
                [f"passage: {text}" for text in texts],
                batch_size=self.batch_size,
            )
            return [_validate_vector(vector, self.dimension) for vector in list(encoded)]
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError("Document embedding failed") from exc

    def embed_query(self, text: str) -> list[float]:
        encoder = self._load()
        try:
            encoded = encoder.embed([f"query: {text}"], batch_size=1)  # type: ignore[attr-defined]
            return _validate_vector(next(iter(encoded)), self.dimension)
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError("Query embedding failed") from exc


def embedding_config_hash(provider: EmbeddingProvider) -> str:
    value = f"{provider.provider}:{provider.model}:{provider.dimension}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
