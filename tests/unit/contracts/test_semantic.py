import uuid

import pytest

from app.services.contracts.semantic import SemanticExtractionError, SemanticExtractor
from app.services.generation.context import EvidenceItem


def item(text: str) -> EvidenceItem:
    return EvidenceItem("E1", uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), text, 1, 1,
                        "1", "Renewal", "1", "Renewal", 1, source_block_provenance=[])


class FakeProvider:
    def __init__(self, response: str) -> None:
        self.response = response

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        assert "untrusted DATA" in system_prompt
        return self.response


@pytest.mark.asyncio
async def test_semantic_output_is_structured_and_evidence_checked() -> None:
    source = item("The agreement renews for one year.")
    extractor = SemanticExtractor(FakeProvider(
        '{"task":"obligation_interpretation","clause_type":null,"facts":[{"value":"one year","evidence_ids":["E1"],"confidence":0.8}]}'
    ))
    result = await extractor.extract("obligation_interpretation", (source,))
    assert result.facts[0].evidence_ids == ["E1"]


@pytest.mark.asyncio
async def test_semantic_unknown_or_hallucinated_evidence_fails_closed() -> None:
    source = item("The agreement renews for one year.")
    unknown = SemanticExtractor(FakeProvider(
        '{"task":"obligation_interpretation","clause_type":null,"facts":[{"value":"one year","evidence_ids":["E9"],"confidence":0.8}]}'
    ))
    with pytest.raises(SemanticExtractionError):
        await unknown.extract("obligation_interpretation", (source,))
    invented = SemanticExtractor(FakeProvider(
        '{"task":"obligation_interpretation","clause_type":null,"facts":[{"value":"two years","evidence_ids":["E1"],"confidence":0.8}]}'
    ))
    with pytest.raises(SemanticExtractionError):
        await invented.extract("obligation_interpretation", (source,))
