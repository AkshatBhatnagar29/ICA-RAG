# Contract comparison

Comparison is Phase 9 code already present despite older roadmap text. The API
is `POST /api/v1/contracts/compare`; `ContractComparisonService.compare()`
checks both versions belong to the tenant and are READY, loads analyses, and
delegates matching/diff/risk logic to `contracts/comparison.py`.

The baseline is deterministic: normalized clause identity and semantic fields
are compared, changes receive source/target evidence IDs, and the result is
validated before idempotent persistence in `contract_comparisons`. It does not
use retrieval, a cross-encoder, or Groq for the core comparison. The agent can
invoke the same service as a typed tool and prefixes source/target evidence with
`S-`/`T-` to preserve provenance.

The comparison snapshot is derived and replaceable; source versions remain
immutable. Tests in `tests/unit/contracts/test_comparison.py` protect evidence
support and semantic validation.
