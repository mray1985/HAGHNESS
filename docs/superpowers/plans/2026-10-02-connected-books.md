# Private connected books implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Track completed steps below.

**Goal:** Implement the Day 8 profile-protected document and bookkeeping workflow, including provider-backed MFA, encrypted versioned storage, restoration, and a traceable HATax draft.

**Architecture:** A separate Python HTTPS API uses Cognito through a browser session, PostgreSQL for permission/ledger metadata, S3/KMS for document bytes and AWS Backup for recovery. Append-only accounting events drive projections; real provider adapters remain distinguishable from test doubles. Preserve the existing calculator and matching-document design.

**Tech stack:** Python, PostgreSQL, AWS Cognito/S3/KMS/Backup, container deployment, browser HTML/JavaScript. Pin SDK/auth/database dependencies after verifying current supported versions; do not install globally.

**Spec:** ../specs/2026-10-02-connected-books-design.md, approved October 2, 2026. Execution method: native implementation in this chat, based on the proposed approval handoff.

## Global constraints

- Documents are linked to client, business and tax year; every server action checks explicit membership.
- One required-MFA session serves normal document access; never invent an MFA claim from a bearer token's existence.
- Preserve source originals and correction history. Encryption keys live outside application code.
- Missing entries, missing receipts, recorded support and reviewed support remain separate states.
- Reporting derives from effective postings; reversals/replacements must not double count.
- Reserve choice is not tax liability, movement or payment. Owner payments and payroll obligations remain separate.
- No real client data, live funds, false filing-readiness claims or unapproved chargeable provisioning during development.
- Full completion requires actual provider-backed isolation, restore and workflow evidence, not only mocks.

## Review focus

1. A revoked profile grant must prevent a later read in the same session (Tasks 1–3).
2. Retried uploads/corrections/payments must not duplicate records or postings (Tasks 3–5).
3. Backup restoration must recover matching object versions and database permissions (Task 4).
4. Future or wrong-year transactions must not contaminate annual totals (Task 5).
5. A changed ledger revision must invalidate previously reviewed drafts (Tasks 5–6).

## File map and shared contracts

- `ha/connected/domain.py`: immutable Principal, Scope, Grant, DocumentVersion, Posting and LedgerEvent value types; money represented as integer minor units.
- `ha/connected/access.py`: `authorize(principal, scope, action, repository) -> None`, deny by default.
- `ha/connected/auth.py`: `complete_login(code, state, verifier) -> Session`; `require_session(cookie) -> Principal`; `logout(cookie) -> None` using verified Cognito and server-owned sessions.
- `ha/connected/repository.py`: `Repository` protocol for grants, version metadata, events and projections; `ha/connected/postgres.py` implements transaction boundaries.
- `ha/connected/storage.py`: `ObjectStore` protocol; `ha/connected/aws_storage.py` implements private S3/KMS streaming and version metadata.
- `ha/connected/documents.py`: `upload(principal, scope, stream, metadata, idempotency_key) -> DocumentVersion`; `read(principal, scope, document_id, version_id) -> stream`; `correct(...) -> DocumentVersion`.
- `ha/connected/ledger.py`: `post_event(principal, scope, event) -> LedgerEvent`; `correct_event(principal, scope, event_id, replacement, key) -> LedgerEvent`.
- `ha/connected/draft.py`: `project(principal, scope, period, repository) -> DraftSnapshot`.
- `ha/connected/api.py`: authenticated HTTP routes, CSRF enforcement and sanitized errors; separate process from legacy public calculator.
- `migrations/001_connected.sql`: tables, foreign keys, profile/year checks, unique idempotency keys and indexes.
- `infra/connected.yaml`: reviewed deployable resources; no embedded secrets or automatic deployment.
- `web/connected.html`, `web/connected.js`, `web/connected.css`: authenticated review interface.
- `tests/test_connected_access.py`, `tests/test_connected_documents.py`, `tests/test_connected_ledger.py`, `tests/test_connected_api.py`: focused behavioral tests.
- `scripts/verify_connected_environment.py`: real-provider preflight and evidence output, never reports mocks as provider verification.
- `docs/CONNECTED-VERIFICATION.md`: measured test/deploy/restore evidence and incomplete requirements.

