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

Whole-goal status: incomplete. No cloud resources provisioned; provider-backed MFA, PostgreSQL, encrypted storage restore, payments and end-to-end deployment still require verification.
