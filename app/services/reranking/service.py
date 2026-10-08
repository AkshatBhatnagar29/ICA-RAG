from __future__ import annotations

import logging
import math
import time
from collections.abc import Sequence

from app.core.config import Settings
from app.services.reranking.models import RerankedResult
from app.services.retrieval.models import HybridResult


class RerankingError(RuntimeError):
    """Raised when explicitly requested local reranking cannot complete."""


class LocalCrossEncoderReranker:
    """Application-owned adapter around FastEmbed's local ONNX cross-encoder."""

    def __init__(self, settings: Settings) -> None:
        self.model = settings.reranker_model
        self.model_version = settings.reranker_model_version
        self.cache_path = settings.reranker_cache_path
        self.batch_size = settings.reranker_batch_size
        self.max_length = settings.reranker_max_length
        self.candidate_limit = settings.reranker_candidate_k
        self.threads = settings.reranker_threads
        self._encoder: object | None = None
        self.last_latency_ms: float | None = None

    def _load(self) -> object:
        if self._encoder is None:
            started = time.perf_counter()
            try:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                supported = {item["model"].lower() for item in TextCrossEncoder.list_supported_models()}
                if self.model.lower() not in supported:
                    raise RerankingError(
                        f"Reranker model {self.model!r} is not supported by installed FastEmbed"
                    )
                self._encoder = TextCrossEncoder(
                    model_name=self.model,
                    cache_dir=self.cache_path,
                    threads=self.threads,
                    cuda=False,
                    lazy_load=False,
                )
            except RerankingError:
                raise
            except Exception as exc:
                raise RerankingError("The local reranker model could not be loaded") from exc
            self.load_latency_ms = (time.perf_counter() - started) * 1000
            logging.getLogger(__name__).info(
                "reranker_loaded",
                extra={"model": self.model, "model_version": self.model_version,
                       "load_duration_ms": round(self.load_latency_ms, 3), "device": "cpu",
                       "threads": self.threads},
            )
        return self._encoder

    def rerank(self, query: str, candidates: Sequence[HybridResult]) -> list[RerankedResult]:
        if not query.strip():
            raise RerankingError("Reranker query must not be empty")
        unique: list[HybridResult] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate.metadata.chunk_id)
            if key in seen:
                continue
            if not isinstance(candidate.metadata.text, str) or not candidate.metadata.text.strip():
                raise RerankingError(f"Candidate {key} has malformed or empty text")
            seen.add(key)
            unique.append(candidate)
            if len(unique) >= self.candidate_limit:
                break
        if not unique:
            self.last_latency_ms = 0.0
            return []

        encoder = self._load()
        started = time.perf_counter()
        try:
            scores = list(encoder.rerank(  # type: ignore[attr-defined]
                query,
                [candidate.metadata.text for candidate in unique],
                batch_size=self.batch_size,
                max_length=self.max_length,
            ))
        except Exception as exc:
            raise RerankingError("Local reranker inference failed") from exc
        self.last_latency_ms = (time.perf_counter() - started) * 1000
        if len(scores) != len(unique) or not all(math.isfinite(float(score)) for score in scores):
            raise RerankingError("Reranker returned an invalid score count or non-finite score")

        ranked = sorted(
            zip(unique, scores, strict=True),
            key=lambda pair: (-float(pair[1]), str(pair[0].metadata.chunk_id)),
        )
        output: list[RerankedResult] = []
        for final_rank, (candidate, score) in enumerate(ranked, start=1):
            output.append(RerankedResult(
                result=candidate,
                score=float(score),
                original_rank=candidate.original_rrf_rank or candidate.final_rank,
                final_rank=final_rank,
            ))
        return output
