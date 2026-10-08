# ADR-005: Application authentication and tenant RBAC

## Decision

Use signed HS256 bearer access tokens, stdlib scrypt password hashing, and
PostgreSQL-backed users, tenants, and memberships in the existing modular
monolith. Resolve an authorized tenant context in reusable FastAPI
dependencies and pass that context boundary into existing services.

## Rationale

This provides standards-compatible bearer semantics without adding a large
identity framework, Redis sessions, or a second service. Database membership
checks are deliberately retained because a user can select among multiple
tenants and membership changes must take effect without trusting a tenant ID.

## Consequences

Protected requests incur JWT verification and a membership lookup. Contract,
legal, retrieval, and agent evidence architectures are unchanged. Secret
rotation and refresh-token lifecycle are not yet implemented and require an
explicit future decision.
