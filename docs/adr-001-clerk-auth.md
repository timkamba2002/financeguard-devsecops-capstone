# ADR 001: Adoption of Clerk Authentication and JWT Verification

## Status
Approved

## Context
FinanceGuard requires an enterprise-ready, robust, and secure user identity management system. The architecture must separate public frontend client routing from backend APIs that handle sensitive financial transaction records.

## Decision
We chose to adopt **Clerk** as our centralized Identity Provider (IdP) for client-side user sessions and authenticate API requests to the Python FastAPI backend via JWT validation.

### Implementation Details
- **Frontend Integration**: Employs the lightweight Clerk JS SDK. Users sign in using Clerk's managed widgets. Client tokens (JWTs) are requested from Clerk in the background.
- **Backend Verification**: Every incoming API call to the `/api/v1/transactions` endpoints must provide a `Bearer` token inside the `Authorization` header.
- **Validation Process**:
  1. The API retrieves Clerk's public JWKS keys.
  2. The JWT signature is decoded and verified using the corresponding RSA public key matching the key ID (`kid`).
  3. The `sub` claim is extracted as the authenticated user's identifier.

## Consequences
- **Pros**:
  - Decreased security risk: passwords, MFA, and OAuth connections are handled externally by Clerk.
  - Zero DB storage overhead for passwords, reducing database leakage impact.
  - Quick setup and excellent user profile widget integrations.
- **Cons**:
  - Requires public internet access inside EKS nodes to periodically sync Clerk public JWKS keys.
  - Potential performance overhead of cryptographic token signature checks on every backend call (mitigated by key caching).
