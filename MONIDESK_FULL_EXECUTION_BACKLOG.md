# MoniDesk Full Execution Backlog (Parity + Surpass)

Date: 2026-02-21  
Sources: `BUMPA_GAP_ANALYSIS.md`, `MONIDESK_PHASE1_EXECUTION_BACKLOG.md`  
Status: Program backlog in active execution

## Execution Progress (2026-02-21)
Completed in this implementation pass:
- `P1-E1-007` Pending-order timeout and auto-cancel policy
  - Implemented lazy auto-cancel on order read/update paths with per-business timeout configuration.
- `P1-E1-008` Frontend orders workspace and status controls
  - Implemented Orders page with create/list/filter/update lifecycle support.
- `P1-E1-009` POS quick-order interaction baseline (scanner-ready input)
  - Implemented keyboard-first quick-add workflow using SKU/size/label matching.
- `P1-E1-004` API list/filter orders completion gap
  - Added `channel` and `customer_id` filters and response echoes.

Validation snapshot for this pass:
- Backend: `30 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P1-E2-001` DB migration for `invoices` and `invoice_events`
  - Added invoice and invoice-event tables with indexes and downgrade path.
- `P1-E2-002` API create and send invoice
  - Added create/list/send invoice endpoints with order/customer linking and state handling.
- `P1-E2-003` API mark invoice paid with reconciliation metadata
  - Added idempotent mark-paid endpoint with payment method/reference/idempotency key support.
- `P1-E2-004` Reminder dispatch abstraction (manual trigger first)
  - Added manual reminder endpoint with logged invoice events and audit entries.
- `P1-E2-005` Frontend invoice workspace (create/list/pay)
  - Added Invoices page with lifecycle actions: create, send, remind, and mark paid.

Validation snapshot for this pass:
- Backend: `33 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P1-E3-001` DB migration for `customers`, `customer_tags`, `customer_tag_links`
  - Added CRM core tables, indexes, and downgrade-safe migration path.
- `P1-E3-002` API customer CRUD + search filters
  - Added customer create/list/update/delete plus query filters by `q` and `tag_id`.
- `P1-E3-003` Customer linking on orders and invoices
  - Added tenant-safe customer existence checks and order/invoice customer consistency validation.
- `P1-E3-005` Frontend CRM workspace (list/create/edit/tag)
  - Added Customers page with customer management, tag creation, tag attach/detach, and search/filtering.

Validation snapshot for this pass:
- Backend: `35 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P1-E3-004` Customer CSV import endpoint
  - Added `/customers/import-csv` with header/no-header parsing, default tag linking, validation, and rejection summary reporting.
- `P1-E3-006` Dashboard customer insight widget
  - Added `/dashboard/customer-insights`, customer insight aggregation service, and dashboard UI card showing active/repeat/top customers.

Validation snapshot for this pass:
- Backend: `37 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P1-E2-006` Receipt/invoice template strategy doc
  - Added variable contract, rendering pipeline, versioning, and rollout/test plan in `docs/receipt-invoice-template-strategy.md`.
- `P2-E5-001` DB schema for storefront config
  - Added `storefront_configs` model and migration baseline with slug/domain/branding/policy fields.
- `P2-E5-002` Catalog publish controls (product/variant visibility)
  - Added product and variant publish flags with owner/admin publish toggle endpoints.
- `P2-E5-003` Public storefront APIs (browse/search/product detail)
  - Added anonymous public storefront profile/catalog/product-detail APIs with rate limiting.

Validation snapshot for this pass:
- Backend: `39 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P2-E5-004` Frontend hosted storefront page templates
  - Added public storefront list/detail routes and pages (`/store/:slug`, `/store/:slug/products/:productId`), mobile-responsive layout, filtering, and pagination controls.
- `P2-E5-005` Custom domain and DNS verification flow
  - Added domain challenge/status/verify APIs with TXT challenge generation and verification lifecycle tracking.
- `P2-E5-006` SEO and metadata controls for storefront pages
  - Added SEO fields (`seo_title`, `seo_description`, `seo_og_image_url`) to config model/API and storefront settings UI.
- `P2-E6-001` Checkout session model and API
  - Added checkout sessions/items model, migration, authenticated session creation endpoint, and public checkout fetch/place-order endpoints.
- `P2-E6-002` Payment provider abstraction layer
  - Added provider adapter contract and stub provider integration for checkout session initialization.

Validation snapshot for this pass:
- Backend: `42 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P2-E6-003` Payment webhook processing and signature verification
  - Added signed webhook callback endpoint (`/payment-webhooks/{provider}`), HMAC verification, and idempotent event storage (`checkout_webhook_events`).
- `P2-E6-004` Auto-mark orders paid on successful gateway callback
  - Added webhook-driven order status transition to `paid` and idempotent order-to-sale conversion for successful payment events.
- `P2-E6-005` Failed and pending payment recovery flows
  - Added checkout session retry endpoint (`/checkout-sessions/{checkout_session_id}/retry-payment`) and frontend recovery controls in a dedicated payments operations UI.
- `P2-E6-006` Payments operations dashboard and reconciliation report
  - Added payments summary endpoint (`/checkout-sessions/payments-summary`), checkout session list/filter API, and frontend `/payments` dashboard with reconciliation status visibility.

Validation snapshot for this pass:
- Backend: `45 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P2-E7-001` Shipping settings model (zones, carriers, service rules)
  - Added shipping settings persistence with zones/service-rule configuration API and validation.
- `P2-E7-002` Carrier provider abstraction and connector base
  - Added provider contract plus stub connector for rate quoting, label purchase, and tracking sync.
- `P2-E7-003` Checkout shipping-rate quote and selection flow
  - Added checkout quote/select APIs and frontend rate quote/select controls in shipping operations UI.
- `P2-E7-004` Shipment creation and label purchase workflow
  - Added shipment creation endpoint with label purchase integration and order linkage.
- `P2-E7-005` Tracking sync and status propagation to orders
  - Added tracking sync endpoint with shipment event logging and order status propagation.
- `P2-E7-006` Ops UI for shipping management
  - Added `/shipping` page with settings management, checkout quote/select workflow, shipment creation, and tracking sync actions.
- `P2-E8-001` DB migration for `locations` and location membership scope
  - Added location/membership scope schema with tenant-safe constraints and migration support.
- `P2-E8-002` Location-aware inventory ledger and stock queries
  - Added location inventory ledger service and endpoints for stock-in/adjust/query/overview.
