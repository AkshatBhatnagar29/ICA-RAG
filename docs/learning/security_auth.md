# Authentication, RBAC, and multi-tenancy

`POST /api/v1/auth/bootstrap` is development/test-only and creates a tenant,
user, and ADMIN membership. `POST /api/v1/auth/token` verifies a scrypt password
hash and issues a signed HS256 token containing user, tenant, issuer, audience,
issued-at, expiry, and access-token type.

`get_current_context()` verifies signature/claims, rejects a mismatching
`X-Tenant-ID`, and loads active user + membership from PostgreSQL. Role
permissions are explicit: ADMIN receives all; REVIEWER receives write/analyze/
compare/agent permissions; VIEWER is read-only. Endpoint dependencies enforce
permissions before service calls.

Retrieval additionally requires a non-null tenant scope and applies tenant,
document, and version predicates before dense/BM25 results become evidence.
Contract/legal services repeat identity checks. This defense-in-depth matters:
authentication identifies the caller, authorization grants an operation, and
resource scope protects actual rows.

Secrets are environment settings; production requires a sufficiently long JWT
secret and forbids bootstrap tokens. Passwords use scrypt and constant-time
comparison. This is not a claim that every future production control (rotation,
SSO, audit retention) is implemented.
