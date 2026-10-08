# Authentication and authorization

Phase 12 adds application-level authentication to the modular monolith. Health
and readiness remain public. Data-bearing routes require an OAuth2-compatible
bearer access token.

## Flow and token model

`Authorization: Bearer <token>` is validated before a protected endpoint runs.
Tokens are compact JWTs signed with HS256 using `AUTH_JWT_SECRET`; the
algorithm is fixed, never selected from the untrusted header. Required claims
are `sub`, `tenant_id`, `iat`, `exp`, `iss`, `aud`, and `typ=access`. Tokens
contain identifiers only, never contract text or evidence. Access tokens expire
after `AUTH_ACCESS_TOKEN_MINUTES` and are not logged. Passwords use Python's
stdlib scrypt format with a random salt.

`POST /api/v1/auth/token` accepts OAuth2 password-form credentials. A user may
belong to multiple tenants; `X-Tenant-ID` selects a tenant and is accepted only
when it exactly matches the signed token tenant. A mismatched header is rejected;
it cannot override the authenticated tenant. Without that header, the tenant in
the token is used and membership is still checked.

## Model and permissions

`users`, `tenants`, and `tenant_memberships` persist identity, tenancy, and one
role per membership. Roles map centrally to explicit permissions:

| Role | Permissions |
| --- | --- |
| ADMIN | all Phase 12 permissions |
| REVIEWER | document read/write, search, contract read/analyze/compare, legal read, agent use |
| VIEWER | document read, search, contract read, legal read |

The current permission names are `documents:read`, `documents:write`,
`search:read`, `contracts:read`, `contracts:analyze`, `contracts:compare`,
`legal:read`, `agent:use`, `admin:manage_users`, and
`admin:manage_tenant`.

## Resource and agent boundaries

Endpoint dependencies resolve an authenticated `AuthContext` and replace any
caller-supplied tenant value with the authorized tenant before retrieval,
analysis, comparison, or agent execution. Existing repository/service tenant
filters remain in place as defense in depth. Comparison loads both versions
under the same authorized tenant. Agent requests cannot override the context;
agent tools independently use the context tenant.

Unauthorized resources use the existing non-disclosure convention (404) where
resource services expose it; missing credentials are 401 and insufficient
permissions or membership are 403. Authentication failures use a generic
message.

## Bootstrap and administration

`POST /api/v1/auth/bootstrap` exists only when `APP_ENV` is `development` or
`test` and requires the separately configured `AUTH_BOOTSTRAP_TOKEN` header.
Production startup does not create accounts. Operators should run a controlled
deployment/bootstrap process with a generated JWT secret and bootstrap token,
then disable the development bootstrap path. Development-only administrative
routes provide tenant-scoped user creation, activation/deactivation, membership
creation, and role changes. They require the admin permission and prevent
removing or demoting the final tenant administrator. MFA, refresh-token
rotation, email verification, and SSO remain future work.

Production settings reject an absent or short `AUTH_JWT_SECRET` during
configuration validation. The development/test auth seed is an explicit script,
is idempotent, and stores only scrypt password hashes.

The current Phase 12 implementation protects the existing exposed routes. It
does not add persisted conversations or a general policy engine. No persisted
conversation/message surface is exposed by the current API, so conversation
authorization is not applicable until such a surface exists.
