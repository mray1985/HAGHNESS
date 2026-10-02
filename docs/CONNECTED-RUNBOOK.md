# Connected service: local runbook

This service is separate from the legacy calculator. It is incomplete and is for fictional data only.

Run from the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m ha.connected.server --port 8766
```

Open http://127.0.0.1:8766/ for the locked preview. The HTTP loopback preview cannot establish its Secure authentication cookies. Authentication requires HTTPS with a trusted certificate or a correctly configured HTTPS reverse proxy. Do not enter taxpayer information into the preview.

The connected configuration requires all of `HA_DATABASE_URL`, `HA_AWS_REGION`, `HA_COGNITO_POOL`, `HA_COGNITO_CLIENT`, and `HA_COGNITO_DOMAIN`. Keep database credentials in a secret manager rather than source control. The origin must match the registered callback ending in `/api/auth/callback`. Apply migrations with a separate migration role before starting the service. The runtime does not apply migrations.

Cognito must enforce software-token MFA and authorization-code login. The server verifies that configuration before login, uses PKCE and browser-bound state, and validates the signed identity token. Sessions and login handshakes currently reside in one process: use exactly one worker until a shared session store is implemented. Restarting the service ends sessions.

Document uploads remain unavailable in the runtime until an actual scanning provider and private storage configuration are integrated. The S3 adapter and document service have tests, but those tests do not establish cloud deployment readiness.

Run the database-backed test suite using the ignored local PostgreSQL fixture:

```powershell
.\.venv\Scripts\python.exe scripts/dev_postgres.py test
.\.venv\Scripts\python.exe -m scripts.verify_database_restore
```

The restore command creates a separate fictional database and preserves the source. Its report is `docs/DATABASE-RESTORE-EVIDENCE.json`. This proves a local database restore; it does not prove an AWS Backup restore or encrypted object recovery.

Remaining release gates include a configured AWS account, infrastructure and least-privilege runtime roles, hosted MFA verification, document scanning, encrypted object restore, shared sessions, complete tax calculations, official PDF mapping, state workflows, payment-provider agreements, and end-to-end security review. No payment or return submission is enabled.
