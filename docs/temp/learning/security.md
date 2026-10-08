# Security boundaries

| Boundary | Source | Protection |
|---|---|---|
| identity | `security/auth.py` | signed token, expiry, issuer/audience, active membership |
| tenant | auth + retrieval/services | signed tenant authoritative; SQL scope before evidence |
| upload | `ingestion/validation.py` | size, MIME/extension, signature, filename, checksum, safe key |
| subprocess | parser/processing | fixed executable configuration, safe argument lists, timeout |
| prompt injection | `generation/prompts.py` | retrieved text is data, never instructions |
| LLM output | Pydantic schemas | untrusted JSON validated before use |
| citation spoofing | generation/legal/contracts evidence verifiers | IDs and provenance must be authorized/selected |
| secrets | settings/logging/Compose | env configuration, redacted logs, no committed `.env` |
| tools | agent registry/executor | typed allowlist, no arbitrary execution, limits/timeouts |

A malicious PDF can still stress parser/OCR resources, so bounded subprocesses
and upload limits matter. The system does not claim prompt injection is solved;
it maintains trust boundaries and fail-closed validation. SSRF is not part of
the current upload/tool path because arbitrary URL fetching is not exposed.
