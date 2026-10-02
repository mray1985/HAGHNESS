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
