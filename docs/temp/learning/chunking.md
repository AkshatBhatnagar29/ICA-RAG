# Chunking deep dive

## Here is exactly what ICIA does

`HierarchicalChunker.chunk()` walks `ProcessedDocument.pages`, removes header and
footer blocks, groups blocks by heading boundaries, normalizes text, derives a
number/title from heading syntax, determines clause/subclause level, and emits
`ChunkDraft` objects with page and block provenance.

Configured values are target 600 tokens, soft maximum 1000, hard maximum 1500,
and overlap setting 40. The current algorithm does not mechanically overlap
ordinary clause chunks; structural boundaries take precedence.

If a unit is over the soft limit, paragraphs are accumulated up to the hard
limit. Oversized paragraphs are split by sentence boundaries; if a sentence is
still too large, token windows of the hard limit are used. Refined mode gives
special treatment to recitals and attaches short annexure/schedule/article
labels to the next same-page unit. Chunk identity is a SHA-256 of version,
unit, piece number, and text, making reindexing deterministic.

Each draft contains section/clause identifiers, type, token count, physical page,
printed label, extraction method, and block IDs/positions/bounding boxes. Parent
identities encode hierarchy. Indexing turns the draft identity into a stable
UUID and stores the content hash.

## Why legal structure matters

Clause numbers, headings, exceptions, schedules, and subclauses carry meaning.
Keeping them together improves evidence citation and prevents a definition or
exception from being semantically detached.

## Alternatives

Fixed token windows are simpler but split clauses. Sentence-only chunks lose
heading/provenance structure. Recursive character splitting is not aware of
legal hierarchy. Semantic chunking adds model cost and non-determinism; current
ICIA uses deterministic structure plus bounded token fallback.
