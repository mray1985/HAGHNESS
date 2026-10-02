# Plan: docs/superpowers/plans/2026-10-02-connected-books.md

User approved architecture and plan and requested continuous implementation on October 2, 2026.

Read all eight daily PDFs and the weekly report. Day 5 explicitly replaced browser-only live-client design. Day 7 confirms no completed/sent Schwab proposal. Daily records are evidence of design/history, not deployed controls.

Ruling: use feature branch codex/connected-books in the existing checkout rather than a new worktree — keeps user-supplied daily records and uncommitted approved plans available — cost if wrong: branch isolation does not isolate runtime files.

Task 1: access domain implemented; five tests observed failing before code, then passing. Database scope constraints remain part of Task 2.

Task 2: cryptographic RS256 issuer/audience/expiry/nonce validation and opaque expiring sessions implemented; four tests observed failing before code, then passing. Cognito OAuth exchange/pool policy and actual hosted MFA remain unfinished. Isolated .venv dependencies installed and pinned.

Task 3: immutable document service and KMS/version-enforcing S3 adapter implemented. Four document and three adapter tests passed after observed missing-module failures. Storage/permission doubles are explicitly synthetic; no cloud verification claimed. Scan callback fails closed unless explicitly clean; production scanning adapter remains unfinished.

Task 4: synthetic byte/hash recovery reconciliation implemented and tested. AWS Backup restore is not yet run.

Task 5: append-only balanced correction postings and source-linked book draft implemented; five fixture/edge tests passed after observed missing-module failure. Volatile event store is explicitly test-only; durable PostgreSQL integration remains unfinished.

Verification so far: 66 Python tests pass in .venv (45 legacy + 21 new). Read all eight daily records and weekly report. No real taxpayer data used.

Ruling: perform independent pure-domain work while provider setup is unavailable — avoids blocking ledger work on hosted MFA — cost if wrong: provider integration may require adapting repository interfaces.

Whole-goal status: incomplete. No cloud resources provisioned; provider-backed MFA, encrypted storage restore, payments and end-to-end deployment still require verification.

October 2 continuation: user confirmed no AWS account configured. Implemented Cognito PKCE/browser-bound OAuth exchange and verified provider-policy checks against synthetic responses. Added real PostgreSQL persistence, foreign-key scope constraints, serialized retries/corrections and document metadata persistence. A real database timezone mismatch was reproduced and fixed by UTC normalization. Actual local pg_dump/restore recovered the fictional draft and preserved cross-profile denial; cloud/object restores remain unrun.

Verification reached 81 passing tests with PostgreSQL enabled before runtime configuration tests were added. Added a separate connected service entry point and locked preview. Edge/Playwright browser verification: no page errors, workspace hidden when unconfigured, and no horizontal overflow at 390px. This check does not prove hosted authentication or the signed-in journey. Fixed pending entry/upload retry state when switching business scope.

Runtime instructions and explicit remaining release gates are in docs/CONNECTED-RUNBOOK.md. Document uploads intentionally remain unavailable in the runtime pending actual scanning integration.

Fresh review found stale client-response rendering and timestamp-dependent document correction ordering. Fixed request-generation guards and immediate display clearing; correction now follows the unique chain head. Browser regression proved delayed client A cannot overwrite denied client B using fictional intercepted responses. Document regression covers reversed repository ordering. 84 tests passed with real PostgreSQL. Repeated actual local database restore passed in 1.367 seconds after fixing nondeterministic comparison order.

User redirected provider selection: AWS is optional, inspect current setup and compare non-AWS providers before choosing. Saved docs/NON-AWS-STACK-COMPARISON.md. Recommendation is DigitalOcean App Platform plus Supabase Pro; no migration or provider purchase authorized by this recommendation. Current local code remains reusable; Cognito/S3 adapters are unconfigured candidates, not existing infrastructure.

User subsequently selected the independent DigitalOcean direction and authorized GitHub push. Added deploy/digitalocean locked-preview container/app specification and docs/DIGITALOCEAN-IMPLEMENTATION.md. Supabase is excluded from that target. Default runtime authentication is explicitly disabled; Cognito requires explicit selection. Actual account provisioning, replacement MFA/storage integration and hosted recovery remain unfinished. Container build unverified because Docker is unavailable locally.

