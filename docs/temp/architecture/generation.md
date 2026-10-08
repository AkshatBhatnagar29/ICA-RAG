# Phase 7: Evidence-grounded generation

`POST /api/v1/chat` reuses the Phase 5/6 authorized retrieval and optional reranking path. The generation service never looks up chunk IDs supplied by a caller.

The context builder converts ranked results into a deterministic `EvidencePacket`. It de-duplicates chunks, assigns application-owned IDs (`E1`, `E2`, …), preserves page/section/clause provenance, and skips complete chunks that would exceed `GENERATION_MAX_CONTEXT_TOKENS` (estimated at four characters per token). No arbitrary text truncation is performed.

Groq is accessed through the application-owned `LLMProvider` protocol. `GroqProvider` uses bounded retries for timeouts, network errors, and 5xx responses; 429, authentication, malformed-request, and validation failures are not retried. Provider errors are normalized before reaching API clients.

The system prompt establishes that retrieved contract text is untrusted data, never instructions. The model returns only JSON containing an answer, citation IDs, and optional limitations. Pydantic validates that shape. Citation verification then resolves every ID against the request-local evidence registry; authoritative metadata always comes from that registry. Unknown, duplicate, or cross-scope citations fail closed.

If authorized retrieval produces no evidence, Groq is not called and the API returns a controlled no-evidence answer with an empty citation list. Secrets, full prompts, contract text, and full answers are not logged by this layer.

Candidate presence is not evidence sufficiency. Generation requires an explicit reranker result and uses `GENERATION_MIN_RERANKER_SCORE` (default `-0.3`) as a deterministic floor on the highest returned reranker score. The provisional default is based on the current local fixture's observed separation (relevant termination result `2.915432`, relevant indemnification result `-0.219810`, unrelated Saturn/Mumbai results below `-1.19`), not on a scientifically calibrated distribution. This gate requires Phase 13 evaluation calibration before production threshold claims can be made. Requests without reranking do not generate because dense/sparse/RRF scores are retrieval-ranking signals, not calibrated relevance evidence.