- `P2-E8-003` Inter-location stock transfer workflow
  - Added transfer API and frontend transfer execution workflow in locations UI.
- `P2-E8-004` Location-based low-stock and reorder alerts
  - Added location-aware low-stock endpoint with threshold and pagination controls.
- `P2-E8-005` Location-aware order allocation policy
  - Added order allocation endpoint that validates and reserves location stock.
- `P2-E8-006` UI for location setup and stock visibility
  - Added `/locations` page for location setup, stock operations, transfer logs, low-stock visibility, and order allocation actions.
- `P2-E9-001` Integration credential vault and secret rotation policy
  - Added encrypted secret vault API with versioned rotation behavior and audit logging.
- `P2-E9-002` App installation lifecycle (connect/disconnect/permissions)
  - Added installation lifecycle APIs with connect/reconnect/disconnect tracking and scopes.
- `P2-E9-003` Event outbox and webhook delivery engine
  - Added outbox queue/list/dispatch engine with retry/dead-letter lifecycle.
- `P2-E9-004` Integration center UI
  - Added `/integrations` page for secret management, app installation lifecycle, outbox controls, and connector monitoring.
- `P2-E9-005` Analytics connectors baseline (Meta Pixel, GA)
  - Added storefront analytics outbox emission baseline and integration-center presets/controls for analytics connector setup.
- `P2-E9-006` Messaging connector baseline (WhatsApp provider abstraction)
  - Added outbound messaging connector API and integration-center message dispatch/visibility workflow.

Validation snapshot for this pass:
- Backend: `48 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P3-E10-001` Customer group management (saved dynamic segments)
  - Added segment persistence, dynamic filter evaluation, preview endpoint, and campaign audience resolution via saved segments.
- `P3-E10-002` Bulk campaign composer and send orchestration
  - Added campaign create/list/dispatch APIs with recipient orchestration, provider dispatch flow, and status/count tracking.
- `P3-E10-003` Consent and opt-out framework
  - Added customer consent upsert/list APIs and automated suppression/skip enforcement during campaign recipient generation.
- `P3-E10-004` Campaign performance metrics
  - Added aggregate and per-campaign metrics endpoints plus frontend campaign workspace visibility for send/suppress/failure outcomes.
- `P3-E10-005` Automated retention triggers (repeat purchase nudges)
  - Added retention trigger create/list/run APIs with trigger-run audit trail and optional auto-dispatch execution.
- `P3-E10-006` Message template library and governance
  - Added template create/list/update lifecycle with approval gating for immediate sends and campaign template governance controls.

Validation snapshot for this pass:
- Backend: `49 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P3-E11-001` Multi-currency invoicing and FX conversion policy
  - Added invoice/base-currency model extensions, FX quote API (`/invoices/fx-quote`), and base-currency totals on invoice payloads.
- `P3-E11-002` Branded invoice/receipt template engine
  - Added invoice template model + migration + APIs (`PUT/GET /invoices/templates`) and frontend template workflow in the invoices workspace.
- `P3-E11-003` Partial payments and installment schedules
  - Added invoice payments + installments models/migration and APIs (`/invoices/{id}/payments`, `/invoices/{id}/installments`) with idempotent payment handling and balance recomputation.
- `P3-E11-004` Automated reminder schedules and escalation rules
  - Added reminder policy APIs (`/invoices/{id}/reminder-policy`) and due-reminder automation run endpoint (`/invoices/reminders/run-due`) with escalation metadata.
- `P3-E11-005` Accounts receivable aging dashboard
  - Added receivables aging API (`/invoices/aging`) plus frontend aging visibility and reminder-run controls in `invoices-page`.
- `P3-E11-006` Monthly statements and export packs
  - Added statement APIs (`/invoices/statements`, `/invoices/statements/export`) and frontend statement export action.
- `P1-E0-004` OpenAPI snapshot extension for new modules
  - Regenerated OpenAPI path snapshot with new advanced receivables routes.

Validation snapshot for this pass:
- Backend: `50 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P3-E12-001` Analytical data mart for commerce metrics
  - Added analytics mart persistence (`analytics_daily_metrics`) and refresh flow (`POST /analytics/mart/refresh`) with tenant-safe daily aggregation.
- `P3-E12-002` Channel profitability and net margin dashboards
  - Added channel profitability API (`GET /analytics/channel-profitability`) and frontend analytics workspace visibility.
- `P3-E12-003` Cohort and repeat-customer analytics
  - Added retention/cohort API (`GET /analytics/cohorts`) and frontend cohort charting support.
- `P3-E12-004` Inventory aging and stockout impact analytics
  - Added inventory aging API (`GET /analytics/inventory-aging`) and inventory value/stockout coverage in analytics UI.
- `P3-E12-005` Marketing attribution ingestion
  - Added attribution ingestion API (`POST /analytics/attribution-events`) with persisted attribution event model.
- `P3-E12-006` Report exports and scheduled summaries
  - Added report export/schedule APIs (`GET /analytics/reports/export`, `POST/GET /analytics/reports/schedules`) and frontend report scheduling controls.
- `P3-E13-001` Mobile POS optimized UI and route partitioning
  - Added dedicated POS route/page (`/pos`) with mobile-first interaction layout.
- `P3-E13-002` Offline order queue and local persistence
  - Added offline queue local persistence in frontend with backend sync endpoint (`POST /pos/offline-orders/sync`).
- `P3-E13-003` Conflict resolution policy for delayed sync
  - Added deterministic sync conflict policy handling (`reject`/`adjust_to_available`) with duplicate event idempotency.
- `P3-E13-004` Hardware scanner and receipt printer integration hooks
  - Added scanner/receipt abstraction hooks in `ibos-frontend/src/lib/pos-devices.ts`.
- `P3-E13-005` Shift closeout and cash reconciliation workflow
  - Added shift lifecycle APIs (`POST /pos/shifts/open`, `GET /pos/shifts/current`, `POST /pos/shifts/{shift_id}/close`) and frontend shift reconcile controls.
- `P3-E14-001` Fine-grained RBAC v2 (resource/action-level controls)
  - Added expanded permission matrix and permission-check helper APIs in backend core permissions module.
- `P3-E14-002` Immutable audit archive and retention policy
  - Added audit archive table/model and archive trigger endpoint (`POST /privacy/audit-archive`).
