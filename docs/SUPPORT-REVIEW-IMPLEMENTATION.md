# Supporting-record review implementation

October 2, 2026. Implementation specification derived from the current code; not an implemented approval workflow.

## Current evidence

ledger.py projects every effective income, expense and payroll event into support_review_required and always leaves support_review_complete false. Text evidence and cash explanations are separate from review. A client-supplied reviewed flag cannot clear the queue. PostgresLedger serializes changes using repository.lock_scope; document corrections use the same scope lock. The existing grants schema permits read/post/correct/upload/restore, with no review authority. HATax deliberately withholds combined liability/refund when business adjustments are unresolved.

## Required behavior

Add an explicit review_support grant, with no implicit grant to posters or readers. Check MFA, subject, business/profile/year and current grant on every read/write. Preserve authorization checks inside the transaction; use the existing scope transaction lock for review and correction writes. A read grant lets clients inspect the queue; it does not approve support.

Store append-only support decisions separately from money postings. Each decision includes UUID, scoped effective event ID, exact event fingerprint, actor, server time, idempotency key, bounded reason, accepted/needs_information status, and optional exact document/version reference. Client fields cannot choose actor/time or government-confirmed payment status. Same-key/same-payload retry returns the original decision; conflicting retry fails. Reconsideration adds a new decision rather than editing history.

A receipt review must resolve the exact scoped document/version and read/authenticate its bytes through Documents before acceptance. A document identifier or evidence text alone is insufficient. Cash entries require a nonblank bounded explanation whose fingerprint is included in the decision. An expense without a receipt remains explicitly missing; a documented exception may become a separate later policy but must not silently declare a receipt present. Reviewer judgment does not prove deductibility or eligibility.

A decision binds to the current effective event and the current document head. Correcting money, explanation, evidence or a linked document invalidates the old acceptance in projections while preserving its history. If corrections race review, serialize under the shared scope lock and re-read the references before committing. The queue must show why a previous decision became stale.

Keep missing_receipts, cash_explanations_missing and support_review_required separate. Completing support review cannot imply complete accounting, a finished tax return, government payment confirmation or filing authorization. The tax draft must remain incomplete until tax-specific adjustments and final-review requirements pass.

## Database implementation

Add a new migration for the grant action and an append-only support_reviews table. Do not rewrite existing migration history or silently upgrade read/post grants. Use composite scope/event foreign keys and composite scope/document/version references, requiring supporting unique indexes as necessary. Row-level checks constrain status/reason/fingerprint types and sizes. Cross-row current-head and event-state checks belong in the transaction, not a CHECK clause that reads other rows.

Repository methods should participate in the existing ContextVar transaction, share lock_scope and expose ordered scoped decisions. Backups already dump the entire ha_connected schema; extend recovery verification beyond its five-table list to include support_reviews before releasing the migration. Dedicated reader grants and future-owner default privileges must include the new table. Recovered decisions must become stale under the same rules as live decisions.

## HTTP and client flow

Expose scoped review queue/history and a CSRF-protected append-decision endpoint through the existing MFA session. Deny foreign and revoked profiles before loading document bytes. The interface shows the entry, original/corrected document, explanation, outstanding reasons and reviewer decision. Submit only the selected decision, reference and reason; server computes identity/fingerprints. Keep the client's own confirmation distinct from a reviewer action. Browser state must refresh after either document or ledger correction.

## Verification gates

Use real PostgreSQL for permission/revocation, durable restart, idempotency, linked-document scope, correction invalidation and serialized review/correction races. Test forged reviewed/actor/time flags, missing evidence, blank cash explanation, unavailable or unauthenticated object bytes and stale document heads. Confirm read-only users cannot approve. Verify monthly/quarterly/annual totals and ledger_revision behavior remain consistent, with no review records counted as money. Extend the actual restore harness to compare review rows and queue state, preserve original/correction bytes and foreign-profile denials. Finally exercise the UI using one real MFA session and fictional entries/documents.

## Primary implementation references