## Task 1: Scope and deny-by-default permissions

- [ ] Write failing tests for Orchard owner versus Cedar owner at client/business/year scope. Test read/upload/correct/restore actions, missing grants, mismatched business ownership, expired principal, and revoked grants in an otherwise active session. Assert PermissionError and no storage invocation for denied requests.
- [ ] Run `python -m unittest tests.test_connected_access -v`; expect new tests to fail before implementation.
- [ ] Implement domain types and `authorize`, using repository membership on every operation rather than cached client selection. Add migration constraints that prevent document/business references crossing profiles.
- [ ] Run access tests; require pass and commit the domain/access slice.

## Task 2: PostgreSQL and real MFA session integration

- [ ] Verify supported dependency versions from primary documentation and create an isolated project environment/lockfile. Read config references only; never emit credentials in logs.
- [ ] Write failing tests for bad OAuth state, invalid issuer/signature/token purpose, expiry, CSRF, logout/revocation, and a session opened through a required-MFA login flow. Assert routine document requests reuse the session but recheck grants.
- [ ] Implement migrations, repository transaction API, Cognito authorization-code/PKCE flow, token validation, and opaque server session cookies. Disable connected routes when provider/session configuration is absent. Never accept a client-supplied user ID as authentication.
- [ ] Run unit/integration tests against a local test PostgreSQL when available. Explicitly record missing database/provider verification rather than skip and report pass.
- [ ] Prepare deployment resources with required MFA, HTTPS, private RDS, role-bound KMS, private versioned S3, log redaction and separate development/production resources. Do not provision until a quote and deployment authorization exist.
- [ ] In an authorized development provider environment, complete actual MFA once and two document requests without another login; test wrong profile and expired session. Save sanitized evidence and commit slice.

## Task 3: Protected originals and document corrections

- [ ] Write failing tests proving denied list/read/upload/correct cannot disclose metadata or invoke object storage; repeat upload key returns the same version; originals retain hash/bytes; corrections append actor/time/reason/prior-version links.
- [ ] Implement S3/KMS adapter and document service with server-generated object keys, 20 MiB upload limit, PDF/JPEG/PNG/plain-text type allowlist, content validation and quarantine scan status. Non-clean uploads cannot be downloaded. Read streams reauthorize, and metadata/object transactions use pending/ready states with recovery handling.
- [ ] Test failed object write, failed database commit, key permission denial, truncated stream, wrong object version and hash mismatch. No failure may silently report a ready document.
- [ ] Run unit tests plus actual development upload/read/correction with fictional bytes. Confirm original and corrected versions independently readable, wrong-profile denial and no public object access. Commit slice with evidence.

## Task 4: Consistent backup and restoration

- [ ] Define development daily backup retention 35 days, monthly snapshots 12 months, RDS PITR 35 days; separate protected backup vault/account. Preserve key access during recovery. Production tax-record retention remains a policy decision before onboarding.
- [ ] Add failing restore reconciliation tests: missing metadata version, wrong hash, missing encryption-key access, recovered permissions pointing to another profile. Assert recovery cannot be promoted if any mismatch exists.
- [ ] Implement backup/restore runbook and verifier using a manifest of document IDs, version IDs, hashes, database snapshot/recovery point, key references and timestamps. Restore only to isolated resources initially.
- [ ] Run a real fictional-file and metadata restore, prove byte equality and permission isolation, and measure elapsed time and recovery-point age. Compare actual results with proposed RPO 24h/RTO 4h; do not claim targets verified unless demonstrated.
- [ ] Commit configuration, reconciliation logic and sanitized restore evidence.

## Task 5: Ledger correction and draft projection

