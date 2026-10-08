"""Run the small, deterministic Phase 6 developer sanity evaluation."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.reranking.service import LocalCrossEncoderReranker
from app.services.retrieval.models import ChunkMetadata, HybridResult

TEXTS = {
    "termination": "Termination: either party may terminate this Agreement on thirty days prior written notice.",
    "notice": "Notices must be delivered by courier or email to the address in the signature block.",
    "indemnification": "Each party shall indemnify and hold harmless the other party from third-party claims.",
    "liability": "Neither party is liable for indirect damages and aggregate liability is capped at fees paid.",
    "renewal": "This Agreement automatically renews for successive one-year periods unless notice is given.",
    "governing-law": "This Agreement is governed by the laws of India, without regard to conflict rules.",
    "jurisdiction": "The courts of Mumbai, India have exclusive jurisdiction over disputes.",
    "identifier": "12.3(a) Confidential Information excludes information already in the public domain.",
}


def candidate(section: str, rank: int) -> HybridResult:
    metadata = ChunkMetadata(
        __import__("uuid").uuid5(__import__("uuid").NAMESPACE_URL, section),
        __import__("uuid").uuid5(__import__("uuid").NAMESPACE_URL, "doc"),
        __import__("uuid").uuid5(__import__("uuid").NAMESPACE_URL, "version"),
        TEXTS[section], 1, 1, "1", section, section, None, None, "CLAUSE", "PDF", [],
    )
    return HybridResult(metadata=metadata, rrf_score=1.0 / rank, original_rrf_rank=rank, final_rank=rank)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-k", type=int, default=8)
    args = parser.parse_args()
    fixture = json.loads((ROOT / "data/evaluation/reranking_fixture.json").read_text())
    reranker = LocalCrossEncoderReranker(get_settings())
    total_mrr = total_recall = total_ndcg = 0.0
    sections = list(TEXTS)
    for row in fixture:
        candidates = [candidate(section, index) for index, section in enumerate(sections, 1)]
        baseline = candidates[:args.candidate_k]
        relevant = set(row["relevant_sections"])
        baseline_ranks = [i for i, item in enumerate(baseline, 1) if item.metadata.section_identifier in relevant]
        ranked = reranker.rerank(row["query"], baseline)
        reranked_ranks = [i for i, item in enumerate(ranked, 1) if item.result.metadata.section_identifier in relevant]
        total_mrr += 1.0 / reranked_ranks[0] if reranked_ranks else 0.0
        total_recall += 1.0 if reranked_ranks else 0.0
        dcg = sum(1.0 / math.log2(rank + 1) for rank in reranked_ranks)
        ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant), len(ranked)) + 1))
        total_ndcg += dcg / ideal if ideal else 0.0
        print(f"{row['query']}: RRF MRR rank={baseline_ranks[0] if baseline_ranks else 'NA'}; "
              f"reranked rank={reranked_ranks[0] if reranked_ranks else 'NA'}")
    count = len(fixture)
    print(f"RERANKER SANITY EVALUATION (developer fixture): MRR={total_mrr/count:.4f} "
          f"Recall@{args.candidate_k}={total_recall/count:.4f} nDCG={total_ndcg/count:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
