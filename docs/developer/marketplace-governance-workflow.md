# App Marketplace Governance Workflow

## Objective
Provide controlled publication of partner apps with auditable review decisions.

## Entities
- Listing record: metadata, requested scopes, status, review notes.
- Reviewer actions: approve, reject, or move to under-review.
- Publication action: publish/unpublish toggle with timestamp.

## State Machine
1. `draft`
2. `submitted`
3. `under_review` (optional)
4. `approved` or `rejected`
5. `published` (only from `approved`)

Unpublish transitions `published -> approved`.

## Required Checks Before Approval
- Scope request aligns with business need.
- Data access scope is minimal.
- Webhook behavior and retry expectations are documented.
- Support and incident contact exists.

## Audit and Traceability
- Every create/submit/review/publish action is written to audit logs.
- Review notes are persisted on listing.

## Rejection Handling
- Rejected listings can be updated and resubmitted.
- Review notes should include remediation steps.
