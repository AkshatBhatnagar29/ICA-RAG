# Document ingestion

Here is the actual upload pipeline:

```text
UploadFile -> size/read limit -> upload_document
 -> validation/signature/checksum/storage key
 -> Document + DocumentVersion
 -> DocumentProcessingPipeline
 -> Parsed pages/blocks -> normalized/structured ProcessedDocument
 -> HierarchicalChunker -> E5 embeddings -> Chunk rows -> READY
```

## Source map

- `ingestion/documents.py:upload_document` owns the database/storage upload
  transaction and immutable version identity.
- `validation.py` checks supported type/extension, safe filename, size,
  emptiness, magic signature, checksum, and storage-key traversal safety.
- `storage.py` defines the object-storage protocol and local filesystem adapter.
- `parser.py` uses PyMuPDF for PDFs and `python-docx` for DOCX. PDF text quality
  is measured; if insufficient and OCR is enabled, bounded Tesseract runs over
  rendered pages. LibreOffice can render DOCX for physical-page provenance.
- `normalization.py` performs deterministic whitespace/text normalization.
- `structure.py` turns parsed blocks into headings/sections/clauses without
  inventing identifiers.
- `processing_models.py` defines typed pages, blocks, provenance, and
  `ProcessedDocument`.
- `pipeline.py:DocumentProcessingPipeline.process` coordinates download,
  parsing, processing artifact persistence, and failure state.

OCRmyPDF is not installed or called. Tesseract is an external process with
bounded arguments/timeouts. LibreOffice is optional. Raw documents and processed
artifacts are object storage; relational rows hold identity/lifecycle metadata.

## Failure boundaries

Malformed or unsupported files fail before processing. Parser/OCR subprocess
failure marks the version failed. Indexing checks processed version/document and
tenant identity, validates vectors, rolls back on errors, and never marks a
partially indexed version READY.
