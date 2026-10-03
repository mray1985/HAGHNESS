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

The [current DigitalOcean cost scenario](DIGITALOCEAN-COST-PLAN.md) prices application/scanner, identity, a single-node database, Spaces and optional daily VM backups at a $129.05 component subtotal. A complete quote still needs retained backups, key recovery, overages, monitoring, operations and support. Treasury and Schwab integration charges require written provider terms. No complete monthly total has been verified.

The latest saved actual local recovery run took 8.777 seconds, restoring seven snapshot tables, six ledger events, four document versions, two saved tax-input references and support-review history, with scope and wrong-key denials. Private backup locator copy/readback also passed through the fictional local store. This single sample is not p50/p95, hosted recovery time or user completion time.

For future measurements, record environment, trial ID, start/end UTC, elapsed seconds, success/error, provider confirmation and charges for each phase: login/MFA, original upload, correction, draft calculation, restore, bank linking, payment confirmation and IRA funding. Report task time separately from settlement time and failures separately from successful observations. Provider phases remain unmeasured.

## Current completion audit

| Requirement | Evidence/status |
|---|---|
| Platform identified | Local Python application and PostgreSQL; no preexisting hosted MFA |
| Per-profile permissions | Local domain/API/PostgreSQL cross-profile denials pass |
| One protected MFA session | Actual local Keycloak password/OTP through HA HTTPS callback verified across books, tax, documents and support reviews; hosted enrollment/recovery and combined rendered browser journey pending |
| Preserve originals and corrections | API/UI and immutable metadata implemented; permission regression fixed |
| Recovery | Actual isolated database and encrypted local object restore passed; hosted recovery pending |
| Retention/backups | Encrypted snapshot capture, private copy/readback, off-host locator, downloaded actual database restore and nondestructive retention planner verified locally with fictional storage; hosted schedule/permissions/expiry controls pending |
| Fictional business flow | Ledger fixtures verified locally; combined local HTTPS API workflow now verified; hosted browser journey pending |
| Tax drafts/payments | Book/reserve projections exist; comprehensive tax engine and confirmed money movement incomplete |
| Growth proposal | Day 7 says none was written; new unsent discussion draft now saved |
| Costs/times | Published bank-data rates and one local recovery measurement; five local API workflow timings saved; full quote/provider timings pending |

Current regression checkpoint: 209 tests, 207 passed with real PostgreSQL, two Linux-only tests skipped. Later dated entries below record the intervening changes; older entries describe their checkpoint rather than current limitations. The full build remains incomplete; local evidence must not be presented as hosted security, filing readiness or a confirmed partnership.


## Real MFA saved-tax-input checkpoint

October 2: the completed local Keycloak password/OTP to HA HTTPS callback probe now saves and reopens tax inputs under the same actual opaque session used for books, tax estimates, documents and support review. Actual PostgreSQL 16, ClamD and AES-GCM local objects participate. Original and correction inputs and server metadata reopen exactly, including leading-zero amounts, blanks and multiple states. Retry preserves the original response; stale edits, missing CSRF, missing edit authority, foreign scope, revoked grants and access after logout are rejected. Revoking edit permission still permits explicitly authorized reading.

Recalculating the reopened correction produces wages of $200 and book profit of $1,180. Refund and balance remain held, and preparation authority remains false. The saved KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json records each check. The final probe exited successfully, and no owned Java, PostgreSQL or ClamD fixture services remained running afterward. Two Linux cleanup tests also passed.

This is actual local MFA/API evidence with fictional taxpayer data. The separate rendered-browser checks use fictional API responses; a combined rendered browser with real MFA remains pending. Hosted DigitalOcean/Spaces, real-user enrollment and recovery, external key recovery, retention execution and filing remain unverified. Runtime uploads remain unactivated.


## Rendered browser with actual MFA session

October 2: optional HA_MFA_BROWSER_NODE extension passed in actual headless Edge against the live local fixture, with no mocked API routes. The opaque cookie from the verified password/OTP callback is passed in memory through subprocess stdin, never written as browser state or logged. The protected /tax screen reopens the saved correction, saves a new fictional correction, reloads and reopens it again. Three saved versions are listed. Browser storage is empty, no page errors occur and the 390-pixel mobile viewport has no horizontal overflow. The final composed probe exited successfully; no owned fixture services remained running.

This verifies rendered tax save/reload/reopen with actual PostgreSQL, ClamD and encrypted local objects under an actual MFA-created session. It reuses that session rather than entering password/OTP in the browser. The browser accepts the disposable self-signed fixture certificate; browser certificate trust is not proven. Separate protocol checks still verify hostname and certificate trust. Hosted DigitalOcean/Spaces, real-user enrollment/recovery, external key recovery, retention execution and filing remain pending.

The extension requires the Windows Node executable via HA_MFA_BROWSER_NODE and the installed Playwright/Edge runtime. HA_PLAYWRIGHT_MODULE can override the module location. It is an optional local verifier, never a production authentication bypass. Authentication reuse follows the Playwright BrowserContext cookie API: https://playwright.dev/docs/api/class-browsercontext.


## Connected rendered journey checkpoint

October 2: the actual-session Edge verifier now opens HA Bookin, checks recorded income $1,500, corrected expenses $320 and book profit $1,180, then verifies October monthly, quarterly and annual API and rendered totals without double counting. It checks owner payments recorded $100 versus government-confirmed $0 and the reopened advertising support question. Downloading the corrected receipt through the screen returns exact fictional bytes. Opening an unauthorized profile clears prior totals/documents; returning to the permitted scope and following Open HATax preserves the case. Tax correction/save/reload/reopen still passes. No API routes are mocked.

