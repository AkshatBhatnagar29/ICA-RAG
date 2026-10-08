# Document Processing (Phase 3)

Phase 3 converts uploaded PDF and DOCX files into a deterministic, typed
representation for later chunking. It does not chunk, embed, index, retrieve,
or interpret legal meaning.

PDFs use PyMuPDF text blocks in reading order. Physical pages are 1-indexed and
block coordinates are retained. Pages with visual content and insufficient
meaningful text use Tesseract OCR. Mixed documents record page-level methods
and document-level `HYBRID`. DOCX uses python-docx for paragraphs, heading
styles, lists, and tables. When LibreOffice is installed, DOCX is rendered to
PDF for physical page provenance; otherwise physical page numbers are null.

The artifact is stored at `documents/{document_id}/versions/{version_id}/processed/document.json`.
It links IDs, pages, blocks, sections, positions, text, extraction methods, and
processing metadata. Headers and footers are classified and retained.
Normalization uses NFC Unicode cleanup, conservative whitespace cleanup, and
line-wrap hyphenation removal without rewriting legal values or meaning.

Processing marks versions `PROCESSING`, then `INDEXING` after the artifact is
written. Only successful chunking, embedding, and persistence marks a version
`READY`; empty extraction, OCR errors, and indexing failures mark it `FAILED`.
OCR and LibreOffice use safe
argument arrays, `shell=False`, timeouts, temporary directories, and cleanup.
Logs include IDs and timing, never contract contents. Docker includes Tesseract
and LibreOffice as deliberate native processing dependencies.