- `P3-E14-003` Backup, restore, and disaster recovery runbooks
  - Added runbook documentation in `docs/p3-e14-backup-restore-runbook.md`.
- `P3-E14-004` Platform observability dashboards and SLO alerts
  - Added observability/SLO runbook documentation in `docs/p3-e14-observability-slo.md`.
- `P3-E14-005` Security testing cycle (SAST/DAST/pen test)
  - Added security testing cycle documentation in `docs/p3-e14-security-testing-cycle.md`.
- `P3-E14-006` Data privacy controls (PII export/delete workflow)
  - Added privacy API surface (`GET /privacy/customers/{customer_id}/export`, `DELETE /privacy/customers/{customer_id}`) and frontend privacy workspace.
- `P1-E0-004` OpenAPI snapshot extension for new modules
  - Regenerated OpenAPI path snapshot for new analytics/POS/privacy routes.

Validation snapshot for this pass:
- Backend: `51 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P4-E15-001` Event-aware feature store for AI context (orders, refunds, stockouts, campaigns)
  - Added AI copilot feature snapshot model/migration (`ai_feature_snapshots`) and APIs (`POST /ai/feature-store/refresh`, `GET /ai/feature-store/latest`) with 7-120 day window aggregation.
- `P4-E15-002` AI insight types v2 (anomaly, urgency, opportunity)
  - Added insight model/migration (`ai_generated_insights`) and taxonomy generation/list APIs (`POST /ai/insights/v2/generate`, `GET /ai/insights/v2`) with confidence and severity metadata.
- `P4-E15-003` Prescriptive AI actions with approval workflow
  - Added prescriptive action model/migration (`ai_prescriptive_actions`), action list/decision APIs (`GET /ai/actions`, `POST /ai/actions/{action_id}/decision`), and frontend approve/reject workflow in `insights-page`.
- `P1-E0-004` OpenAPI snapshot extension for new modules
  - Regenerated OpenAPI path snapshot for new AI copilot routes.

Validation snapshot for this pass:
- Backend: `52 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P4-E15-004` Natural-language analytics assistant over curated metrics
  - Added assistant query API (`POST /ai/analytics-assistant/query`) with curated metric grounding and governance trace linkage.
- `P4-E15-005` Proactive risk alerts (cashflow, stockout, refund spikes)
  - Added risk-alert config and run surfaces (`GET/PUT /ai/risk-alerts/config`, `POST /ai/risk-alerts/run`, `GET /ai/risk-alerts/events`) with configurable thresholds/channels.
- `P4-E15-006` AI governance and response traceability
  - Added governance trace APIs (`GET /ai/governance/traces`, `GET /ai/governance/traces/{trace_id}`) and persisted trace capture for assistant/risk and existing AI flows.
- `P4-E16-001` Credit model redesign with trend-based explainable factors
  - Added credit profile v2 API (`GET /dashboard/credit-profile/v2`) with weighted trend factors, rationale text, and prior-window comparison.
- `P4-E16-002` Cashflow forecast engine (short and medium horizon)
  - Added forecast API (`GET /dashboard/credit-forecast`) exposing interval projections and explicit error bounds.
- `P4-E16-003` Scenario simulator (pricing, expense, restock what-if)
  - Added simulation API (`POST /dashboard/credit-scenarios/simulate`) and frontend side-by-side scenario outcomes in `credit-profile-page`.
- `P1-E0-004` OpenAPI snapshot extension for new modules
  - Regenerated OpenAPI path snapshot for new AI governance/risk and credit intelligence routes.

Validation snapshot for this pass:
- Backend: `54 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P4-E16-004` Lender-ready export pack (statements, trends, score explanation)
  - Added export bundle API (`POST /dashboard/credit-export-pack`) returning credit profile v2, forecast, statement periods, and score explanation package metadata.
- `P4-E16-005` Finance guardrails and policy alerts
  - Added policy and alert APIs (`GET/PUT /dashboard/finance-guardrails/policy`, `POST /dashboard/finance-guardrails/evaluate`) with margin-collapse, expense-spike, and weak-liquidity detection.
- `P4-E16-006` Credit improvement action planner
  - Added planner API (`GET /dashboard/credit-improvement-plan`) with prioritized measurable actions and estimated score impact, plus frontend planner/guardrails/export integration in `credit-profile-page`.
- `P1-E0-004` OpenAPI snapshot extension for new modules
  - Regenerated OpenAPI path snapshot for lender pack and finance guardrail/improvement plan routes.

Validation snapshot for this pass:
- Backend: `55 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P4-E17-001` Rules engine core (event trigger -> condition -> action)
  - Added automation rules runtime with versioned rules, condition evaluation, event trigger matching, and persisted run state transitions.
- `P4-E17-002` Action adapters (message, tag customer, create task, discount)
  - Added production adapters for messaging dispatch, customer tagging, internal task creation, and discount artifact generation.
- `P4-E17-003` Automation templates (abandoned cart, overdue invoice, low stock)
  - Added installable template catalog and install endpoint with reusable baseline triggers/conditions/actions.
- `P4-E17-004` No-code workflow builder UI
  - Added `/automation` frontend workspace with rule builder, action configuration, template installs, and dry-run controls.
- `P4-E17-005` Workflow run logs and debugging console
  - Added automation run/step log APIs and UI run console with per-step statuses and failure visibility.
- `P4-E17-006` Safety guardrails (rate limits, loop prevention, rollback)
  - Added per-rule hourly rate limits, loop-prevention fingerprinting, and rollback compensation for reversible actions.
- `P1-E0-004` OpenAPI snapshot extension for new modules
  - Regenerated OpenAPI path snapshot for automation module routes.

Validation snapshot for this pass:
- Backend: `57 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P4-E18-001` Public API v1 scope and authentication model
  - Added public API boundary and auth contract with scope catalog, API-key hashing, tenant binding, and scope enforcement dependency for `/public/v1/*`.
- `P4-E18-002` Public REST endpoints and tenant-safe API keys
  - Added API key lifecycle APIs (`create/list/rotate/revoke`) and public REST read endpoints (`/public/v1/me`, `/public/v1/products`, `/public/v1/orders`, `/public/v1/customers`) with per-scope authorization.
- `P4-E18-003` Outbound webhook subscriptions for third-party apps
  - Added webhook subscription management, signed webhook delivery queue, retry/dead-letter dispatch engine, and delivery observability APIs.
