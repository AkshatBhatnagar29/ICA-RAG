# Legal RAG

Legal evidence is represented separately from contract evidence:

```text
legal_corpus_version -> legal_document -> legal_document_version
                      -> legal_chunk + vector
                      -> LegalRetrievalService -> LegalEvidence (L*)
```

`app/models/legal.py` and migration `0006_legal_corpus.py` define the separate
tables. Metadata includes source type, title, citation, section/subsection,
article/paragraph identifiers, page/provenance, corpus version, jurisdiction,
and JSON metadata at the persistence layer. The repository supports statute,
rule/regulation, and case-law source records; datasets map their source fields
without treating them as contract chunks.

`legal/retrieval.py` uses the existing embedding provider, pgvector scope, RRF,
and optional reranker. `legal/evidence.py:assess_evidence` gates empty or
unproven results; `verify_legal_citations` validates IDs and provenance.

Legal and contract namespaces remain separate because a contract statement is
not a legal authority, corpus versions have independent lifecycle/provenance,
and accidental mixing would make citations ambiguous. ICIA provides contextual
legal retrieval, not legal advice, enforceability analysis, or a general legal
search engine.
