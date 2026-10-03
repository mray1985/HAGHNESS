# Protected HATax input persistence

Status: input codec, database reference foundation and saving/opening service implemented and tested; HTTP routes and user controls are not implemented. HATax still loses entries on refresh. This is the next core workflow feature, not completed saving.

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
