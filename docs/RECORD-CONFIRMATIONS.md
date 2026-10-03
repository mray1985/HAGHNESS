# Review statements for entered business records

October 3, 2026. This completes a local review step in the approved connected
workflow, without treating a user statement as independent verification.

A separately permitted user compares entered income and expenses with their
bank, card, cash and other records, adds omitted transactions, chooses a review
cutoff date and records their explicit accuracy/completeness statement. The
cutoff must be in the business tax year, include every recorded posting date,
and not be in the future. An empty checkbox is never submitted automatically.

Each append-only record retains its server-authenticated actor, recording time,
statement version `records-v1`, explanation, review cutoff, ledger revision and
SHA-256 fingerprint of the entire ledger history. The whole-year revision is
used even if the visible reporting view is monthly or quarterly. A cutoff in
October does not confirm the remaining months of the year. All history remains
visible to permitted readers. Any ledger addition/correction changes the
snapshot and makes an earlier statement stale. Document/support review is a
separate workflow; changing a receipt does not constitute a new ledger entry.

The projection continues to report `entry_completeness: not_verified` and
`missing_entries: null`. Its separate `records_confirmation` records whether a
user statement matches the current entered ledger, with
`independently_verified: false`. Current means the statement applies to the
unchanged ledger through its cutoff, not that HA detected every omitted entry.
Book profit, support decisions, payment confirmation, tax eligibility,
`may_prepare_return` and filing authorization are unchanged. HATax carries this
metadata within the connected business draft and continues holding the combined
refund/balance pending business tax treatment.

## Authority and persistence

Migration 004 adds `ha_connected.record_confirmations` and the separate
`confirm_records` permission. It grants no existing user authority. Both `read`
and `confirm_records` must currently cover the exact client/business/year for
submission. Read authority allows history/status viewing; confirmation authority
can be revoked without deleting history. The existing MFA cookie, Origin and
CSRF checks apply to `POST /api/connected/records/confirmations`. GET uses the
same permitted scope. No second vault sign-in is introduced.

Scope locking serializes statements with ledger writes. The displayed revision
must still match at submission; concurrent changes reject the statement for
review again. Exact retries return the original record, conflicting retries
fail, and revocation denies retries too. SQL triggers reject UPDATE/DELETE.
Saving never changes income, expense, reserve or government-payment totals.

UI controls remain disabled until current authority and the displayed ledger
revision are confirmed. Opening another case or signing out clears fields and
history; earlier asynchronous responses cannot repopulate them. During a save,
statement fields are disabled. A failed save preserves its idempotency key until
the user edits the statement or opens a different case.

The encrypted backup verifier includes this table, verifies byte-for-byte row
recovery and current/stale history semantics in both actual local PostgreSQL
restore paths. Migration operators must grant the dedicated backup reader
SELECT access to new tables or set appropriate owner default privileges; runtime
startup does not apply migrations or grant access. Hosted backup/retention and
independent external key retrieval remain pending.

## Verification

Five real PostgreSQL tests cover explicit authority, scoped history, exact and
conflicting retries, stale submission, concurrent retries, immutable history,
bounded fields, review-date rules, CSRF/session/scope/revocation and unchanged
completeness/support/filing flags. The full suite ran 293 tests: 289 passed and
four Linux-only checks skipped on Windows. The local encrypted restore preserved
two confirmation records against ledger revisions six and eight, all originals,
$1,180 profit and $125 recorded/$0 confirmed payment totals. It completed in
11.232 seconds for one fictional local fixture, not hosted recovery evidence.
See DATABASE-RESTORE-EVIDENCE.json. The scanner and transfer store there are
synthetic, and key custody is a separate ignored local file, not off-host custody.

Independent code review found no important defects. The actual local
Keycloak/nginx/PostgreSQL/ClamD browser fixture passed review saving, unchecked
submission prevention, preserved history, invalidation after a payment correction,
and clearing the new review fields/history on unrelated-profile denial. Mobile
Bookin review controls and HATax fit without overflow; no page errors or browser
storage persisted. Existing draft save/reopen and logout-denial checks passed.
The final browser portion measured 7.4 seconds, excluding fixture startup and
OTP waits, not a customer completion-time promise. Proxy temporary activity was
absent and inherited logs empty; owned proxy/services stopped afterward.
KEYCLOAK-NGINX-SESSION-EVIDENCE.json records this local result. The browser
explicitly tolerates a self-signed fixture certificate, and no hosted provider
readiness is implied. [Fictional mobile panel](screenshots/record-confirmation-mobile.png)
contains only the post-login review, never MFA setup/password/OTP data.

An initial verifier mistakenly checked invalidation before posting the correction
and timed out. Its assertion was moved after the actual correction response;
the rerun and final extended field-clearing/capture run passed. This was verifier
ordering, not a change to application confirmation or MFA policy.