October 2 integration increment: connected service now serves the HATax preview at
/tax and its explicit asset allowlist. HA Bookin links to it, and HATax links back
on the connected deployment. Stateless scenario math is available without login;
protected records still require an authenticated session. No identity fields are
sent by the tax client and no tax draft is saved. Public arithmetic has a 256 KiB
request limit. Auth/storage integration and actual DigitalOcean deployment remain
unverified. API regressions cover routing, computation and locked record access.

Integration verification: 113 tests passed with real PostgreSQL. Browser verified
HA Bookin -> HATax -> W-2 layout -> live $1,928.50 limited refund scenario from
$45,000 wages and $5,200 withholding. No browser errors captured. Independent
review found no material defect. Screenshot uses fictional identity only.

October 2 recovery continuation: implemented a local-only encrypted immutable
file adapter using AES-256-GCM with a caller-supplied separate key. Followed
cryptography's official AEAD documentation (https://cryptography.io/en/latest/hazmat/primitives/aead/).
Tests verify ciphertext persistence, overwrite rejection, wrong-key/tamper/object-swap
rejection and path/version validation. Hosted runtime does not select this adapter.

Actual recovery harness now creates an isolated source database rather than
resetting the existing test database. pg_dump/restore plus encrypted object copies
recovered both original and corrected fictional receipt bytes, correction links,
118000 minor-unit book profit and cross-profile denials. Wrong keys were rejected.
Fresh measured recovery time: 2.020 seconds locally. Key files remain outside
source control and outside the object backup. ACL management, hosted key recovery,
rotation, scanning, backup retention enforcement and cloud recovery remain release
gates. Updated evidence is in docs/DATABASE-RESTORE-EVIDENCE.json.

October 2 independent authentication continuation: added Keycloak authorization
code/PKCE login and a distinct signed-ID-token verifier. Requires exact issuer,
audience/authorized client, nonce, ID-token type, recent auth_time, ACR2 and
execution-derived password+OTP AMR. Browser-bound one-time handshakes reject
wrong-browser and replay callbacks. Namespaced permission subjects prevent
identity collisions across providers. Explicit runtime configuration rejects
partial/mixed providers and retains disabled preview as default.

Verification: 123 tests passed with real PostgreSQL, including six new Keycloak
/configuration tests. Independent review found no important defect. References
and required realm controls are in docs/KEYCLOAK-IMPLEMENTATION.md. This is
synthetic signed-token evidence, not deployed provider-policy or live MFA proof.
The Day 8 objective remains incomplete: actual hosted identity/storage, retention,
provider recovery, payment agreements/timings and the full connected journey are
not yet verified.

October 2 correction continuation: connected API now exposes corrected document
versions through `/api/connected/document/corrections`, with session/CSRF and
per-scope correction permission before document processing. UI allows selecting
original versus correction, entering original ID and change reason. File reads
snapshot the scope and discard stale edits/scope switches before upload.

Independent review found that falsy document IDs could create originals using
correction permission. Fixed in Documents.correct; empty/null/false/list/whitespace
IDs now fail validation. Regression observed RED then GREEN with correction-only
grants. Tests also verify original/corrected byte reads, links, idempotent retries,
revoked correction permission, cross-profile denial and disabled-storage refusal.

Protected browser interaction is not verified yet because hosted identity and
storage/scanning remain unconfigured. JavaScript syntax passed; no runtime storage
is activated by this increment. Full Day 8 goal remains incomplete.

October 2 growth continuation: recovered Day 7 agenda confirms no earlier Schwab proposal existed. Saved a new unsent discussion draft, documented refund contribution-year confirmation, refreshed non-AWS provider status and published bank-data pricing. Provider access, full costs and completion times remain unverified. Documentation-only change; no new application test claim.

October 2 retention continuation: implemented a non-destructive 35-day/12-calendar-month UTC backup planner and operator CLI. Protects latest snapshot and explicit holds; invalid inventories fail closed. Four focused tests pass; full prior regression run passed 129 tests before the fourth case. Independent review found no important defect. Hosted schedule, complete snapshot inventory, lifecycle enforcement and recovery-key operations remain unconfigured. See BACKUP-RETENTION.md.

October 2 Spaces continuation: official compatibility/versioning research informed a client-encrypted private Spaces adapter. Exact provider-version reads, bucket/object/key-ID binding, key rotation and bounded stream closure are tested. Six focused cases pass; independent review found no important defect. No hosted deployment or runtime upload activation is claimed.
Verification for Spaces continuation: full suite passed 136 tests with real isolated PostgreSQL; git diff whitespace check passed.

