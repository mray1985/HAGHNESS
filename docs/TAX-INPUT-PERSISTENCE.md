# Protected HATax input persistence

Status: input codec, database reference foundation and saving/opening service implemented and tested; HTTP routes and rendered user controls implemented; actual composed MFA/database/browser and hosted proof remain open; local restored saved-input proof now passes. HATax still loses entries on refresh. This is the next core workflow feature, not completed saving.

## Current evidence

`web/return.js` keeps profile, multiple W-2/1099-R forms, active document and state answers in the `draft` page object. Browser storage is unused. Connected estimates already use the Bookin MFA session, scope and CSRF. Private documents are encrypted through configured object adapters, with immutable original/correction metadata in PostgreSQL. Existing backup bundles capture document rows and ciphertext. The tax engine remains a limited preview and holds combined business refunds/balances when treatment is unresolved.

## Saved input contract

`ha/connected/tax_snapshot.py` serializes the versioned `ha-tax-input-v1` envelope. Its input contains year, profile, forms, active document index and state answers. It preserves raw strings, blanks, leading zeros and incomplete entries; it does not treat saving as tax validation. It rejects unexpected fields, computed estimates, unsupported form/layout names, duplicate JSON fields, mismatched scoped year and excessive rows/text/bytes. Maximum serialized input is 256 KiB; maximum forms/states is 100 and W-2 code rows four. These are explicit preview limits, not claims about legal form limits or comprehensive support.

Calculated estimate, profileReady, navigation step and transient request revision are omitted. Reopening must recalculate the estimate from current rules and current books, derive profile validity from the actual form, and supply safe rendering defaults for absent optional states/codes/checks. Stored values must always be escaped when rendered. The codec itself does not store anything and its output is sensitive plaintext until passed into the encrypted object adapter. Do not put it in logs, localStorage, filenames or ledger JSON.

## Implementation gates

1. Add a distinct `save_tax` permission, without automatic grants. Read access must be checked fresh for listing/opening; save access must be checked inside the write transaction. A business-book permission must not silently create tax editing authority.
2. Add a scoped input-version reference table pointing at the encrypted document version, with server actor/time and an append-only history. Expose only bounded references, never profile/form plaintext, in PostgreSQL metadata. Include this table in migration and actual backup/restore comparisons.
3. Serialize encrypted document creation and input-reference publication in the same scoped database transaction. Use existing encryption/scanning fail-closed behavior. Preserve originals and corrections; object failures or metadata failures cannot report save success. An uploaded orphan must never become an active draft by itself.
4. Require expected current version and a request idempotency key. Concurrent edits from two tabs must reject stale writes rather than silently overwrite. Identical retries return the original result; conflicting reuse rejects. First save must expect no previous version. Corrections need a bounded reason. Test actual PostgreSQL locking and rollback behavior.
5. Add protected scoped list/open/save routes using existing MFA cookie, Origin/CSRF and no-store responses. Bound input before reading/parsing. Foreign-profile, revoked-grant, unsigned, bad-CSRF, wrong-year, corrupt-object and missing-key cases must deny without public fallback.
6. Add explicit Save/Reopen controls only on protected HATax routes. Show saved version/time and unsaved changes; keep page inputs after failed saves. Bind save responses to input revision/scope so an earlier response cannot mark newer edits saved. On reopen, ask before replacing unsaved page entries and recompute estimates. Standalone preview remains fictional and memory-only.
7. Verify refresh/reopen and another authorized session through actual MFA/PostgreSQL/encrypted objects; prove unrelated profile denial and immutable correction history. Run rendered desktop/mobile UI checks, then an actual downloaded backup restore containing a saved input and compare reopened inputs. Report hosted status separately.

One return may eventually include several businesses or Form 1041. The current connected scope is profile/business/year; label this feature as a business-linked draft until a return-level authorization model exists. Do not silently duplicate household inputs across businesses or sum saved drafts. No filing, payment or final-review authorization is implied by saving.


## Database foundation checkpoint

Migration 003 adds explicit `save_tax` vocabulary without granting it, plus append-only `tax_input_versions` metadata. Exact scoped document-version foreign keys prevent links across profile/business/year. A scoped predecessor foreign key also requires the same document chain. One original per case/year and one successor per snapshot prevent duplicate roots/forks. A BEFORE INSERT guard requires an existing lower-sequence predecessor; a reproduced multirow disconnected-cycle insertion is now rejected. Server-generated actor/time/version and optimistic expected-version enforcement remain service work; SQL constraints alone do not authorize saves or verify document bytes.

Actual PostgreSQL tests cover scope/year denial, explicit permission preservation through repeated migration, update/delete rejection, corrections, exact root/fork constraints, blank correction reason and cyclic multirow inserts. Latest full suite: 214 total, 212 passed, two Linux-only skipped. Independent review identified the cycle gap; it was reproduced, fixed and reviewed again with no remaining important findings. The actual encrypted backup/download/pg_restore harness now compares all seven tables, including a deliberately labeled metadata fixture referencing receipt bytes. That fixture proves reference-row recovery; it does not prove a saved tax input can be reopened.


