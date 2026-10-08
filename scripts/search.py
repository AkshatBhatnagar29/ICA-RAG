"""Developer-facing retrieval inspection utility."""

from __future__ import annotations

import argparse
import asyncio
import sys
import textwrap
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.models.chunk import Chunk
from app.services.indexing.embeddings import LocalE5EmbeddingProvider
from app.services.reranking.service import LocalCrossEncoderReranker
from app.services.retrieval.models import RetrievalMode, RetrievalQuery, RetrievalScope
from app.services.retrieval.service import RetrievalService


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Inspect ICIA Phase 5 retrieval results")
    result.add_argument("query", help="text query")
    result.add_argument("--mode", choices=[mode.value for mode in RetrievalMode], default="hybrid")
    result.add_argument("--top-k", type=int, default=5)
    result.add_argument("--tenant-id")
    result.add_argument("--document-id")
    result.add_argument("--document-version-id")
    result.add_argument("--preview-length", type=int, default=500)
    result.add_argument("--rerank", action="store_true", help="rerank the RRF candidate set locally")
    return result


def value(value: object | None) -> str:
    return "N/A" if value is None else str(value)


def print_response(query: str, mode: str, top_k: int, preview_length: int, response: object) -> None:
    # Keep formatting here only; ranking and retrieval remain application-owned.
    print("=" * 50)
    print(f"QUERY: {query}\nMODE: {mode}\nTOP K: {top_k}")
    print("=" * 50)
    results = response.results  # type: ignore[attr-defined]
    for result in results:
        metadata = result.metadata
        page = (f"{metadata.physical_page_start}-{metadata.physical_page_end}"
                if metadata.physical_page_start is not None else None)
        print(f"\nRank {result.final_rank}")
        print(f"Chunk: {metadata.chunk_id}")
        print(f"Document: {metadata.document_id}")
        print(f"Version: {metadata.document_version_id}")
        print(f"Section: {value(metadata.section_title or metadata.section_identifier)}")
        print(f"Clause: {value(metadata.clause_title or metadata.clause_number)}")
        print(f"Page: {value(page)}")
        print("\nDense:")
        print(f"  rank = {value(result.dense_rank)}")
        print(f"  score = {value(result.dense_score)}")
        print("\nBM25:")
        print(f"  rank = {value(result.sparse_rank)}")
        print(f"  score = {value(result.sparse_score)}")
        print("\nRRF:")
        print(f"  score = {result.rrf_score:.6f}")
        if result.reranker_score is not None:
            print(f"  original rank = {result.original_rrf_rank}")
            print(f"  reranker score = {result.reranker_score:.6f}")
        preview = textwrap.shorten(" ".join(metadata.text.split()), width=preview_length,
                                   placeholder=" …")
        print(f'\nText:\n"{preview}"')
        print("\n" + "-" * 50)
    diagnostics = response.diagnostics  # type: ignore[attr-defined]
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Results returned: {diagnostics.result_count}")
    print(f"Dense candidates: {diagnostics.dense_candidate_count}")
    print(f"BM25 candidates: {diagnostics.sparse_candidate_count}")
    print(f"Final hybrid results: {diagnostics.fused_candidate_count}")
    print(f"Latency: {diagnostics.latency_ms:.2f} ms")
    if diagnostics.reranker_enabled:
        print(f"Reranker: {diagnostics.reranker_model}")
        print(f"Reranker candidates: {diagnostics.reranker_candidate_count}")
        print(f"Reranker latency: {diagnostics.reranker_latency_ms:.2f} ms")


async def run(arguments: argparse.Namespace) -> int:
    if not arguments.tenant_id:
        print("Authorization scope error: --tenant-id is required; retrieval fails closed without tenant scope.", file=sys.stderr)
        return 2
    try:
        import uuid

        scope = RetrievalScope(
            tenant_id=uuid.UUID(arguments.tenant_id),
            document_id=uuid.UUID(arguments.document_id) if arguments.document_id else None,
            document_version_id=(uuid.UUID(arguments.document_version_id)
                                 if arguments.document_version_id else None),
        )
        settings = get_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            request = RetrievalQuery(query=arguments.query, scope=scope, top_k=arguments.top_k,
                                     mode=RetrievalMode(arguments.mode), rerank=arguments.rerank)
            reranker = LocalCrossEncoderReranker(settings) if arguments.rerank else None
            service = RetrievalService(LocalE5EmbeddingProvider(settings), reranker=reranker)
            baseline = None
            if arguments.rerank:
                baseline = await service.search(
                    session, request.model_copy(update={"rerank": False})
                )
            response = await service.search(session, request)
            if not response.results and response.diagnostics.dense_candidate_count == 0 and response.diagnostics.sparse_candidate_count == 0:
                count = await session.scalar(select(func.count()).select_from(Chunk).where(Chunk.tenant_id == scope.tenant_id))
                if not count:
                    print("No indexed chunks found. Upload/process/index a document first.")
                    return 0
            if baseline is not None:
                print("\n" + "=" * 50)
                print("RRF BASELINE")
                print("=" * 50)
                print_response(arguments.query, arguments.mode, arguments.top_k,
                               arguments.preview_length, baseline)
                print("\n" + "=" * 50)
                print("RERANKED")
                print("=" * 50)
            print_response(arguments.query, arguments.mode, arguments.top_k,
                           arguments.preview_length, response)
            if baseline is not None:
                baseline_ranks = {str(item.metadata.chunk_id): item.final_rank for item in baseline.results}
                print("\n" + "=" * 50)
                print("COMPARISON")
                print("=" * 50)
                for item in response.results:
                    chunk_id = str(item.metadata.chunk_id)
                    print(f"Chunk {chunk_id}: RRF rank {baseline_ranks.get(chunk_id, item.original_rrf_rank)} "
                          f"-> reranked rank {item.final_rank}; "
                          f"RRF score {item.rrf_score:.6f}; reranker score {item.reranker_score:.6f}")
        await engine.dispose()
        return 0
    except (OperationalError, DBAPIError) as exc:
        print("PostgreSQL is unavailable. Start the Docker stack with:\n"
              "docker compose up -d", file=sys.stderr)
        if get_settings().app_env == "development":
            print(f"Database detail: {exc.__class__.__name__}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid retrieval input: {exc}", file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(f"Authorization scope error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"Retrieval failed: {exc.__class__.__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    arguments = parser().parse_args()
    raise SystemExit(asyncio.run(run(arguments), loop_factory=asyncio.SelectorEventLoop))
