import re
import unicodedata

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACE_RE = re.compile(r"[ \t]+")
_BLANK_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Conservative, deterministic cleanup that does not paraphrase text."""
    value = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    value = _CONTROL_RE.sub("", value)
    value = re.sub(r"(?<=[a-z])-[ \t]*\n[ \t]*(?=[a-z])", "", value)
    value = _SPACE_RE.sub(" ", value)
    value = re.sub(r"[ \t]*\n[ \t]*", "\n", value)
    value = _BLANK_RE.sub("\n\n", value)
    return value.strip()
