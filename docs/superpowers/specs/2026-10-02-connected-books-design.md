# HA Bookin' to HATax: private connected workflow

Status: architecture approved by the user October 2, 2026; implementation plan saved for review. No services provisioned. User confirmed this repository is the platform and there is no existing hosted MFA.

## Current evidence

Repository: mray1985/HAGHNESS, local Python standard-library HTTP server and HTML/JavaScript UI. Local code has no authentication/session, business/client profiles, storage provider, ledger, document access control, or backup implementation. The existing 45 Python tests pass but exercise legacy calculation behavior rather than the connected goal. Existing tax-law errors must be corrected separately before complete tax estimates are offered. No deployed URL or cloud account configuration was identified. AWS CLI and Docker were not found; Node is available. Preserve existing document-entry design and full 1040/1041 scope.

## Selected stack

Use a separate authenticated API alongside the legacy local calculator, with Python application services behind an HTTPS gateway. Select AWS Cognito user pools (required TOTP MFA), private S3 with customer-managed KMS encryption and versioning, RDS PostgreSQL for profile membership/ledger/document metadata, and AWS Backup for document recovery. Deploy the API as a container on ECS/Fargate with private database connectivity; use a backend-for-frontend session cookie for browser access. Region selection defaults to us-east-2 for a US development environment, subject to account availability and production requirements. Production and development use separate resources and keys.

This is a provider selection, not an account creation, subscription or deployment. A deployment needs a user-controlled AWS account, domain/HTTPS configuration, least-privilege deploy role and a priced resource plan. Do not commit credentials or provision chargeable resources without a concrete cost/deployment approval. Compare a unified Supabase stack and externally hosted Postgres/object storage at the plan stage if cost measurements make AWS unsuitable; the single-provider access/audit/backup boundary is the reason for this selection.

Source evidence: Cognito TOTP https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-mfa-totp.html; authentication https://docs.aws.amazon.com/cognito/latest/developerguide/authentication.html; RDS recovery https://docs.aws.amazon.com/AmazonRDS/latest/gettingstartedguide/managing-backup-restore.html; S3 backup https://docs.aws.amazon.com/aws-backup/latest/devguide/s3-backups.html. Pricing sources: https://aws.amazon.com/cognito/pricing/ and https://aws.amazon.com/s3/pricing/. Database, compute, gateway, KMS, backups, egress and logs must also be included in a measured quote; no total price has been established.

## One session and server-side access

Sign in once through Cognito using authorization-code/PKCE, complete required MFA, and exchange verified tokens for a Secure/HttpOnly/SameSite session cookie. Validate issuer, signature, audience/client, token purpose, expiry, state and nonce as applicable. A token's existence alone does not prove MFA; establish the required user-pool policy and authenticated challenge outcome. Expired/revoked sessions fail closed. Routine document access uses the same active session and membership check; no separate vault password.

Tables: principals; client_profiles; business_profiles; memberships (principal/profile/action grants); tax_cases (profile, business, tax year); documents; document_versions; ledger_events; evidence_links; review_events; tax_payments; reserve_choices; audit_events. Grants are explicit and tested by action, profile, business and year. UI selectors and user-supplied object keys never establish permission. IDs are opaque. Cross-profile guessed IDs return generic denied/not-found responses with no filename or metadata leak.

For upload/read/version/restore, authorize the session against the metadata record first. Object keys are server generated. Stream downloads through the authorized service so subsequent requests recheck membership; any future short-lived signed URL design must document its revocation window. Never grant the browser general bucket access. Enforce size/type bounds, upload quarantine and malware scanning before documents are available; reject traversal keys. Log IDs/action/outcome rather than document contents, SSNs or access tokens.

## Encryption and records

Block all public bucket access, require HTTPS and KMS encryption by bucket policy, and use task roles for key access. KMS keys exist outside code and are managed independently; database encryption and encrypted transport are required too. Separate restore role from normal runtime role. Key disablement/destruction and lost permissions are tested as recovery failure modes; encrypted backups are useless without retained usable keys.

Original source bytes and their SHA-256 hash are preserved in an immutable application record. Corrections append versions with actor, timestamp, reason and previous-version ID. No normal endpoint overwrites or deletes originals. Replacing a receipt and correcting an accounting classification are distinct events. Existing bookkeeping records missing a receipt remain recorded but have unresolved support; missing transactions are separate review items.

## Backup choice and proposed operational policy

Use S3 versioning plus AWS Backup to a separate backup vault/account, and RDS point-in-time backups. Proposed development retention: daily backup 35 days, monthly snapshots 12 months; database automated retention 35 days. Tax-record retention is a separate production policy and must be confirmed before real client onboarding. Do not implement irreversible retention locks as a default. Proposed recovery objectives: RPO 24 hours for documents, RTO 4 hours for a complete tested restore; measure rather than claim them.

