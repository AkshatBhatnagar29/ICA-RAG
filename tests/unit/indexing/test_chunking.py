import uuid
from datetime import UTC, datetime

from app.core.config import Settings
from app.services.indexing.chunking import HierarchicalChunker, token_count
from app.services.ingestion.processing_models import (
    Block,
    BlockType,
    ExtractionMethod,
    Page,
    ProcessedDocument,
    ProcessingMetadata,
)
from app.services.ingestion.structure import split_structural_lines


def processed(blocks: list[Block], printed: str | None = "iv") -> ProcessedDocument:
    return ProcessedDocument(
        document_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        version_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        source_filename="contract.pdf", mime_type="application/pdf",
        metadata=ProcessingMetadata(processing_version="v1", parser_version="v1", page_count=1,
            extraction_methods=[ExtractionMethod.NATIVE_TEXT], ocr_used=False, processed_at=datetime.now(UTC)),
        pages=[Page(physical_page_number=3, printed_page_label=printed, text="", extraction_method=ExtractionMethod.NATIVE_TEXT, blocks=blocks)],
    )


def block(number: int, kind: BlockType, text: str, section: str | None = None) -> Block:
    return Block(block_id=f"b{number}", block_type=kind, text=text, block_position=number, section=section)


def test_clauses_are_separate_and_provenance_is_retained() -> None:
    chunks = HierarchicalChunker(Settings(chunk_refinement_mode="refined")).chunk(processed([
        block(1, BlockType.HEADING, "1. Term"), block(2, BlockType.PARAGRAPH, "The term is one year."),
        block(3, BlockType.HEADING, "2. Payment"), block(4, BlockType.PARAGRAPH, "Payment is due in rupees ₹10,00,000."),
        ]))
    assert len(chunks) == 2
    assert chunks[0].clause_number == "1."
    assert chunks[1].clause_title == "Payment"
    assert chunks[1].physical_page_start == 3
    assert chunks[1].printed_page_label == "iv"
    assert chunks[1].source_block_provenance[0]["block_id"] == "b3"


def test_large_text_uses_structural_and_sentence_fallbacks_without_rewriting() -> None:
    text = "First sentence retains ₹10,00,000 and 30%. " * 30
    chunks = HierarchicalChunker(Settings(chunk_target_tokens=10, chunk_soft_max_tokens=20, chunk_hard_max_tokens=30)).chunk(
        processed([block(1, BlockType.HEADING, "7. Liability"), block(2, BlockType.PARAGRAPH, text)])
    )
    assert len(chunks) > 1
    assert all(token_count(chunk.text) <= 30 for chunk in chunks)
    assert "₹10,00,000" in " ".join(chunk.text for chunk in chunks)


def test_table_remains_one_logical_unit_when_small() -> None:
    chunks = HierarchicalChunker(Settings()).chunk(processed([
        block(1, BlockType.TABLE, "Table 1"), block(2, BlockType.TABLE_ROW, "Party | Notice"),
        block(3, BlockType.TABLE_ROW, "A | 30 days"),
    ], printed=None))
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "TABLE"
    assert chunks[0].printed_page_label is None


def test_nested_clause_records_parent_identity() -> None:
    chunks = HierarchicalChunker(Settings()).chunk(processed([
        block(1, BlockType.HEADING, "1. General"), block(2, BlockType.PARAGRAPH, "General terms."),
        block(3, BlockType.HEADING, "1.1 Definitions"), block(4, BlockType.PARAGRAPH, "Definitions apply."),
    ]))
    assert chunks[1].parent_identity == chunks[0].identity


def test_embedded_numbered_clauses_are_split_conservatively() -> None:
    derived = split_structural_lines(
        "CIRCULAR\n\nIntroductory text.\n\n1. Payment is due within 30 days.\n\n"
        "1.1 Interest applies after the due date.\n\nOrdinary continuation."
    )
    assert [kind for _, kind in derived] == [BlockType.HEADING, BlockType.HEADING, BlockType.HEADING]
    assert derived[1][0].startswith("1. Payment")
    assert derived[2][0].startswith("1.1 Interest")


def test_bare_clause_marker_does_not_become_tiny_heading() -> None:
    derived = split_structural_lines("7.\nTermination is effective on written notice.")
    assert len(derived) == 1
    assert derived[0][1] == BlockType.HEADING
    assert derived[0][0] == "7. Termination is effective on written notice."


def test_annexure_label_attaches_to_following_content() -> None:
    chunks = HierarchicalChunker(Settings(chunk_refinement_mode="refined")).chunk(processed([
        block(1, BlockType.HEADING, "Annexure I"),
        block(2, BlockType.HEADING, "AGREEMENT WITH CONTRACTOR"),
        block(3, BlockType.PARAGRAPH, "The parties agree to the following terms."),
    ]))
    assert len(chunks) == 1
    assert "Annexure I" in chunks[0].text
    assert "AGREEMENT WITH CONTRACTOR" in chunks[0].text


def test_whereas_background_units_are_not_bundled() -> None:
    chunks = HierarchicalChunker(Settings(chunk_refinement_mode="refined")).chunk(processed([
        block(1, BlockType.HEADING, "AND"),
        block(2, BlockType.PARAGRAPH, "The Contractor is a registered entity."),
        block(3, BlockType.PARAGRAPH, "Whereas, the Government invited bids."),
        block(4, BlockType.PARAGRAPH, "And whereas, the Contractor submitted its offer."),
    ]))
    assert len(chunks) == 3
    assert all(chunk.section_title == "AND" for chunk in chunks)
