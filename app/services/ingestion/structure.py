import re

from app.services.ingestion.processing_models import BlockType

_NUMBERED = re.compile(r"^(?:\d+(?:\.\d+)*|[IVXLC]+)[.)]?\s+\S+", re.IGNORECASE)
_PAREN_NUMBERED = re.compile(r"^\(\d+(?:\.\d+)*\)\s+\S+")
_TITLE_MARKER = re.compile(r"^(?:schedule|annexure|article|section|clause)\s+[a-z0-9ivxlc][\w./() -]*$", re.IGNORECASE)
_ALL_CAPS = re.compile(r"^[A-Z][A-Z0-9 &'’(),:/-]{2,}$")
_LIST = re.compile(r"^(?:[-*•]|\(?[a-z][.)]|\(?\d+[.)])\s+")


def _is_heading_candidate(text: str) -> bool:
    value = " ".join(text.split())
    if not value or len(value) > 180:
        return False
    return bool(_NUMBERED.match(value) or _PAREN_NUMBERED.match(value) or _TITLE_MARKER.match(value)
                or _ALL_CAPS.fullmatch(value)
                or value.casefold() in {"definitions", "termination", "payment terms", "scope of work"})


def split_structural_lines(text: str) -> list[tuple[str, BlockType]]:
    """Split page-sized extraction blocks at conservative legal markers."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    merged_lines: list[str] = []
    for line in lines:
        if merged_lines and re.fullmatch(r"(?:\(?\d+(?:\.\d+)*\)?|[IVXLC]+)[.)]?", merged_lines[-1], re.IGNORECASE):
            merged_lines[-1] = f"{merged_lines[-1]} {line}"
        else:
            merged_lines.append(line)
    lines = merged_lines
    groups: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if current and _is_heading_candidate(line):
            groups.append(current)
            current = []
        current.append(line)
    if current:
        groups.append(current)

    output: list[tuple[str, BlockType]] = []
    for group in groups:
        value = "\n".join(group).strip()
        kind = BlockType.HEADING if _is_heading_candidate(group[0]) else BlockType.PARAGRAPH
        output.append((value, kind))
    return output


def classify_block(text: str, style: str | None = None) -> BlockType:
    if style and style.lower().startswith("heading"):
        return BlockType.HEADING
    if _is_heading_candidate(text):
        return BlockType.HEADING
    if _LIST.match(text):
        return BlockType.LIST
    return BlockType.PARAGRAPH


def section_for(blocks: list[tuple[str, BlockType, str | None]]) -> list[str | None]:
    current: str | None = None
    result: list[str | None] = []
    for text, block_type, _ in blocks:
        if block_type == BlockType.HEADING:
            current = text
        result.append(current)
    return result
