from __future__ import annotations

from scripts.run_reranker_experiment import rows_for_reranked


def candidate(chunk_id: str, rank: int, text: str = "passage") -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "rank": rank,
        "text": text,
        "tenant_id": "tenant-1",
        "document_version_id": "version-1",
    }


def test_reranker_preserves_identical_candidate_set_and_scope() -> None:
    candidates = [candidate("b", 1), candidate("a", 2), candidate("c", 3)]
    results = rows_for_reranked(candidates, [0.2, 0.9, 0.1])

    assert {row["chunk_id"] for row in results} == {row["chunk_id"] for row in candidates}
    assert all(row["tenant_id"] == "tenant-1" for row in results)
    assert all(row["document_version_id"] == "version-1" for row in results)
    assert [row["chunk_id"] for row in results] == ["a", "b", "c"]


def test_reranker_tie_breaking_is_deterministic_by_chunk_id() -> None:
    candidates = [candidate("z", 1), candidate("a", 2)]
    first = rows_for_reranked(candidates, [1.0, 1.0])
    second = rows_for_reranked(list(reversed(candidates)), [1.0, 1.0])

    assert [row["chunk_id"] for row in first] == ["a", "z"]
    assert [row["chunk_id"] for row in first] == [row["chunk_id"] for row in second]


def test_empty_candidate_set_is_stable() -> None:
    assert rows_for_reranked([], []) == []


def test_malformed_score_count_cannot_preserve_candidate_invariant() -> None:
    candidates = [candidate("a", 1), candidate("b", 2)]
    results = rows_for_reranked(candidates, [0.5, 0.2])
    assert len(results) == len(candidates)
    assert {row["chunk_id"] for row in results} == {"a", "b"}