## Transactional service checkpoint

`TaxInputs` uses the same PostgreSQL repository as Documents. Save checks current read/save_tax authority inside the shared transaction, takes the existing scope lock, validates the explicit request and scoped input, compares expected snapshot and enforces scoped idempotency. Canonical sorted-key snapshot bytes make equivalent JSON object order retry consistently. Initial writes and corrections pass through existing Documents upload/correct permissions, scan gates and configured encryption. Prior bytes are authenticated before correction; a separately changed document head prevents extending stale input references. Server actor/time and exact document-version references are appended in the same database transaction.

Open/history check current read permission; open authenticates document bytes and validates the saved format/year. Current and earlier snapshots are available. This is saving entered facts, not computing or approving tax results. An unauthorized editor receives no publication. A failed scanner/storage/metadata operation leaves active input/document metadata unchanged; a metadata failure after object publication may retain an encrypted unreferenced object for operator cleanup, never an active saved draft. No automatic deletion is added.

Actual isolated PostgreSQL tests cover permissions, restart of the service instance, originals/corrections, identical/conflicting retries, stale edits, forged fields, cross-profile denial, revoked editing and corrupt bytes. A separate actual AES-GCM local fixture verifies ciphertext, scanner/storage/metadata failure preservation and competing-save behavior. Tests use a synthetic scanner, not actual ClamD, and domain principals, not live MFA browser login. Final suite: 217 total, 215 passed, two Linux-only skipped. Independent code review found no important defect. HTTP routes, rendered save/reopen, actual MFA integration and restored saved-input reopening remain open. HATax still loses screen inputs on refresh until those controls are connected.


## Protected HTTP checkpoint

GET `/api/connected/tax/inputs?profile=...&business=...&year=...` returns scoped history references and a can_save hint. The hint checks read, save_tax and the necessary existing upload/correct permission; POST always rechecks actual authority. POST to the same path accepts `{scope, save}` using the service's explicit input/expected_snapshot_id/reason/idempotency_key contract. Requests above 512 KiB reject before reading the body; serialized input itself remains limited to 256 KiB. GET `/api/connected/tax/input` opens current input, or an exact `snapshot` query reference, with authenticated document read and saved-format/year validation. Responses inherit no-store behavior.

Routes use existing MFA-derived session and Origin/CSRF verification, with no public saving fallback. Unconfigured service returns unavailable; unrelated/missing references do not disclose input. Automatic service wiring requires a shared PostgreSQL repository and configured Documents. Operators must apply migration 003 and explicitly provision editing plus document-write grants; routes do not grant access.

Actual local HTTP plus PostgreSQL tests pass unsigned, missing-CSRF, absent edit permission, explicit grant, identical retry, history/current reopen, unknown snapshot, foreign profile, wrong year, invalid/oversized input, revoked permission and logout boundaries. The HTTP fixture uses an injected synthetic MFA session and volatile unencrypted object test double, not a live provider identity/storage journey. Encryption/concurrency were tested separately in the service fixture. Final regression: 219 total, 217 passed, two Linux-only skipped. Independent review found no important issues. Rendered Save/Reopen controls, actual MFA composition, hosted proof and recovery of saved input remain unfinished; current screen still clears on refresh.


## Rendered controls checkpoint

Business-linked HATax now exposes explicit Save/Reopen, saved-version selection, correction reason and saved/unsaved status. Existing work must be reopened before editing. Replacing unsaved entries requires a modal confirmation; cancel preserves them. Reopen supplies optional form defaults, derives actual profile-form validity and recalculates the estimate. Connected year is fixed to the case. Public preview has no saving controls or browser storage.

Input signatures protect async behavior: saving older input never labels newer edits saved; edits during an in-flight reopen prevent replacement. Failed saves keep screen input. Equivalent retries reuse an in-memory idempotency key until input/expected-version/reason changes; successful save/reopen clears it. No client plaintext is persisted to localStorage/sessionStorage. Leaving with unsaved work uses the browser's navigation warning.

Actual Edge headless Playwright on loopback rendered HTML/JS/CSS with explicitly fictional API responses. Browser plugin not available, so the frontend-testing skill's regular Playwright fallback was used. Checks passed save, page reload/reopen, cancel/confirm replacement, edits during save/open, denied-save preservation and retry-key reuse, W-2 multiple states and optional code defaults, 1099-R reopen, viewer-disabled save, public-hidden controls, empty browser storage, desktop1440x1000/mobile390x844 no horizontal overflow and no page errors. Screenshots outside the repo were visually inspected. An early script assertion needed to wait for async reopen; a later scripted confirmation incorrectly expected a dialog after a successful save, and was corrected to create unsaved work first. Those were verifier errors, not production defects.