October 2 scanning continuation: implemented fail-closed ClamD INSTREAM over local Unix socket and explicit Spaces/mounted-key runtime configuration. Partial configuration rejects startup, default remains locked. Scanner rejection publishes neither objects nor metadata. Shared session/CSRF/scope APIs now receive the configured Documents service. Independent review found no important defect. Live daemon policy/signatures, Linux permissions, hosted bucket and recovery verification remain open.
Scanning continuation verification: 148 tests passed against real isolated PostgreSQL; whitespace check passed.

October 2 combined workflow continuation: five verified-local-HTTPS trials used actual PostgreSQL and encrypted local objects in a new isolated database. Same session served ledger and original/corrected documents. Card/cash income, correction, missing receipt, retry, month/quarter/year totals, unconfirmed owner payment, CSRF, existing unrelated-profile and logout denials passed. Observed API-only median 2.4927s, nearest-rank p95 3.2507s, n=5. Local signed identity and synthetic scanner bypass are explicitly disclosed; hosted identity/storage/payment/tax readiness is not claimed. Independent review found no important defect.
Combined workflow verification: 150 regression tests passed with real isolated PostgreSQL; integration runner passed five trials; whitespace check passed.

October 2 support-review continuation: projection now distinguishes missing receipts, missing cash explanations and recorded information awaiting review. User-supplied reviewed=true cannot clear the queue; corrections preserve prior payment method/explanation. New evidence/explanation values must be bounded text. Independent review found legacy nontext records could crash projection; reproduced and fixed with a regression test so legacy values remain visible and require review. Connected UI shows the queue. Combined HTTPS workflow passed five trials with four operating entries awaiting review; no authorized support-review completion workflow is claimed.
Support-review verification: 153 tests passed with isolated PostgreSQL; JavaScript syntax and whitespace checks passed. Hosted UI/provider verification remains open.

October 2 return handoff continuation: Bookin carries profile/business/year to HATax. Protected estimate endpoint reads current annual books through existing session/CSRF permissions, requires year match and suppresses combined balances when business treatment is unfinished. No public-estimate fallback occurs after protected access failure. UI shows book profit/revision and actual review source name. Independent review caught hardcoded 1099-R/null labeling; fixed. Five combined real-PostgreSQL/local-HTTPS trials passed with handoff; 156 regression tests passed. JavaScript/UTF-8 and whitespace checks passed. Hosted browser and full tax treatment remain unverified.


October 2 Linux deployment continuation: native systemd service, explicit Keycloak/Spaces environment example, HTTPS nginx and protected ClamD settings saved under deploy/digitalocean/droplet. App binds loopback, key directory is outside source and read-only, scanner uses group-restricted Unix socket. Independent review found inherited nginx error-log URI exposure; template now discards those logs and requires sanitized monitoring verification. Eleven existing scanner/configuration tests passed. Local Ubuntu unit validation reports missing target services/executable; nginx/ClamAV validators unavailable. No hosted activation or filing readiness established.


October 2 encrypted database backup continuation: streaming authenticated archives now protect pg_dump contents with a separately stored recovery key. Actual isolated restore recovered six events and two document versions with cross-profile denials. Review-driven atomic publication prevents a partial archive appearing at its final path. Final full suite passed 160 tests with real PostgreSQL; final archive tests and actual restore rerun passed. Independent follow-up review confirmed the publication fix. A Windows socket-abort error on the first full run did not recur. Hosted schedules and retention remain open. See ENCRYPTED-DATABASE-BACKUPS.md.


October 2 actual Linux scanner verification: installed local ClamAV and official signatures, verified clean/EICAR/encrypted-PDF/unavailable-socket behavior through the real adapter. Expanded ZIP limit probes returned clean unexpectedly; saved evidence marks the overall policy gate failed. Runtime uploads remain unactivated. Four encrypted-backup tests also passed on actual Linux. See DOCUMENT-SCANNING.md and LIVE-SCANNER-EVIDENCE.json.


October 2 scanner policy continuation: researched official ClamAV container metadata signatures, added an explicit >25 MiB member policy, and verified nine real Linux probes including boundary/nested rejection. Baseline failure remains saved. Full 64-bit policy range accepted by the actual engine; forged metadata/ZIP64 and hosted verification still open. Independent review found no remaining important defect in this change.


October 2 live document-service continuation: fourteen actual Linux checks now include Documents with real ClamD and encrypted objects, clean original/correction preservation, no publication on rejected upload/correction, and authorization before foreign stream access. Saved report explicitly identifies volatile metadata/permissions and synthetic MFA principal; live provider login/storage/database integration remains open.
