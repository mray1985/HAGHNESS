# Day 8 provider and completion evidence

Checked October 2, 2026. This report records source findings and current gaps; it is not evidence of deployed integrations.

## Provider decisions

| Purpose | Selected/candidate | Evidence | Remaining prerequisite |
|---|---|---|---|
| Authentication | Cognito required TOTP MFA | https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-mfa-totp.html | Account/pool, tested session validation, cross-profile enforcement |
| Document storage | Private versioned S3, KMS key outside application | https://docs.aws.amazon.com/aws-backup/latest/devguide/s3-backups.html | Bucket/key policies, metadata access checks, encrypted backup and actual restore |
| Profiles/ledger | RDS PostgreSQL | https://docs.aws.amazon.com/AmazonRDS/latest/gettingstartedguide/managing-backup-restore.html | Schema, private networking, encrypted database, transaction tests and restore |
| Bank data | Stripe Financial Connections candidate | https://docs.stripe.com/financial-connections | Provider account and permissioned connection; no payment capability implied |
| Reserve accounts/funds movement | Stripe Treasury v2 candidate, not committed | https://docs.stripe.com/treasury/connect | US is private preview; contact sales for access. Confirm business eligibility and quote before building provider-dependent money movement |
| IRS payments | Explicit user-authorized IRS payment path | https://www.irs.gov/payments/direct-pay-with-bank-account | Direct Pay is a user-facing official service; no public API contract established by this research. A link or recorded receipt is not HA automatic payment integration |
| IRA/refund/investment | Schwab provider review pending | https://developer.schwab.com/ and https://www.schwab.com/ira | Developer portal gave no readable public specifications in this check; no verified account-opening/funding agreement, partnership or investment authorization |

Stripe's older Treasury documentation redirects to a legacy v1 integration and explicitly says not to build a new v1 integration: https://docs.stripe.com/treasury/connect/legacy/v1. Current v2 documentation lists US private preview and sales access. Therefore the next implementation must abstract reserve/payment providers and not silently rely on legacy access.

Financial Connections documents permissioned balance, ownership and transaction data. Ownership data availability depends on the financial institution; any missing ownership response must remain unresolved rather than be presumed verified. Source: https://docs.stripe.com/financial-connections/ownership.

IRS Direct Pay is described as free, secure and supporting individual estimated/balance payments and business payments. Its advertised price does not mean HA bank/refund-transfer providers are free. Different payment types require the appropriate official workflow. Never submit payment twice after a timeout without checking the prior attempt's status.

## Cost evidence and measurement record

Pricing references: https://aws.amazon.com/cognito/pricing/, https://aws.amazon.com/s3/pricing/, https://aws.amazon.com/kms/pricing/, https://aws.amazon.com/backup/pricing/.

The attempted Stripe URL https://stripe.com/financial-connections/pricing returned 404; no price is asserted from it. Treasury pricing/access needs a provider quote. No verified HA monthly total exists. Regional database/compute/network/logging costs must be quoted alongside storage/authentication; pricing only storage would conceal major costs.

Before provisioning, produce a quote with region, instance/container size, hours, storage GB, monthly active users, uploads/downloads, KMS requests/keys, backup retained GB, egress, logs, taxes and fee absorption. Measure fictional-flow timestamps for login/MFA, upload, draft update, correction, restore and provider sandbox confirmation. Report environment and observed p50/p95 when enough samples exist; do not invent timing measurements or promise refund arrival times.

## Goal audit against current state

| Day 8 requirement | Current authoritative evidence | Status |
|---|---|---|
| Identify platform | Local Git repository, Python server, user confirmed no existing hosted MFA | Confirmed |
| Select storage/database/auth | Approved connected architecture names S3/KMS, PostgreSQL and Cognito | Approved; AWS account not configured |
| Client/business/year document permissions | ha/connected access, document service and PostgreSQL constraints | Locally tested; cloud verification pending |
| One MFA session | Signed token validation, Cognito policy checks, opaque cookies and CSRF | Implemented; hosted MFA unverified; single process |
| Cross-profile denial | Domain/API/PostgreSQL tests and restored database check | Local checks pass; deployed check pending |
| Preserve originals/version corrections | Immutable metadata and S3 version/KMS adapter | Locally tested; real storage/scanning pending |
| Backup storage/retention | Proposed AWS Backup + RDS recovery; 35-day/12-month operational schedule | Proposed, not configured |
| Fictional-file restore | Actual local PostgreSQL dump/restore report saved | Database recovery proved locally; encrypted object/cloud recovery pending |
| Card/cash/missing-receipt/correction scenario | Durable ledger tests run against real PostgreSQL | Local checks pass; signed-in browser journey pending |
| Monthly/quarterly/annual draft, payments | Tests produce 1180 book profit, 375 reserve and 100 unverified owner payment | Locally verified; full tax calculations missing |
| Disclosure | Connected page explains incomplete tax calculations and reserve/payment distinction | Displayed; locked preview browser checked |
| Schwab Day 7 proposal | Earlier idea appears in document-entry spec; actual Day 7 proposal artifact absent | Source needed; no partnership confirmed |
| Banking/payments support | Official provider docs distinguish permissions, preview access and IRS payments | Research advanced; live integration missing |
| Costs and completion times | References and measurement protocol, no complete quote or measured integration | Incomplete |

## Next permissible steps

The user approved the connected architecture and implementation plan and requested continuous work. Local implementation proceeds under that approval. The user confirmed no AWS account is configured; provider-backed deployment remains unavailable. Tests and the locked preview do not constitute hosted authentication or production readiness.

Deployment subsequently needs a user-controlled cloud account/role, priced resource plan, and configuration through a secure mechanism. Do not request credentials in chat. The complete goal stays active until permissions, restore and the connected flow pass provider-backed verification.
