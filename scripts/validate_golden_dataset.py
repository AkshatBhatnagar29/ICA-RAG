"""Validate expanded golden data against the canonical local artifacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import selectors
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import ResourceManager
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.models.legal import LegalCorpusVersion
from app.services.evaluation.golden_dataset import load_golden_dataset, validate_answer_leakage


def norm(value: str) -> str:
    return " ".join(value.casefold().split())


def anchor_matches(anchor: str, text: str) -> bool:
    expected = norm(anchor)
    actual = norm(text)
    if expected in actual:
        return True
    # PDF extraction can normalize curly punctuation or split a word at a
    # line boundary. Require most substantive anchor terms, never a guessed
    # answer or a page-only match.
    terms = [term for term in expected.split() if term.isalnum() and len(term) > 3]
    if not terms:
        return False
    matched = sum(term in actual for term in terms)
    return matched / len(terms) >= 0.6


async def validate(path: Path, processed_path: Path) -> dict[str, Any]:
    dataset = load_golden_dataset(path)
    diagnostics = validate_answer_leakage(dataset)
    report: dict[str, Any] = {
        "dataset": str(path),
        "dataset_version": dataset.version,
        "case_count": len(dataset.cases),
        "category_counts": {},
        "document_versions": {},
        "legal_corpus_versions": {},
        "processed_artifact": {"path": str(processed_path), "exists": processed_path.is_file()},
        "answer_leakage_diagnostics": diagnostics,
        "errors": [],
        "valid": False,
    }
    for case in dataset.cases:
        report["category_counts"][case.category] = report["category_counts"].get(case.category, 0) + 1

    resources = ResourceManager(get_settings())
    try:
        async with resources.session_factory() as session:
            for source in dataset.source_documents:
                version = await session.get(DocumentVersion, source.document_version_id)
                document = await session.get(Document, version.document_id) if version else None
                chunks = list((await session.execute(select(Chunk).where(
                    Chunk.document_version_id == source.document_version_id).order_by(Chunk.chunk_index))).scalars().all())
                key = str(source.document_version_id)
                report["document_versions"][key] = {
                    "document_exists": document is not None,
                    "status": version.status.value if version else None,
                    "processed_representation_exists": processed_path.is_file(),
                    "chunk_count": len(chunks),
                    "embedding_count": sum(item.embedding is not None for item in chunks),
                    "required_metadata": all(item.tenant_id and item.document_id and item.document_version_id and item.text for item in chunks),
                    "source_filename": version.original_filename if version else None,
                }
                if document is None or version is None or version.status != DocumentStatus.READY:
                    report["errors"].append(f"missing or non-READY document version: {key}")
                if not chunks:
                    report["errors"].append(f"no chunks for document version: {key}")
                for case in dataset.cases:
                    if case.document_version_id != source.document_version_id:
                        continue
                    texts = [norm(item.text) for item in chunks]
                    for evidence in case.expected_evidence:
                        if evidence.chunk_id and not any(str(item.id) == str(evidence.chunk_id) for item in chunks):
                            report["errors"].append(f"{case.id}: missing chunk_id {evidence.chunk_id}")
                        if evidence.anchor and not any(anchor_matches(evidence.anchor, text) for text in texts):
                            report["errors"].append(f"{case.id}: anchor not found in indexed chunks: {evidence.anchor}")

            for corpus_id in dataset.legal_corpus_versions:
                corpus = await session.get(LegalCorpusVersion, corpus_id)
                report["legal_corpus_versions"][str(corpus_id)] = {"exists": corpus is not None}
                if corpus is None:
                    report["errors"].append(f"missing legal corpus version: {corpus_id}")
    finally:
        await resources.close()

    report["valid"] = not report["errors"] and not diagnostics
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/evaluation/golden/standard_agreement_v2.json")
    parser.add_argument("--processed-artifact", type=Path, default=ROOT / "data/evaluation/results/processed_postchange.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/results/golden_dataset_validation.json")
    args = parser.parse_args()
    report = asyncio.run(validate(args.dataset, args.processed_artifact), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
