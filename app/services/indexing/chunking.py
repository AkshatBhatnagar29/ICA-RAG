from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.core.config import Settings
from app.services.ingestion.normalization import normalize_text
from app.services.ingestion.processing_models import Block, BlockType, Page, ProcessedDocument

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_NUMBER_RE = re.compile(r"^(?P<number>(?:\d+(?:\.\d+)*|[IVXLC]+|\(?[A-Za-z]|\(?\d+)[.)]?)\s+(?P<title>.+)$", re.IGNORECASE)
_WHEREAS_RE = re.compile(r"^(?:and\s+)?whereas\b", re.IGNORECASE)
_ATTACHABLE_LABEL_RE = re.compile(r"^(?:annexure|schedule|article)\b", re.IGNORECASE)


def token_count(text: str) -> int:
    return len(_TOKEN_RE.findall(text))


@dataclass(frozen=True)
class ChunkDraft:
    identity: str
    parent_identity: str | None
    chunk_index: int
    section_identifier: str | None
    section_title: str | None
    clause_number: str | None
    clause_title: str | None
    chunk_type: str
    text: str
    token_count: int
    physical_page_start: int | None
    physical_page_end: int | None
    printed_page_label: str | None
    extraction_method: str
    source_block_provenance: list[dict[str, object]]


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", text) if part.strip()]


def _token_split(text: str, limit: int) -> list[str]:
    words = _TOKEN_RE.findall(text)
    return [" ".join(words[pos:pos + limit]) for pos in range(0, len(words), limit)]


