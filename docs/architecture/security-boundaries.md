# Phase 7 security boundaries

The Phase 7 generation path treats user input, uploaded documents, extracted/OCR text, retrieved chunks, and LLM output as untrusted. Trusted application data consists of authorization decisions, tenant/document/version scope, application-generated evidence IDs, provenance, and validation rules.

Authorization occurs in the existing retrieval service before context construction. The generation service does not fetch arbitrary chunk IDs. The context builder receives only ranked retrieval results, validates their scope, assigns request-local `E1`, `E2`, … IDs, and bounds the context size.

Retrieved text is placed in a clearly delimited data section. The static system prompt states that instructions appearing inside that data are not instructions to the model. This is a defense-in-depth boundary, not a claim that prompt injection is completely prevented. Structured output validation and citation verification provide additional controls.

Every citation must resolve to the current request's evidence registry. The application, not the model, owns chunk, document, version, tenant, page, section, clause, and provenance metadata. Unknown, duplicate, fabricated, or out-of-scope citations fail closed. No authorized evidence means no LLM call.