- `P4-E18-004` Developer portal and API documentation site
  - Added frontend `/developers` workspace with API key controls, webhook operations, marketplace controls, docs index, and public API smoke test tools.
- `P4-E18-005` SDK starter kits and integration quickstarts
  - Added SDK quickstart docs and starter probes for Node/Python in `docs/sdk/*` and `docs/sdk/examples/*`.
- `P4-E18-006` App marketplace governance and listing workflow
  - Added marketplace listing draft/submit/review/publish lifecycle APIs, audit coverage, and governance docs.
- `P1-E0-004` OpenAPI snapshot extension for new modules
  - Regenerated OpenAPI path snapshot for developer platform and public API v1 routes.

Validation snapshot for this pass:
- Backend: `59 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

Additional completed in this pass:
- `P1-E0-001` Data model ADR for orders, invoices, customers, memberships, audit logs
  - Reconciled backlog status with existing implementation and ADR artifact in `docs/adr/0001-phase1-foundation-domain-model.md`.
- `P1-E0-002` Extend auth context to resolve user + business + role
  - Reconciled backlog status with existing business-access context and role resolution middleware.
- `P1-E0-003` Shared audit logging utility for domain mutations
  - Reconciled backlog status with existing shared audit helper in `app/services/audit_service.py` and broad module adoption.
- `P1-E1-001` DB migration for `orders` and `order_items`
  - Reconciled backlog status with existing migration `20260221_0006_add_orders_tables.py`.
- `P1-E1-002` Order status machine and transition guards
  - Reconciled backlog status with existing transition validation and guard paths in orders router.
- `P1-E1-003` API create order (`POST /orders`)
  - Reconciled backlog status with existing create-order endpoint and integration tests.
- `P1-E1-005` API update order status (`PATCH /orders/{id}/status`)
  - Reconciled backlog status with existing status update endpoint and transition enforcement.
- `P1-E1-006` Idempotent order-to-sale conversion logic
  - Reconciled backlog status with existing idempotent conversion flow used by orders and checkout callbacks.
- `P1-E4-001` DB migration for `business_memberships`
  - Reconciled backlog status with existing migration `20260221_0004_add_business_memberships.py`.
- `P1-E4-002` Permission matrix and policy dependency middleware
  - Reconciled backlog status with existing role-policy and permission middleware.
- `P1-E4-003` Team management API (invite/add/remove/change role)
  - Reconciled backlog status with existing team router endpoints and tests.
- `P1-E4-004` Audit log storage + query API
  - Reconciled backlog status with existing audit models, migration, and `/audit-logs` API.
- `P1-E4-005` Frontend team and roles page
  - Reconciled backlog status with existing `team-page` UI and workflow wiring.
- `P1-E4-006` Frontend audit timeline page
  - Reconciled backlog status with existing `audit-logs-page` UI and filters.
- `P3-E13-006` POS performance and reliability SLO tests
  - Added dedicated integration SLO test coverage in `ibos-backend/tests/test_pos_slo.py` with explicit thresholds for offline-sync P95 latency, shift endpoint latency, and sync reliability/duplicate replay behavior.

Validation snapshot for this pass:
- Backend: `60 passed, 2 skipped` (`pytest -q -p no:cacheprovider`)
- Frontend: production build successful (`npm run build`)

## Program Objective
Deliver an end-to-end roadmap from current MoniDesk capabilities to:
1. Match Bumpa's core commerce and operations surface.
2. Surpass Bumpa with stronger finance intelligence, AI operations, and credit-readiness tooling.

## Success Definition
A release is considered parity-or-better when MoniDesk supports:
- Omnichannel selling (in-store POS + online storefront + shareable checkout/order links).
- Full order lifecycle automation (pending, paid, fulfillment, cancellation, refunds).
- Invoicing and receipts with reminders and payment-state tracking.
- CRM with import, grouping, and campaign messaging workflows.
- Team operations with role-based permissions and audit trails.
- Multi-location inventory and stock transfer workflows.
- Payments, shipping, analytics, and marketing integrations.

A release is considered surpass when MoniDesk additionally provides:
- Event-aware AI copilot with prescriptive actions.
- Explainable credit-readiness and lender export workflows.
- Cashflow forecasting and profit-protection automation.
- Workflow automation engine and external developer platform.

## Ticket Convention
`<Phase>-<Epic>-<Ticket>`
- Example: `P2-E6-003`
- Phase: `P1`, `P2`, `P3`, `P4`

## Phases and Milestones

### P1 - Operational Foundation (Core System Layer)
Milestones: `M0`, `M1`, `M2`, `M3`

### P2 - Commerce Parity (Bumpa Match Layer)
Milestones: `M4`, `M5`, `M6`

### P3 - Growth and Scale (Parity+ Layer)
Milestones: `M7`, `M8`

### P4 - Differentiation and Moat (Surpass Layer)
Milestones: `M9`, `M10`

---

## P1 Backlog: Operational Foundation

### Epic P1-E0: Platform Enablers
- `P1-E0-001` Data model ADR for orders, invoices, customers, memberships, audit logs
  - Type: Architecture
  - Depends on: None
  - Acceptance: entity boundaries and state transitions approved.
- `P1-E0-002` Extend auth context to resolve user + business + role
  - Type: Backend
  - Depends on: `P1-E0-001`
  - Acceptance: role context available in every protected endpoint.
- `P1-E0-003` Shared audit logging utility for domain mutations
  - Type: Backend
  - Depends on: `P1-E0-001`
  - Acceptance: audit helper reusable from routers/services.
- `P1-E0-004` Test scaffolding and OpenAPI snapshot extension for new modules
  - Type: QA
  - Depends on: `P1-E0-001`
  - Acceptance: baseline integration tests for each new router.

### Epic P1-E1: Order Management Domain
- `P1-E1-001` DB migration for `orders` and `order_items`
  - Type: Backend/DB
  - Depends on: `P1-E0-001`
  - Acceptance: status, totals, customer reference, timestamps supported.
- `P1-E1-002` Order status machine and transition guards
  - Type: Backend
  - Depends on: `P1-E1-001`
  - Acceptance: invalid transitions return deterministic errors.
- `P1-E1-003` API create order (`POST /orders`)
  - Type: Backend
  - Depends on: `P1-E1-001`, `P1-E1-002`
  - Acceptance: order totals computed server-side and tenant-safe.
- `P1-E1-004` API list/filter orders (`GET /orders`)
  - Type: Backend
  - Depends on: `P1-E1-001`
  - Acceptance: status/date/channel/customer filters available.
- `P1-E1-005` API update order status (`PATCH /orders/{id}/status`)
  - Type: Backend
  - Depends on: `P1-E1-002`
  - Acceptance: transitions validated and audit logged.
- `P1-E1-006` Idempotent order-to-sale conversion logic
  - Type: Backend
  - Depends on: `P1-E1-003`, `P1-E1-005`
  - Acceptance: no duplicate financial postings.
- `P1-E1-007` Pending-order timeout and auto-cancel policy
  - Type: Backend
  - Depends on: `P1-E1-002`
  - Acceptance: configurable cancellation window per business.
- `P1-E1-008` Frontend orders workspace and status controls
  - Type: Frontend
  - Depends on: `P1-E1-003`, `P1-E1-004`, `P1-E1-005`
  - Acceptance: create, view, update order lifecycle in UI.
- `P1-E1-009` POS quick-order interaction baseline (scanner-ready input)
  - Type: Frontend
  - Depends on: `P1-E1-008`
  - Acceptance: rapid cart interactions and keyboard-first flow.

### Epic P1-E2: Invoicing and Payment Status (Core)
- `P1-E2-001` DB migration for `invoices` and `invoice_events`
  - Type: Backend/DB
  - Depends on: `P1-E0-001`
  - Acceptance: draft/sent/paid/overdue/cancelled states supported.
- `P1-E2-002` API create and send invoice
  - Type: Backend
  - Depends on: `P1-E2-001`, `P1-E3-001`
  - Acceptance: invoice links to customer/order where present.
- `P1-E2-003` API mark invoice paid with reconciliation metadata
  - Type: Backend
  - Depends on: `P1-E2-001`, `P1-E1-006`
  - Acceptance: idempotent payment updates and traceable events.
- `P1-E2-004` Reminder dispatch abstraction (manual trigger first)
  - Type: Backend
  - Depends on: `P1-E2-001`
  - Acceptance: reminder events logged for auditability.
- `P1-E2-005` Frontend invoice workspace (create/list/pay)
  - Type: Frontend
  - Depends on: `P1-E2-002`, `P1-E2-003`
  - Acceptance: core invoice lifecycle manageable in UI.
- `P1-E2-006` Receipt/invoice template strategy doc
  - Type: Product/Design
  - Depends on: None
  - Acceptance: variable schema and rendering strategy finalized.

### Epic P1-E3: CRM Core
- `P1-E3-001` DB migration for `customers`, `customer_tags`, `customer_tag_links`
  - Type: Backend/DB
  - Depends on: `P1-E0-001`
  - Acceptance: customer identity and grouping primitives available.
- `P1-E3-002` API customer CRUD + search filters
  - Type: Backend
  - Depends on: `P1-E3-001`
  - Acceptance: filter by name/phone/email and tags.
- `P1-E3-003` Customer linking on orders and invoices
  - Type: Backend
  - Depends on: `P1-E3-001`, `P1-E1-001`, `P1-E2-001`
  - Acceptance: tenant-safe cross-entity references.
- `P1-E3-004` Customer CSV import endpoint
  - Type: Backend
  - Depends on: `P1-E3-001`
  - Acceptance: import summary includes valid/rejected rows.
- `P1-E3-005` Frontend CRM workspace (list/create/edit/tag)
  - Type: Frontend
  - Depends on: `P1-E3-002`
  - Acceptance: operators can manage customers without API tools.
- `P1-E3-006` Dashboard customer insight widget
  - Type: Backend + Frontend
  - Depends on: `P1-E3-003`
  - Acceptance: repeat buyers and top customers card visible.

### Epic P1-E4: Staff Roles, Permissions, and Audit
- `P1-E4-001` DB migration for `business_memberships`
  - Type: Backend/DB
  - Depends on: `P1-E0-001`
  - Acceptance: owner/admin/staff roles with backward compatibility.
- `P1-E4-002` Permission matrix and policy dependency middleware
  - Type: Backend
  - Depends on: `P1-E4-001`, `P1-E0-002`
  - Acceptance: endpoint-level role guards enforced.
- `P1-E4-003` Team management API (invite/add/remove/change role)
  - Type: Backend
  - Depends on: `P1-E4-001`, `P1-E4-002`
  - Acceptance: membership lifecycle fully manageable by owner/admin.
- `P1-E4-004` Audit log storage + query API
  - Type: Backend
  - Depends on: `P1-E0-003`
  - Acceptance: filterable logs by actor/action/date/resource.
- `P1-E4-005` Frontend team and roles page
  - Type: Frontend
  - Depends on: `P1-E4-003`
  - Acceptance: role assignment and member management from UI.
- `P1-E4-006` Frontend audit timeline page
  - Type: Frontend
  - Depends on: `P1-E4-004`
  - Acceptance: searchable activity history for operators.

---

## P2 Backlog: Commerce Parity (Match Bumpa)

### Epic P2-E5: Online Storefront and Catalog Publishing
- `P2-E5-001` DB schema for storefront config (branding, domain, policy pages)
  - Type: Backend/DB
  - Depends on: `P1-E1-001`, `P1-E3-001`
  - Acceptance: per-business storefront config persisted.
- `P2-E5-002` Catalog publish controls (product/variant visibility)
  - Type: Backend
  - Depends on: `P2-E5-001`
  - Acceptance: unpublished items hidden from public storefront.
- `P2-E5-003` Public storefront APIs (browse/search/product detail)
  - Type: Backend
  - Depends on: `P2-E5-002`
  - Acceptance: anonymous read endpoints with rate limits.
- `P2-E5-004` Frontend hosted storefront page templates
  - Type: Frontend
  - Depends on: `P2-E5-003`
  - Acceptance: mobile-first storefront renders catalog and product pages.
- `P2-E5-005` Custom domain and DNS verification flow
  - Type: Platform
  - Depends on: `P2-E5-004`
  - Acceptance: business can attach verified custom domain.
- `P2-E5-006` SEO and metadata controls for storefront pages
  - Type: Frontend + Backend
  - Depends on: `P2-E5-004`
  - Acceptance: title/meta/open graph fields configurable.

### Epic P2-E6: Checkout, Payments, and Auto-Paid Confirmation
- `P2-E6-001` Checkout session model and API
  - Type: Backend
  - Depends on: `P1-E1-001`, `P2-E5-003`
  - Acceptance: shareable checkout links create pending orders.
- `P2-E6-002` Payment provider abstraction layer
  - Type: Backend
  - Depends on: `P2-E6-001`
  - Acceptance: provider adapter interface supports at least one gateway.
- `P2-E6-003` Payment webhook processing and signature verification
  - Type: Backend
  - Depends on: `P2-E6-002`
  - Acceptance: secure webhook validation with idempotency keys.
- `P2-E6-004` Auto-mark orders paid on successful gateway callback
  - Type: Backend
  - Depends on: `P2-E6-003`, `P1-E1-005`
  - Acceptance: order status updates and sales conversion triggered once.
- `P2-E6-005` Failed and pending payment recovery flows
  - Type: Backend + Frontend
  - Depends on: `P2-E6-001`, `P2-E6-003`
  - Acceptance: retry and expiration handling visible in UI.
- `P2-E6-006` Payments operations dashboard and reconciliation report
  - Type: Backend + Frontend
  - Depends on: `P2-E6-004`
  - Acceptance: reconciled vs unreconciled transactions view.

### Epic P2-E7: Shipping and Delivery Operations
- `P2-E7-001` Shipping settings model (zones, carriers, service rules)
  - Type: Backend/DB
  - Depends on: `P1-E1-001`
  - Acceptance: configurable shipping profile per business.
- `P2-E7-002` Carrier provider abstraction and connector base
  - Type: Backend
  - Depends on: `P2-E7-001`
  - Acceptance: pluggable provider contracts for rates and tracking.
- `P2-E7-003` Checkout shipping-rate quote and selection flow
  - Type: Backend + Frontend
  - Depends on: `P2-E7-002`, `P2-E6-001`
  - Acceptance: buyer can choose rate before payment.
- `P2-E7-004` Shipment creation and label purchase workflow
  - Type: Backend
  - Depends on: `P2-E7-003`
  - Acceptance: shipment record linked to order fulfillment status.
- `P2-E7-005` Tracking sync and status propagation to orders
  - Type: Backend
  - Depends on: `P2-E7-004`
  - Acceptance: in-transit/delivered updates reflected in order timeline.
- `P2-E7-006` Ops UI for shipping management
  - Type: Frontend
  - Depends on: `P2-E7-004`, `P2-E7-005`
  - Acceptance: staff can create shipments and track progress.

### Epic P2-E8: Multi-Location Inventory and Fulfillment
- `P2-E8-001` DB migration for `locations` and location membership scope
  - Type: Backend/DB
  - Depends on: `P1-E4-001`
  - Acceptance: businesses can define multiple stock locations.
- `P2-E8-002` Location-aware inventory ledger and stock queries
  - Type: Backend
  - Depends on: `P2-E8-001`
  - Acceptance: stock computed per variant per location.
- `P2-E8-003` Inter-location stock transfer workflow
  - Type: Backend + Frontend
  - Depends on: `P2-E8-002`
  - Acceptance: transfer requests adjust source and destination ledgers.
- `P2-E8-004` Location-based low-stock and reorder alerts
  - Type: Backend
  - Depends on: `P2-E8-002`
  - Acceptance: low-stock endpoint supports location filters.
- `P2-E8-005` Location-aware order allocation policy
  - Type: Backend
  - Depends on: `P2-E8-002`, `P1-E1-006`
  - Acceptance: orders reserve/fulfill from explicit location.
- `P2-E8-006` UI for location setup and stock visibility
  - Type: Frontend
  - Depends on: `P2-E8-001`, `P2-E8-002`
  - Acceptance: manager can switch and manage location context.

### Epic P2-E9: Connected Apps Foundation
- `P2-E9-001` Integration credential vault and secret rotation policy
  - Type: Platform/Security
  - Depends on: `P1-E0-001`
  - Acceptance: integration secrets encrypted and rotatable.
- `P2-E9-002` App installation lifecycle (connect/disconnect/permissions)
  - Type: Backend
  - Depends on: `P2-E9-001`
  - Acceptance: install state and scopes tracked per business.
- `P2-E9-003` Event outbox and webhook delivery engine
  - Type: Backend/Infra
  - Depends on: `P2-E9-001`
  - Acceptance: reliable retries and dead-letter handling.
- `P2-E9-004` Integration center UI
  - Type: Frontend
  - Depends on: `P2-E9-002`
  - Acceptance: user can connect and monitor integrations.
- `P2-E9-005` Analytics connectors baseline (Meta Pixel, GA)
  - Type: Backend + Frontend
  - Depends on: `P2-E9-003`, `P2-E5-004`
  - Acceptance: storefront events emitted to installed tools.
- `P2-E9-006` Messaging connector baseline (WhatsApp provider abstraction)
  - Type: Backend
  - Depends on: `P2-E9-003`, `P1-E3-001`
  - Acceptance: outbound message dispatch capability exposed.

---

## P3 Backlog: Growth and Scale (Parity+)

### Epic P3-E10: CRM Campaigns and Messaging Workflows
- `P3-E10-001` Customer group management (saved dynamic segments)
  - Type: Backend + Frontend
  - Depends on: `P1-E3-001`, `P1-E3-005`
  - Acceptance: dynamic groups by behavior and attributes.
- `P3-E10-002` Bulk campaign composer and send orchestration
  - Type: Backend + Frontend
  - Depends on: `P3-E10-001`, `P2-E9-006`
  - Acceptance: campaigns queued and status tracked.
- `P3-E10-003` Consent and opt-out framework
  - Type: Backend
  - Depends on: `P3-E10-002`
  - Acceptance: suppression lists enforced automatically.
- `P3-E10-004` Campaign performance metrics
  - Type: Backend + Frontend
  - Depends on: `P3-E10-002`
  - Acceptance: sent/delivered/open/reply (where available) views.
- `P3-E10-005` Automated retention triggers (repeat purchase nudges)
  - Type: Backend
  - Depends on: `P3-E10-001`, `P2-E9-003`
  - Acceptance: trigger templates runnable by schedule/event.
- `P3-E10-006` Message template library and governance
  - Type: Product + Backend
  - Depends on: `P3-E10-002`
  - Acceptance: reusable templates with approval states.

### Epic P3-E11: Invoicing and Receivables Advanced
- `P3-E11-001` Multi-currency invoicing and FX conversion policy
  - Type: Backend
  - Depends on: `P1-E2-001`
  - Acceptance: invoice currency independent from base currency.
- `P3-E11-002` Branded invoice/receipt template engine
  - Type: Backend + Frontend
  - Depends on: `P1-E2-006`
  - Acceptance: template variants selectable per business.
- `P3-E11-003` Partial payments and installment schedules
  - Type: Backend
  - Depends on: `P1-E2-003`
  - Acceptance: invoice balance and payment schedule tracked.
- `P3-E11-004` Automated reminder schedules and escalation rules
  - Type: Backend
  - Depends on: `P1-E2-004`, `P2-E9-006`
  - Acceptance: configurable reminder cadence.
- `P3-E11-005` Accounts receivable aging dashboard
  - Type: Backend + Frontend
  - Depends on: `P3-E11-003`, `P3-E11-004`
  - Acceptance: aging buckets and overdue summaries available.
- `P3-E11-006` Monthly statements and export packs
  - Type: Backend
  - Depends on: `P3-E11-005`
  - Acceptance: downloadable statements by customer/date range.

### Epic P3-E12: Analytics and Decision Intelligence
- `P3-E12-001` Analytical data mart for commerce metrics
  - Type: Data/Backend
  - Depends on: `P1-E1-006`, `P1-E2-003`, `P1-E3-003`
  - Acceptance: denormalized metric tables refreshed reliably.
- `P3-E12-002` Channel profitability and net margin dashboards
  - Type: Backend + Frontend
  - Depends on: `P3-E12-001`
  - Acceptance: channel-level P&L visibility.
- `P3-E12-003` Cohort and repeat-customer analytics
  - Type: Backend + Frontend
  - Depends on: `P3-E12-001`, `P1-E3-003`
  - Acceptance: retention and repeat-rate charts.
- `P3-E12-004` Inventory aging and stockout impact analytics
  - Type: Backend + Frontend
  - Depends on: `P2-E8-002`
  - Acceptance: aged inventory and stockout trend metrics.
- `P3-E12-005` Marketing attribution ingestion
  - Type: Backend
  - Depends on: `P2-E9-005`
  - Acceptance: top-funnel to order attribution summary.
- `P3-E12-006` Report exports and scheduled summaries
  - Type: Backend + Frontend
  - Depends on: `P3-E12-002`, `P3-E12-003`, `P3-E12-004`
  - Acceptance: CSV/PDF export with scheduled email option.

### Epic P3-E13: POS Mobility and Offline Resilience
- `P3-E13-001` Mobile POS optimized UI and route partitioning
  - Type: Frontend
  - Depends on: `P1-E1-009`
  - Acceptance: touchscreen-optimized POS workflow.
- `P3-E13-002` Offline order queue and local persistence
  - Type: Frontend + Backend
  - Depends on: `P3-E13-001`
  - Acceptance: orders captured offline and synced later.
- `P3-E13-003` Conflict resolution policy for delayed sync
  - Type: Backend
  - Depends on: `P3-E13-002`
  - Acceptance: deterministic merge rules for stock/order conflicts.
- `P3-E13-004` Hardware scanner and receipt printer integration hooks
  - Type: Frontend
  - Depends on: `P3-E13-001`
  - Acceptance: device integration abstraction available.
- `P3-E13-005` Shift closeout and cash reconciliation workflow
  - Type: Backend + Frontend
  - Depends on: `P1-E4-002`, `P3-E13-001`
  - Acceptance: per-shift summaries and discrepancy reports.
- `P3-E13-006` POS performance and reliability SLO tests
  - Type: QA/Perf
  - Depends on: `P3-E13-002`
  - Acceptance: defined latency and sync reliability thresholds.

### Epic P3-E14: Security, Reliability, and Compliance Hardening
- `P3-E14-001` Fine-grained RBAC v2 (resource/action-level controls)
  - Type: Backend/Security
  - Depends on: `P1-E4-002`
  - Acceptance: role policies extend to module/action scope.
- `P3-E14-002` Immutable audit archive and retention policy
  - Type: Backend/Infra
  - Depends on: `P1-E4-004`
  - Acceptance: tamper-resistant log archive process defined.
- `P3-E14-003` Backup, restore, and disaster recovery runbooks
  - Type: Infra
  - Depends on: `P1-E0-001`
  - Acceptance: backup restore tested in non-prod.
- `P3-E14-004` Platform observability dashboards and SLO alerts
  - Type: Backend/Infra
  - Depends on: `P1-E0-004`
  - Acceptance: SLO breach alerts available for critical flows.
- `P3-E14-005` Security testing cycle (SAST/DAST/pen test)
  - Type: Security
  - Depends on: `P3-E14-001`
  - Acceptance: critical findings addressed before GA.
- `P3-E14-006` Data privacy controls (PII export/delete workflow)
  - Type: Backend
  - Depends on: `P1-E3-001`
  - Acceptance: admin-driven customer data lifecycle controls.

---

## P4 Backlog: Differentiation and Moat (Surpass)

### Epic P4-E15: AI Operations Copilot
- `P4-E15-001` Event-aware feature store for AI context (orders, refunds, stockouts, campaigns)
  - Type: Data/Backend
  - Depends on: `P3-E12-001`, `P2-E9-003`
  - Acceptance: AI context no longer limited to simple summary fields.
- `P4-E15-002` AI insight types v2 (anomaly, urgency, opportunity)
  - Type: Backend/AI
  - Depends on: `P4-E15-001`
  - Acceptance: structured insight taxonomy with confidence metadata.
- `P4-E15-003` Prescriptive AI actions with approval workflow
  - Type: Backend + Frontend
  - Depends on: `P4-E15-002`, `P1-E4-002`
  - Acceptance: user can approve/reject suggested actions.
- `P4-E15-004` Natural-language analytics assistant over curated metrics
  - Type: Backend + Frontend
  - Depends on: `P3-E12-001`
  - Acceptance: NL query answers grounded in approved metric layer.
- `P4-E15-005` Proactive risk alerts (cashflow, stockout, refund spikes)
  - Type: Backend
  - Depends on: `P4-E15-001`
  - Acceptance: configurable alert thresholds and channels.
- `P4-E15-006` AI governance and response traceability
  - Type: Backend/Security
  - Depends on: `P4-E15-002`
  - Acceptance: prompts, context snapshots, and outputs auditable.

### Epic P4-E16: Credit and Finance Intelligence 2.0
- `P4-E16-001` Credit model redesign with trend-based explainable factors
  - Type: Backend/Data
  - Depends on: `P3-E12-001`
  - Acceptance: score factors include trend windows and rationale.
- `P4-E16-002` Cashflow forecast engine (short and medium horizon)
  - Type: Backend/Data
  - Depends on: `P3-E12-001`
  - Acceptance: forecast intervals and error bounds exposed.
- `P4-E16-003` Scenario simulator (pricing, expense, restock what-if)
  - Type: Backend + Frontend
  - Depends on: `P4-E16-002`
  - Acceptance: side-by-side scenario outcomes available.
- `P4-E16-004` Lender-ready export pack (statements, trends, score explanation)
  - Type: Backend
  - Depends on: `P4-E16-001`, `P3-E11-006`
  - Acceptance: one-click export bundle generated.
- `P4-E16-005` Finance guardrails and policy alerts
  - Type: Backend
  - Depends on: `P4-E16-002`
  - Acceptance: alerts for margin collapse, expense spikes, weak liquidity.
- `P4-E16-006` Credit improvement action planner
  - Type: Backend + Frontend
  - Depends on: `P4-E16-001`, `P4-E15-003`
  - Acceptance: prioritized actions tied to measurable score impact.

### Epic P4-E17: Workflow Automation Engine
- `P4-E17-001` Rules engine core (event trigger -> condition -> action)
  - Type: Backend
  - Depends on: `P2-E9-003`
  - Acceptance: reusable automation runtime with versioned rules.
- `P4-E17-002` Action adapters (message, tag customer, create task, discount)
  - Type: Backend
  - Depends on: `P4-E17-001`
  - Acceptance: minimum action set runnable in production.
- `P4-E17-003` Automation templates (abandoned cart, overdue invoice, low stock)
  - Type: Product + Backend
  - Depends on: `P4-E17-002`
  - Acceptance: template library installable per business.
- `P4-E17-004` No-code workflow builder UI
  - Type: Frontend
  - Depends on: `P4-E17-001`, `P4-E17-002`
  - Acceptance: non-technical operator can create and test workflow.
- `P4-E17-005` Workflow run logs and debugging console
  - Type: Backend + Frontend
  - Depends on: `P4-E17-001`
  - Acceptance: each run has step-by-step execution history.
- `P4-E17-006` Safety guardrails (rate limits, loop prevention, rollback)
  - Type: Backend
  - Depends on: `P4-E17-001`
  - Acceptance: runaway automations automatically contained.

### Epic P4-E18: Developer Platform and Ecosystem Moat
- `P4-E18-001` Public API v1 scope and authentication model
  - Type: Architecture + Backend
  - Depends on: `P2-E9-001`, `P1-E4-002`
  - Acceptance: external API boundary and auth strategy approved.
- `P4-E18-002` Public REST endpoints and tenant-safe API keys
  - Type: Backend
  - Depends on: `P4-E18-001`
  - Acceptance: API key rotation and scoped access supported.
- `P4-E18-003` Outbound webhook subscriptions for third-party apps
  - Type: Backend
  - Depends on: `P2-E9-003`, `P4-E18-001`
  - Acceptance: subscribers receive signed events with retries.
- `P4-E18-004` Developer portal and API documentation site
  - Type: Frontend/Docs
  - Depends on: `P4-E18-002`
  - Acceptance: onboarding guides and reference docs published.
- `P4-E18-005` SDK starter kits and integration quickstarts
  - Type: DevRel
  - Depends on: `P4-E18-004`
  - Acceptance: sample apps for common integration scenarios.
- `P4-E18-006` App marketplace governance and listing workflow
  - Type: Product + Backend
  - Depends on: `P2-E9-002`, `P4-E18-003`
  - Acceptance: partner app review and publication process defined.

---

## Cross-Phase Critical Path
1. Foundation: `P1-E0-001` -> `P1-E4-001` -> `P1-E4-002`
2. Order and payment spine: `P1-E1-001/002/003/005/006` -> `P2-E6-001/003/004`
3. Storefront commerce: `P2-E5-003/004` + `P2-E6-001/004` + `P2-E7-003/004`
4. Operational scale: `P2-E8-002/003/005` + `P3-E13-002/003`
5. Data and intelligence: `P3-E12-001` -> `P4-E15-*` and `P4-E16-*`
6. Ecosystem moat: `P2-E9-003` -> `P4-E17-*` and `P4-E18-*`

## Milestone-to-Epic Mapping
- `M0`: P1-E0, P1-E4-001
- `M1`: P1-E1 core backend + P1-E1-008
- `M2`: P1-E2, P1-E3 core
- `M3`: P1-E4 completion and regression hardening
- `M4`: P2-E5 storefront baseline
- `M5`: P2-E6 payments + P2-E7 shipping baseline
- `M6`: P2-E8 multi-location + P2-E9 integration center baseline
- `M7`: P3-E10 CRM campaigns + P3-E11 invoicing advanced
- `M8`: P3-E12 analytics + P3-E13 POS offline + P3-E14 hardening
- `M9`: P4-E15 AI copilot + P4-E16 finance intelligence
- `M10`: P4-E17 automation engine + P4-E18 developer platform

## Definition of Done (Program Standard)
- Migrations include downgrade path and backfill plan.
- APIs documented with examples and contract tests.
- Tenant isolation and role permissions validated.
- Core flows have integration tests for success and failure modes.
- UI includes loading/error/empty/success states.
- Audit coverage exists for sensitive mutations.
- Observability includes logs, metrics, and alert hooks for new critical flows.

## Key Program Risks
- Domain overlap risk across orders/sales/invoices.
  - Mitigation: lock source-of-truth rules in `P1-E0-001`.
- Integration complexity (payments, shipping, messaging).
  - Mitigation: strict provider adapter interfaces and phased connector rollout.
- Data integrity risk with offline and multi-location inventory.
  - Mitigation: idempotency keys, conflict policy, reconciliation jobs.
- Scope creep in AI and automation layers.
  - Mitigation: ship deterministic rules first, then advanced inference.

## Immediate Next 10 Tickets (If Implementation Starts)
1. `P1-E0-001`
2. `P1-E4-001`
3. `P1-E0-002`
4. `P1-E1-001`
5. `P1-E1-002`
6. `P1-E0-003`
7. `P1-E1-003`
8. `P1-E1-005`
9. `P1-E1-006`
10. `P1-E3-001`

This order builds the minimum stable spine before adding storefront, integrations, and intelligence layers.