Restore into isolated resources, verify byte hashes, reconcile document/version metadata and memberships, verify wrong-profile denial, then promote only with a recorded restore decision. Restore a fictional file and a database snapshot together. A successful list-backups call is not proof of restore success.

## Books to draft

Ledger events are balanced debit/credit postings using decimal minor units; every event has business, date, currency, provenance, idempotency key and review state. Source transaction IDs prevent duplicate bank/manual imports. Corrections reverse and replace earlier events in one transaction; reporting uses the effective postings, not a sum of originals plus replacements. Monthly/quarterly/annual totals are derived from the same event set. A payee's aggregate receipt can be recorded without every customer's identity; attach explanatory support for summarized cash income.

Card transactions preserve statement evidence and optional receipt; cash transactions preserve explanation and optional receipt. Evidence exists independently of review/approval. Unresolved support does not disappear, and a tax draft shows both recorded figures and unresolved classification/support items. Tax eligibility is not inferred from a category label alone.

Draft projections are rebuilt idempotently from a committed ledger revision and reviewed source facts. Retain links from each draft line back to events and documents. Book profit is not AGI or complete tax liability; owner estimated tax payments are payments/owner equity, not operating expense. Employee payroll obligations use distinct ledger accounts and workflows. Preserve limitations for unsupported tax years/states/1041 paths; do not call an existing bracket calculation a complete return.

## Reserve, payments and authorization

Reserve choices have percentage, basis, owner, business, effective dates and explicit consent. A 25% selection describes earmarked funds, not calculated tax or an IRS payment. Bank balance, reserve ledger, initiated transfer, settled transfer and IRS-confirmed payment are separate states. No UI alone marks a payment successful. Store payment year/type, amount, external reference and confirmation state; imported receipts are reviewed records, not proof that HA transmitted a payment.

Any optional extra-payment prompt shows amount, destination, tax year, payment type and date before a separate authorization. Production bank/provider support must be established before reserve movement. IRS payment support needs a permitted actual payment path and receipts; a general ACH API is not by itself an IRS integration. No live funds move in the development fixture.

## Disclosure and review journey

Proposed disclosure: 'HA Bookin’ connects your business records with HATax to build a draft throughout the year. You can review the information and supporting documents in one place. Missing records and questions remain visible. Before filing, confirm accuracy, resolve required items, review the final return, and authorize submission.'

Use Understand > Gather > Check > Do > Verify > Explain > Close consistently. Explain the difference between recorded, supported, reviewed and filed facts. The protected information area belongs inside the existing product session. Keep the previously specified matching-form UI and official-PDF mappings as part of the larger scope; this connected workflow supplies its facts rather than replaces it.

## Fictional acceptance scenario

Use two principals/profiles, Orchard Demo and Cedar Demo; only Orchard's owner may read its documents. No real taxpayer or bank identifiers. Use fixture at ../../fixtures/day8-connected-workflow.json.

Orchard October 2026: card sale 1000; cash aggregate sales 500 with explanation; supplies 100 corrected to 120 by reversal/replacement; advertising 200 recorded with missing receipt. Income 1500, expenses 320, book profit 1180. Earlier profit before correction is 1200. Quarterly and annual totals equal 1180 when October is the only populated month. Owner estimated payment 100 has no effect on book profit. A 25% of recorded-receipts reserve scenario is 375, not a tax calculation and not reduced by pretending it is a payment. Preserve original supplies support when correcting its accounting event.

Required evidence: authenticated MFA login; one session reads/uploads twice without another vault login; missing/expired token denial; wrong client/business/year denial on list/read/write/restore; version/hash evidence; isolated backup restore; ledger correction audit; monthly/quarterly/annual totals; missing-receipt review item; draft source trails; payment/reserve separation; no production filing readiness claim. Measure login, upload, correction, draft update and restore timings with environment details. Record each requirement as passed/failed/unimplemented.

## Banking and Schwab research deliverable

Keep a provider comparison recording eligibility, integration permissions, fees, implementation requirements, confirmation semantics and measured sandbox timings. Include refund-transfer fee coverage, account ownership checks, IRA contribution year/limits, refund deposit support and separate investment consent. A Schwab trader API is not established account-opening/refund-transfer permission. No partnership or endorsement is claimed. The Day 7 proposal text is not present here; preserve that fact and request its source rather than invent it.

## Build sequence and approval boundary

First produce an executable plan for authenticated profile/document access, versioned storage and restore. Next implement the connected ledger/draft fixture; then integrate real payment/account providers with measured costs and timings. All are required for the overall goal; a local fixture alone does not finish it. Provider-backed tests and a deployed end-to-end run are required before completion.

This is new architecture beyond the earlier document-entry spec. The user approved this written architecture on October 2, 2026. The connected implementation plan is saved at ../plans/2026-10-02-connected-books.md for the required plan review. No application code or cloud services were modified by this document.