The final probe passed; no owned Keycloak, PostgreSQL or ClamD processes remained afterward. The browser portion measured 3.7 seconds for one automated local fictional run, excluding MFA/runtime startup. This is not a customer completion-time claim. Browser certificate trust, hosted DigitalOcean/Spaces, real-user enrollment/recovery, external key recovery, retention execution and filing remain unverified. Detailed evidence is KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json.


October 2 backup monitor: read-only known private off-host locator CLI distinguishes current/stale/unavailable with sanitized JSON and explicit no integrity/recovery/deletion authority. 21 targeted tests and actual isolated PostgreSQL/encrypted restore probe passed; provider transfer remains fictional. Independent review no important defects. Details: BACKUP-MONITORING.md. Hosted scheduling/catalog/alerts/retention and external key recovery remain open.


October 2 backup attempt journal: runner emits bounded structured started/completed/failed records with matching attempt ID and UTC times. Completion gates verified copy and off-host locator; failure hides exception details. Service template explicitly journals output. 23 targeted tests plus actual disabled failure invocation passed; independent review no important defects. Output format changed to JSON. Hosted scheduler/journal retention/external alerts remain unconfigured. See BACKUP-MONITORING.md.


October 2 backup attempt assessment: bounded ordered JSONL journal reader assesses latest observed start, newer failure/unfinished overrides old success including overlapping old finish. Exactschema/duplicatefields/order/future/transition checks fail closed. 28 targetedtests and actual disabledrunner-to-reader pipeline passed; independentreview no important gaps. Read-only supplied-window evidence only; separate locator check needed. Hosted journal retention/scheduler/external alerts remain open. See BACKUP-MONITORING.md.


## Actual rendered password and OTP login

October 2: the latest composed Edge probe now performs password and OTP entry on the real local Keycloak screens and receives its own HA session through the HTTPS callback. It no longer injects the protocol fixture's opaque cookie. Disposable credentials travel through subprocess stdin only; credential form destinations are checked before filling. Secure/HttpOnly/SameSite/Path session cookie properties pass. The same browser session then passes Bookin totals and period views, corrected receipt download, denied-profile clearing, HATax handoff and saved correction/reload/reopen. Clicking Sign out denies subsequent protected tax access. No API routes are mocked.

The browser journey measured 6.3 seconds in one automated fictional run, including browser password/OTP but excluding runtime startup and the fixture's unused-TOTP-period wait. Actual PostgreSQL16, ClamD and AES-GCM local objects participate. The successful probe left no owned services running. Four targeted fixture parser/OTP tests passed on Windows, with two Linux cleanup tests skipped there. Independent review found no important defects in credential/session handling.

Windows could not reach the local Java IPv6-mapped loopback listener during initial rendered-login attempts. The local fixture now uses -Djava.net.preferIPv4Stack=true; socket inspection confirmed 127.0.0.1:8843, and the full rendered journey passed. This follows Oracle's networking property documentation: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/net/doc-files/net-properties.html. This fixture-specific choice does not alter hosted configuration. Failure diagnostics contain fixed step/error-type or network-code labels only.

Browser trust of the disposable self-signed certificate remains bypassed explicitly for this fixture, while separate protocol checks verify hostname/certificate trust. Real-user OTP enrollment/recovery, hosted DigitalOcean/Spaces, external key recovery, operational retention/alerts and filing remain unverified. The latest KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json supersedes earlier cookie-reuse-only checkpoints.


October 2 provider prerequisite: fixed-endpoint read-only DigitalOcean account checker added with account:read scope, no redirects, bounded response, no identity/secret output or resource creation. Five tests pass. Actual local invocation reports token_not_configured; no provider account verified. See DIGITALOCEAN-IMPLEMENTATION.md.


October 2 actual Linux key rotation/recovery: runtime MountedKeys+SpacesObjects fictional versioned storage preserve original/corrected document and encoded W2 bytes across activekeychange/separate local recoverycopy. Missing historicalkey deniesold/newstillreads;0644/symlinkreject. Actualprobe and16targetedtests pass, independentreviewnoimportantdefects. No hostedSpaces/externalcustody/DB/MFA claim. Details KEY-RECOVERY.md and KEY-ROTATION-EVIDENCE.json.


## Permitted record chooser

October 2: signed-in HA Bookin users can choose their current read-permitted profile/business/year from a server-provided list. Manual ID entry is in an Advanced disclosure. GET /api/connected/cases requires the existing MFA session, filters fresh grants to read scopes, validates business ownership, deduplicates and sorts. Revocation removes scopes from the next list; every later data action still checks its own permissions. The list returns IDs and year only, not tax facts or names. Picker requests guard stale responses and expose a refresh action.

Fifteen API/access tests passed, including unsigned/logout denial, duplicate grants, another subject's grant, upload-only authority, mismatched profile/business and revocation. The actual Keycloak password/OTP, PostgreSQL and ClamD composed browser probe passed choosing the permitted case and the full existing connected journey. Its automated browser portion measured 7 seconds locally, not customer completion time. Owned services stopped afterward.

The completed run logged a server-side TLS disconnect while a browser navigation cancelled an in-flight response; functional checks passed, but disconnect-log handling remains a follow-up. Query cost currently includes one ownership lookup per distinct granted business; larger firm inventories need a joined/paginated repository query. Labels currently use IDs because a client display-name directory is not implemented. Hosted provider setup and recovery remain unverified. Evidence: KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json.
