# ADR 0001: Phase 1 Foundation Domain Model

Date: 2026-02-21
Status: Accepted
Scope: P1-E0-001

## Context
MoniDesk currently resolves tenant context from `businesses.owner_user_id`, which assumes one user and one business.
The Phase 1 roadmap requires team roles and controlled multi-user access.
We also need domain boundaries that let `orders` drive operations while `sales` remains the accounting spine.

## Decision
1. Keep `sales` as immutable financial records and inventory-impact source.
2. Introduce `orders` as an operational lifecycle entity, later converted to `sales` through idempotent rules.
3. Introduce `business_memberships` for role-based access:
   - Roles: `owner`, `admin`, `staff`
   - One active membership identifies a user's business access context.
4. Use backward-compatible business resolution:
   - Prefer active membership.
   - Fallback to legacy `owner_user_id` lookup during migration period.
5. Add auditability as a first-class concern for high-risk mutations.

## Entity Boundaries
- `businesses`: legal workspace container.
- `business_memberships`: user-to-business role assignment.
- `orders`: customer/order lifecycle and fulfillment status.
- `sales`: finalized posted transactions for financial and inventory truth.
- `invoices`: receivables lifecycle and payment events.
- `customers`: CRM identity across orders and invoices.

## State and Flow Rules
- `orders` state transitions are explicit and validated.
- `sales` creation from `orders` is idempotent and one-way.
- `invoices` track receivables states independently but can reconcile against `orders` or `sales`.
- Role checks gate sensitive operations (inventory mutation, financial updates, team management).

## Consequences
Positive:
- Enables staff access without breaking existing owner-only accounts.
- Provides a stable path to role-based authorization and audit trail features.
- Preserves financial integrity by separating operational and accounting layers.

Tradeoff:
- Temporary dual-resolution logic (membership + owner fallback) adds complexity until migration is fully complete.
