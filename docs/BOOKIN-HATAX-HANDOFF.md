# Protected Bookin to HATax handoff

October 2, 2026. Implemented locally; hosted signed-in browser journey remains unverified.

After opening a permitted profile/business/year in Bookin, its HATax link carries those scope identifiers to the tax page. The identifiers confer no access. HATax retrieves the existing session's CSRF token and requests `/api/connected/return/estimate`; it never falls back to a public wage-only estimate when connected access fails.

The protected server reads the latest annual ledger projection and includes it as `business_draft`. It requires the selected return year to match the business year. Scope authorization, session and CSRF checks apply through the same API boundary as books and documents.

When business records exist, the combined estimated tax, refund and balance are held for review. The UI displays saved book profit and ledger revision alongside the review reason. Book profit is not added directly to personal AGI or treated as verified Schedule C profit. Recorded estimated payments remain unconfirmed; reserve scenarios do not move money. Business tax adjustments, self-employment tax and complete payment/credit treatment remain unfinished.

Tests verify saved-book carry-forward, year matching, unrelated scope denial, anonymous/CSRF rejection and suppression of an incomplete wage-only refund. The combined HTTPS/PostgreSQL verifier exercises the handoff in five fictional trials. Identity and scanning in that verifier remain explicitly synthetic; it does not establish hosted MFA, real scanning or filing readiness.

Independent review found a hardcoded retirement label for the business review item. Corrected to render the actual form name and omit a null index. JavaScript syntax and UTF-8 checks passed. A production browser journey still requires actual configured identity, document storage/scanner and hosted access.