PostgreSQL 16 constraints: https://www.postgresql.org/docs/16/ddl-constraints.html
PostgreSQL explicit locks: https://www.postgresql.org/docs/17/explicit-locking.html

The official references support composite foreign-key integrity and transaction-level lock coordination. Advisory locks require every participating write path to cooperate; they do not automatically lock arbitrary application operations. The design above is an application decision, not a claim that the database implements the workflow for us.


## Implemented foundation checkpoint

Migration002 now provides explicit review_support grant vocabulary and support_reviews with scoped event/document-version foreign keys, bounded fields, decision/request fingerprints and idempotency uniqueness. Update/delete triggers preserve history. Migration runs serialized under a transaction advisory lock and does not grant review authority to anyone. Real PostgreSQL tests prove foreign-scope and missing-document rejection, no automatic review grants and durable append-only rows. The recovery fixture now restores and compares all six tables, including one fictional needs_information decision, through transferred encrypted ciphertext. Service methods, HTTP actions, reviewer interface, byte authentication/current-head validation and correction-aware queue projection are still unimplemented. Database rows alone are not evidence that the client review workflow is complete.


## Service checkpoint

SupportReviews.submit/history now use the shared PostgreSQL transaction and scope lock. Submit requires fresh explicit review_support and read grants, allowlisted bounded fields, current operating entry and optional exact current document head. Linked bytes are authenticated through Documents; accepted expenses require a document, cash entries require an explanation. Actor/time are server-controlled. Payload fingerprints provide same-request retries and conflicting-retry rejection. History is scoped and ordered. Real PostgreSQL checks cover poster denial, explicit reviewer acceptance, durable actor/history, missing/corrupt/stale receipts, missing cash explanations, forged actor and revoked reviewer retries. The service does not yet expose HTTP actions, compute correction-aware queue completion or provide a reviewer interface; client queue behavior remains unchanged.


## Correction-aware projection checkpoint

PostgresLedger now projects scoped ordered review history and current document heads under the shared transaction scope lock. Latest decision governs; changed event fingerprints or superseded document versions reopen review with explicit reasons. Reconsideration preserves prior history. Verified current linked receipts resolve missing-receipt flags independently of outstanding decision status. support_revision counts decisions separately from monetary ledger_revision. Monetary totals, tax completeness and filing authorization remain unchanged. Real PostgreSQL checks cover accepted support, later needs_information, changed amounts, stale receipts and revoked reviewer retries. The actual transferred-bundle restore also compares the nonempty review queue between recovered databases. HTTP/client workflow and concurrent-race stress tests remain open.


## Protected HTTP checkpoint

GET /api/connected/support/reviews returns scoped history; POST accepts {scope,review} and delegates bounded review fields to the service. Both use the existing opaque MFA session. POST requires the existing origin/CSRF verification. Auto-configuration requires the ledger and Documents to share the same PostgreSQL repository; unconfigured service returns503. Unauthorized or foreign resources return404 without details. Apply migration002 before using the routes and provision review_support explicitly for intended reviewers. Actual local HTTP plus PostgreSQL tests cover unsigned401, CSRF403, no-review-grant404, acceptance/idempotency/history, foreign404, queue completion, grant revocation and logout401. The fixture session is synthetic MFA-verified, not a new proof of live provider login. UI and combined live-MFA review flow remain unfinished.


## Reviewer interface implementation checkpoint

HA Bookin now includes current operating-entry selection, entry details, current document-version selection, authenticated document download, accepted/needs_information decision, bounded reason and ordered history. Posting decisions refreshes the projected queue; document corrections also refresh support state. Scope changes clear selectors, history, reason, decision and cached entries; pending requests use scope-generation guards. POST retry preserves its idempotency key until input/context changes. GET /api/connected/events exposes scoped history through existing read checks for the selection list. Document downloads are octet-stream attachments, not executed content. Independent code review found stale reason/decision across client switch; the reset was applied. JavaScript syntax and backend regressions pass. Rendered browser interaction, accessibility and live-MFA reviewer flow remain unverified; this checkpoint must not be presented as completed UI acceptance.
