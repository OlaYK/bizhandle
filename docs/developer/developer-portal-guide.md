# Developer Portal Guide

The Developer Portal is available in-app at `/developers`.

## What It Manages
- Public API scope catalog and key lifecycle.
- Webhook subscriptions and delivery dispatch logs.
- Marketplace app listing governance workflow.
- Links to SDK and API quickstarts.

## API Keys
1. Create key with minimal scopes.
2. Copy plaintext key once and store in external secret manager.
3. Rotate key on partner handoff or schedule.
4. Revoke compromised or unused keys.

## Webhooks
1. Create subscription with endpoint and event patterns.
2. Store signing secret securely.
3. Dispatch deliveries and monitor failures/dead-letter status.
4. Rotate secret if leakage is suspected.

Webhook payloads are signed with `sha256=` HMAC signature.

## Marketplace Listings
Lifecycle:
- `draft` -> `submitted` -> `under_review|approved|rejected` -> `published`

Publication is allowed only from `approved`.

## Operational Recommendations
- Use least-privilege scopes.
- Enforce key rotation policy per partner tier.
- Track dead-letter webhook events in weekly ops review.
