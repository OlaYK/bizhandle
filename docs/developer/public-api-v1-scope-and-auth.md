# Public API v1 Scope and Authentication Model

## Boundary
- Base path: `/public/v1/*`
- Authentication: `X-Monidesk-Api-Key` header
- Tenant isolation: every API key is bound to one `business_id`; cross-tenant reads are blocked in query scope.

## Key Lifecycle
- Create key: `POST /developer/api-keys`
- Rotate key: `POST /developer/api-keys/{api_key_id}/rotate`
- Revoke key: `POST /developer/api-keys/{api_key_id}/revoke`
- List keys metadata: `GET /developer/api-keys`

Plaintext key material is returned only on create/rotate and never returned again.

## Scope Matrix
- `business:read` -> `GET /public/v1/me`
- `products:read` -> `GET /public/v1/products`
- `orders:read` -> `GET /public/v1/orders`
- `customers:read` -> `GET /public/v1/customers`
- `webhooks:manage` -> developer webhook control APIs
- `marketplace:manage` -> developer marketplace listing APIs

## Validation Rules
- Missing key -> `401`
- Invalid/revoked/expired key -> `401`
- Valid key with insufficient scope -> `403`

## Security Controls
- API keys are stored as one-way hashes.
- Key prefix is stored separately for safe operator identification.
- Key usage updates `last_used_at`.
- Mutating key operations are audit logged.

## Versioning
- Version is fixed at `v1` path contract.
- Breaking changes require new versioned path (`/public/v2`).