- [ ] Write failing fixture tests using `docs/fixtures/day8-connected-workflow.json`: income 150000 minor units, expenses 32000 after correction, monthly/quarterly/annual book profit 118000, reserve scenario 37500, recorded unverified owner payment 10000 and confirmed payment zero.
- [ ] Add tests for balanced postings, duplicate source IDs, duplicate correction keys, negative/invalid monetary input, profile/period isolation, payroll account separation and missing-receipt review. Test boundary dates, leap days and mixed currencies; refuse unsupported mixed-currency totals rather than sum them.
- [ ] Implement ledger posting and atomic reversal/replacement; aggregate effective postings by dates within scope. Owners' estimated payments post separately from operating expenses. Evidence/review states remain independent.
- [ ] Implement `project` returning ledger revision, source-linked book totals, reserve scenarios, tax-payment states and unresolved items. A changed revision invalidates prior review/signing state. Expose tax liability as unavailable when a complete supported calculation is absent; do not substitute book profit for AGI.
- [ ] Run fixture and PostgreSQL transaction tests. Run duplicate/retry/concurrent-correction cases against actual database constraints. Commit ledger/projection slice.

## Task 6: Protected connected review UI

- [ ] Implement the authenticated review interface and disclosure from the approved spec. Display profiles, business/year selector, documents/versions, recorded entries, review items, month/quarter/year totals, corrections, reserve and payment status.
- [ ] Add browser checks for login/MFA session reuse, inaccessible Cedar profile, missing receipt visible, correction history/original preserved and updated source-linked draft. Return authorization remains unavailable when required review items or calculation support are unresolved.
- [ ] Test on desktop and 390px width; render untrusted names/explanations as text. A material draft change clears prior final-review state. Record upload/correction/draft latency from the fictional scenario with environment details.
- [ ] Run existing and connected tests; commit UI with evidence.

## Task 7: Providers, costs and full-goal audit

- [ ] Carry forward the saved Schwab/IRA concept and locate the actual Day 7 proposal if supplied; never invent its terms. Verify account-opening/funding permissions and eligible contribution paths with provider documentation or agreement.
- [ ] Price the full AWS deployment: compute, database, networking, storage, MFA/auth tier, KMS, backup, logs and egress for stated region/volume. Obtain bank/refund-transfer quotes and fee-coverage terms; preserve zero-extra-charge client intent.
- [ ] Resolve Stripe Treasury US preview access or another eligible bank provider before implementing money movement. Financial Connections data access is not IRS payment permission. Test provider confirmations and replay/reversal behavior with sandbox accounts; no live funds in the fixture.
- [ ] Define separate explicit payment authorization and idempotency/status checks. Record real provider sandbox timings; pending/transferred/settled/IRS-confirmed states cannot be conflated. A manual IRS handoff is labeled manual and does not satisfy automatic IRS integration.
- [ ] Audit every Day 8 numbered requirement against implementation, rendered flows, provider-backed tests and restore evidence. Run the entire fictional card/cash/receipt/correction/payment-to-draft scenario end to end. Keep original matching-form, state, official-PDF and filing scope intact in subsequent plans.
- [ ] Update verification report with passed, failed, unavailable and unimplemented items. Only claim full goal completion when all required deployed behavior and provider measurements exist.

## Handoff and unavailable external inputs

Native execution is proposed/preserved. Written-plan review is required by the writing-plans workflow before implementation. Cloud account/role, provider access and a complete cost quote are separate deployment prerequisites; they must not prevent authorized local domain/API work after plan approval. Test doubles accelerate local tests but do not satisfy real MFA, encrypted cloud restore, database integration or bank confirmation acceptance.

Self-review: all Day 8 items map to Tasks 1–7; permissions and restore are provider-backed, ledger expectations preserve all fixture distinctions, and growth work includes cost/timing evidence. No task authorizes chargeable provisioning or real funds. The goal remains incomplete until the full audit passes.
