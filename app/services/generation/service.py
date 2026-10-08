from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.observability.metrics import metrics
from app.services.generation.citations import VerifiedCitation, verify_citations
from app.services.generation.context import EvidencePacket, build_evidence_packet
from app.services.generation.llm import LLMProvider
from app.services.generation.output import GeneratedAnswer
from app.services.generation.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.retrieval.models import HybridResult, RetrievalQuery
from app.services.retrieval.service import RetrievalService

logger = logging.getLogger(__name__)


class GenerationOutputError(ValueError):
    pass


def has_sufficient_evidence(
    results: Sequence[HybridResult], *, rerank_requested: bool, minimum_reranker_score: float
) -> bool:
    """Require an explicit relevance signal before sending evidence to the LLM.

    RRF/dense/sparse candidate presence is a recall signal, not proof that a
    result answers the query. A generation request therefore needs reranking;
    the highest reranker score must meet the configured floor.
    """
    if not rerank_requested or not results:
        return False
    scores = [result.reranker_score for result in results if result.reranker_score is not None]
    return bool(scores) and max(scores) >= minimum_reranker_score


@dataclass(frozen=True)
class ChatResult:
    answer: str
    citations: list[VerifiedCitation]
    limitations: str | None
    candidate_count: int
    reranker_candidate_count: int
    evidence_count: int
    reranked: bool


class GenerationService:
    def __init__(self, retrieval: RetrievalService, provider: LLMProvider, settings: Settings) -> None:
        self.retrieval = retrieval
        self.provider = provider
        self.settings = settings

    async def answer(self, session: AsyncSession, request: RetrievalQuery) -> ChatResult:
        retrieval = await self.retrieval.search(session, request)
        packet: EvidencePacket = build_evidence_packet(
            retrieval.results, self.settings.generation_max_context_tokens, request.scope,
            getattr(self.settings, "generation_top_k", 10),
        )
        if not packet.items or not has_sufficient_evidence(
            retrieval.results,
            rerank_requested=request.rerank,
            minimum_reranker_score=self.settings.generation_min_reranker_score,
        ):
            return ChatResult("Sufficient authorized evidence was not found for this query.", [], None,
                              len(retrieval.results), retrieval.diagnostics.reranker_candidate_count,
                              0, request.rerank)
        metrics.observe("generation_context_token_estimate", packet.context_token_estimate)
        metrics.observe("generation_selected_evidence_count", len(packet.items))
        user_prompt = build_user_prompt(request.query, packet.context)
        logger.info("generation evidence selected", extra={
            "retrieved_count": len(retrieval.results),
            "candidate_evidence_count": packet.candidate_count,
            "selected_evidence_count": len(packet.items),
            "generation_context_token_estimate": packet.context_token_estimate,
            "provider_request_size": len(user_prompt.encode("utf-8")),
            "evidence_ids_sent_to_llm": list(packet.selected_evidence_ids),
        })
        raw = await self.provider.generate(SYSTEM_PROMPT, user_prompt)
        try:
            model = GeneratedAnswer.model_validate(json.loads(raw))
        except (ValueError, TypeError) as exc:
            metrics.increment("llm_structured_output_failures_total")
            raise GenerationOutputError("The model returned malformed structured output") from exc
        citations = verify_citations(model, packet)
        return ChatResult(model.answer, citations, model.limitations, len(retrieval.results),
                          retrieval.diagnostics.reranker_candidate_count, len(packet.items), request.rerank)
