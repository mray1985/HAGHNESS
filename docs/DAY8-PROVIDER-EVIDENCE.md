# Day 8 provider and completion evidence

Checked October 2, 2026. This supersedes the earlier AWS-first plan. Research and local tests do not prove deployed integrations.

## Current decisions

| Purpose | Direction | Remaining prerequisite |
|---|---|---|
| Application and database | DigitalOcean deployment configuration; PostgreSQL | User-controlled account/resources, reviewed quote, private connectivity and deployed verification |
| Authentication | Independent Keycloak PKCE with signed MFA claims | Deployed realm, tested password/OTP policy and browser session; sessions currently single-process |
| Private documents | Private versioned Spaces target; client AES-GCM adapter and local recovery fixture | Select/configure hosted private storage, external key management, scanner and operational access policies |
| Bank data | Stripe Financial Connections candidate | Provider account, permissions, ownership availability and sandbox verification |
| Reserve accounts/payment movement | Stripe Treasury candidate | US private-preview access, eligibility, agreement and quoted charges |
| Federal tax payment | Client-controlled IRS Direct Pay | Correct tax type/year, authorization and confirmation; no HA automatic payment API established |
| Retirement referral/funding | Schwab exploratory draft | Correct business contact, agreement, contribution-year process and provider-approved technical access |

Implementation details: [DigitalOcean plan](DIGITALOCEAN-IMPLEMENTATION.md), [Keycloak requirements](KEYCLOAK-IMPLEMENTATION.md), [recovery evidence](DATABASE-RESTORE-EVIDENCE.json), [Schwab draft](SCHWAB-PROPOSAL-DRAFT.md).

## Banking and payment research

[Financial Connections](https://docs.stripe.com/financial-connections) provides permissioned financial data. A bank connection is not payment authorization. Missing institution ownership data cannot be treated as ownership confirmation.

[Stripe Treasury documentation](https://docs.stripe.com/treasury/connect) lists the US as private preview and requires contacting sales for access. Do not commit the build to capabilities HA has not been granted.

[IRS Direct Pay](https://www.irs.gov/payments/direct-pay-with-bank-account) is a free official payment service. That does not make HA processing, refund transfers or bank-provider services free. Payment retries must check prior status before risking duplicate submission.

[Schwab IRA information](https://www.schwab.com/ira) advertises zero opening and maintenance fees; other charges and conditions can apply. No HA integration agreement is established. [IRS refund-to-IRA guidance](https://www.irs.gov/faqs/irs-procedures/refund-inquiries/refund-inquiries-12) requires contribution-year notification to the custodian, timely receipt and owner verification. A refund estimate is not a completed IRA contribution.

## Costs and measured times

[Stripe's US Financial Connections pricing](https://stripe.com/financial-connections#pricing), checked October 2:

| Item | Published unit price |
|---|---|
| Instant verification | $1.50 per verified account |
| Balance retrieval | $0.10 per successful API call |
| Ownership retrieval | $1.50 per successful API call |
| Transaction subscription | $0.30 per institution per account holder per month |

Illustrative bank-data-only budget: 100 newly verified accounts, 100 ownership calls, 400 balance calls and 100 institution/account-holder subscriptions cost $370 for that month at these rates. This arithmetic scenario is not a provider quote or a full HA operating budget. Payment, hosting, identity, storage, backups, support and taxes are separate. Custom pricing may differ.

DigitalOcean quote still needs region, application/identity compute, database capacity, storage, retained backups, key management, egress, monitoring and support. Treasury and Schwab integration charges require written provider terms. No complete monthly total has been verified.

Actual local recovery took 2.02 seconds in the saved fictional PostgreSQL/encrypted-file run, recovering six ledger events and two document versions with scope and wrong-key denials. This single sample is not p50/p95, hosted recovery time or user completion time.

For future measurements, record environment, trial ID, start/end UTC, elapsed seconds, success/error, provider confirmation and charges for each phase: login/MFA, original upload, correction, draft calculation, restore, bank linking, payment confirmation and IRA funding. Report task time separately from settlement time and failures separately from successful observations. Provider phases remain unmeasured.

## Current completion audit

| Requirement | Evidence/status |
|---|---|
| Platform identified | Local Python application and PostgreSQL; no preexisting hosted MFA |
| Per-profile permissions | Local domain/API/PostgreSQL cross-profile denials pass |
| One protected MFA session | Keycloak verifier/PKCE implemented; live realm and signed-in browser unverified |
| Preserve originals and corrections | API/UI and immutable metadata implemented; permission regression fixed |
| Recovery | Actual isolated database and encrypted local object restore passed; hosted recovery pending |
| Retention/backups | 35-day/12-month planner and hold protection implemented; hosted schedule and expiry controls not configured |
| Fictional business flow | Ledger fixtures verified locally; combined local HTTPS API workflow now verified; hosted browser journey pending |
| Tax drafts/payments | Book/reserve projections exist; comprehensive tax engine and confirmed money movement incomplete |
| Growth proposal | Day 7 says none was written; new unsent discussion draft now saved |
| Costs/times | Published bank-data rates and one local recovery measurement; five local API workflow timings saved; full quote/provider timings pending |

Latest code verification before this documentation update: 126 tests passed with real PostgreSQL. No application code changed in this update. The full build remains incomplete; local evidence must not be presented as hosted security, filing readiness or a confirmed partnership.