class HierarchicalChunker:
    def __init__(self, settings: Settings) -> None:
        if not (settings.chunk_target_tokens <= settings.chunk_soft_max_tokens <= settings.chunk_hard_max_tokens):
            raise ValueError("Chunk target, soft maximum, and hard maximum must be ordered")
        self.settings = settings

    def chunk(self, document: ProcessedDocument) -> list[ChunkDraft]:
        units = self._units(document.pages)
        drafts: list[ChunkDraft] = []
        hierarchy: list[str | None] = []
        for unit_number, (heading, blocks, page) in enumerate(units):
            text = normalize_text("\n\n".join(block.text for block in blocks))
            if not text:
                continue
            number, title = self._heading_parts(heading.text if heading else "")
            level = self._level(number)
            chunk_type = "TABLE" if any(block.block_type == BlockType.TABLE for block in blocks) else (
                "SUBCLAUSE" if level > 1 else "CLAUSE" if heading else "PARAGRAPH"
            )
            pieces = self._split_structurally(text, blocks)
            base_parent = hierarchy[level - 2] if heading and level > 1 and len(hierarchy) >= level - 1 else None
            parent_identity = base_parent
            for piece_number, piece in enumerate(pieces):
                identity = hashlib.sha256(f"{document.version_id}:{unit_number}:{piece_number}:{piece}".encode()).hexdigest()
                provenance = [self._provenance(block, page) for block in blocks]
                section_identifier = number or (heading.section if heading and heading.section else None)
                if section_identifier is not None and len(section_identifier) > 255:
                    section_identifier = None
                drafts.append(ChunkDraft(identity, parent_identity, len(drafts),
                    section_identifier,
                    heading.text if heading else (page.blocks[0].section if page.blocks else None),
                    number, title, chunk_type, piece, token_count(piece),
                    page.physical_page_number, page.physical_page_number, page.printed_page_label,
                    page.extraction_method.value, provenance))
                parent_identity = identity
            if heading:
                while len(hierarchy) < level - 1:
                    hierarchy.append(None)
                hierarchy[level - 1:] = [drafts[-1].identity]
        return drafts

    def _units(self, pages: list[Page]) -> list[tuple[Block | None, list[Block], Page]]:
        result: list[tuple[Block | None, list[Block], Page]] = []
        for page in pages:
            current_heading: Block | None = None
            current: list[Block] = []
            for block in page.blocks:
                if block.block_type in (BlockType.HEADER, BlockType.FOOTER):
                    continue
                if block.block_type == BlockType.HEADING and current:
                    result.append((current_heading, current, page))
                    current = []
                if block.block_type == BlockType.HEADING:
                    current_heading = block
                elif (self.settings.chunk_refinement_mode == "refined" and current_heading is not None
                      and len(current) > 1 and _WHEREAS_RE.match(block.text.strip())):
                    # Background recitals are independent semantic units. Keep
                    # the heading as context on each unit without inventing a
                    # clause number or merging unrelated recitals.
                    result.append((current_heading, current, page))
                    current = [current_heading, block]
                    continue
                current.append(block)
            if current:
                result.append((current_heading, current, page))
        return self._attach_short_labels(result) if self.settings.chunk_refinement_mode == "refined" else result

    @staticmethod
    def _attach_short_labels(
        units: list[tuple[Block | None, list[Block], Page]],
    ) -> list[tuple[Block | None, list[Block], Page]]:
        """Attach standalone annexure/schedule labels to their next unit.

        Only a label-only unit below 25 tokens is attached, and only to the
        immediately following unit on the same page. Signature headings,
        party labels, and short substantive clauses remain independent.
        """
        output: list[tuple[Block | None, list[Block], Page]] = []
        index = 0
        while index < len(units):
            heading, blocks, page = units[index]
            label = heading.text.strip() if heading else ""
            if (heading is not None and len(blocks) == 1 and token_count(label) < 25
                    and _ATTACHABLE_LABEL_RE.match(label)
                    and index + 1 < len(units) and units[index + 1][2] is page):
                next_heading, next_blocks, next_page = units[index + 1]
                output.append((next_heading, [*blocks, *next_blocks], next_page))
                index += 2
                continue
            output.append((heading, blocks, page))
            index += 1
        return output

    def _split_structurally(self, text: str, blocks: list[Block]) -> list[str]:
        if token_count(text) <= self.settings.chunk_soft_max_tokens:
            return [text]
        pieces: list[str] = []
        paragraphs = [normalize_text(block.text) for block in blocks if block.text.strip()]
        current = ""
        for paragraph in paragraphs:
            candidate = normalize_text(f"{current}\n\n{paragraph}") if current else paragraph
            if token_count(candidate) <= self.settings.chunk_hard_max_tokens:
                current = candidate
            else:
                if current:
                    pieces.append(current)
                pieces.extend(self._split_text(paragraph)) if token_count(paragraph) > self.settings.chunk_hard_max_tokens else None
                current = "" if token_count(paragraph) > self.settings.chunk_hard_max_tokens else paragraph
        if current:
            pieces.append(current)
        return pieces

    def _split_text(self, text: str) -> list[str]:
        parts = _split_sentences(text)
        if all(token_count(part) <= self.settings.chunk_hard_max_tokens for part in parts):
            result: list[str] = []
            current = ""
            for part in parts:
                candidate = normalize_text(f"{current} {part}") if current else part
                if current and token_count(candidate) > self.settings.chunk_hard_max_tokens:
                    result.append(current)
                    current = part
                else:
                    current = candidate
            if current:
                result.append(current)
            return result
        return [piece for part in parts for piece in _token_split(part, self.settings.chunk_hard_max_tokens)]

    @staticmethod
    def _heading_parts(text: str) -> tuple[str | None, str | None]:
        match = _NUMBER_RE.match(text.strip())
        return (match.group("number"), match.group("title")) if match else (None, text or None)

    @staticmethod
    def _level(number: str | None) -> int:
        if not number:
            return 1
        return number.rstrip(".)").count(".") + 1

    @staticmethod
    def _provenance(block: Block, page: Page) -> dict[str, object]:
        return {"block_id": block.block_id, "block_position": block.block_position,
                "physical_page_number": page.physical_page_number, "bbox": block.bbox}