Independent code review found no important defect. JavaScript syntax and whitespace checks passed. Backend unchanged by this checkpoint; prior actual-PostgreSQL suite remains 217 passed/two Linux-only skipped. Browser responses are fictional, not evidence of a composed production identity/storage journey. Actual MFA composition, restored saved-input reopening and live DigitalOcean permissions remain open. Failed default/unconfigured sign-in cannot save. No filing readiness is implied.


Console-health follow-up: collecting actual browser warning/error messages exposed pre-existing inline spacing styles blocked by the protected page CSP. Moved all HATax inline spacing attributes into named CSS classes without relaxing CSP. The same complete rendered-flow check then passed, with only the deliberately denied fictional API request's HTTP404 resource message (and possible missing favicon) allowed; no app warning or runtime/CSP error. This visual follow-up changes no backend rules.


## Actual saved-input recovery checkpoint

The recovery probe now uses TaxInputs to save a fictional W-2 input original and correction through the actual PostgreSQL transaction service and AES-GCM local document adapter. The former metadata-only reference fixture is replaced. Original text includes a leading-zero wage amount, blank withholding and multiple state rows; the correction changes wages and a fictional profile name. Both complete inputs and their exact server reference metadata reopen correctly after local encrypted database/object restoration, completed-bundle inspection and downloaded-bundle actual pg_restore. History contains both versions; unrelated-profile and wrong-document-key access reject.

The reopened corrected input is recalculated with current restored Bookin records: wages200, book profit118000 minor units, combined refund/balance held pending business tax treatment, may_prepare_return=false. All seven snapshot tables match after restoration. Four document versions are recovered (receipt original/correction and tax-input original/correction); a fifth separately committed upload remains outside the snapshot. Actual read-only capture sees all five current versions. Locators still describe verified copies rather than granting recovery/deletion authority.

Final actual probe passed in 7.994 seconds, a single local fixture measurement rather than hosted or user completion time. Storage transfer remains an explicitly fictional SDK-shaped local adapter, and scanning/identity remain synthetic in this probe. Production code unchanged; independent review found no important defect. Actual browser/MFA composition and live Spaces/key recovery/retention still need verification. Detailed current evidence: DATABASE-RESTORE-EVIDENCE.json.


## Real MFA saved-tax-input checkpoint

October 2: the completed local Keycloak password/OTP to HA HTTPS callback probe now saves and reopens tax inputs under the same actual opaque session used for books, tax estimates, documents and support review. Actual PostgreSQL 16, ClamD and AES-GCM local objects participate. Original and correction inputs and server metadata reopen exactly, including leading-zero amounts, blanks and multiple states. Retry preserves the original response; stale edits, missing CSRF, missing edit authority, foreign scope, revoked grants and access after logout are rejected. Revoking edit permission still permits explicitly authorized reading.

Recalculating the reopened correction produces wages of $200 and book profit of $1,180. Refund and balance remain held, and preparation authority remains false. The saved KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json records each check. The final probe exited successfully, and no owned Java, PostgreSQL or ClamD fixture services remained running afterward. Two Linux cleanup tests also passed.

This is actual local MFA/API evidence with fictional taxpayer data. The separate rendered-browser checks use fictional API responses; a combined rendered browser with real MFA remains pending. Hosted DigitalOcean/Spaces, real-user enrollment and recovery, external key recovery, retention execution and filing remain unverified. Runtime uploads remain unactivated.


## Rendered browser with actual MFA session

October 2: optional HA_MFA_BROWSER_NODE extension passed in actual headless Edge against the live local fixture, with no mocked API routes. The opaque cookie from the verified password/OTP callback is passed in memory through subprocess stdin, never written as browser state or logged. The protected /tax screen reopens the saved correction, saves a new fictional correction, reloads and reopens it again. Three saved versions are listed. Browser storage is empty, no page errors occur and the 390-pixel mobile viewport has no horizontal overflow. The final composed probe exited successfully; no owned fixture services remained running.

This verifies rendered tax save/reload/reopen with actual PostgreSQL, ClamD and encrypted local objects under an actual MFA-created session. It reuses that session rather than entering password/OTP in the browser. The browser accepts the disposable self-signed fixture certificate; browser certificate trust is not proven. Separate protocol checks still verify hostname and certificate trust. Hosted DigitalOcean/Spaces, real-user enrollment/recovery, external key recovery, retention execution and filing remain pending.

The extension requires the Windows Node executable via HA_MFA_BROWSER_NODE and the installed Playwright/Edge runtime. HA_PLAYWRIGHT_MODULE can override the module location. It is an optional local verifier, never a production authentication bypass. Authentication reuse follows the Playwright BrowserContext cookie API: https://playwright.dev/docs/api/class-browsercontext.
