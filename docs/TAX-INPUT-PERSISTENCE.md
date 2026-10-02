# Protected HATax input persistence

Status: input codec implemented and tested; encrypted persistence, routes and user controls are not implemented. HATax still loses entries on refresh. This is the next core workflow feature, not completed saving.

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
