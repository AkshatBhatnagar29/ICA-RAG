import uuid

from app.services.retrieval.bm25 import LocalBM25, tokenize
from app.services.retrieval.models import ChunkMetadata


def metadata(text: str) -> ChunkMetadata:
    chunk_id = uuid.uuid4()
    return ChunkMetadata(chunk_id, uuid.uuid4(), uuid.uuid4(), text, None, None, None, None, None,
                         None, None, "CLAUSE", "TEXT", [])


def test_tokenizer_preserves_legal_identifiers_and_terms() -> None:
    tokens = tokenize("Section 73, clause 12.3(a), INR 30 days prior written notice")
    assert {"section", "73", "12.3(a)", "inr", "30", "days", "notice"}.issubset(tokens)


def test_bm25_is_deterministic_and_ranks_exact_terms() -> None:
    chunks = [metadata("The agreement may terminate on 30 days prior written notice."),
              metadata("The parties agree to indemnification for losses.")]
    bm25 = LocalBM25()
    first = bm25.search("30 days termination notice", chunks, 2)
    second = bm25.search("30 days termination notice", chunks, 2)
    assert [item.metadata.chunk_id for item in first] == [item.metadata.chunk_id for item in second]
    assert first[0].metadata.text.startswith("The agreement may terminate")

