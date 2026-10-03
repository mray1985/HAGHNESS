# Connected service: local runbook

This service is separate from the legacy calculator. It is incomplete and is for fictional data only.

Run from the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m ha.connected.server --port 8766
```

Open http://127.0.0.1:8766/ for HA home, `/connected.html` for the locked Bookin entrance, or `/tax` for HATax. The HTTP loopback preview cannot establish its Secure authentication cookies. Authentication requires HTTPS with a trusted certificate or a correctly configured HTTPS reverse proxy. Do not enter taxpayer information into the preview.

The selected non-AWS stack uses `HA_AUTH_PROVIDER=keycloak` with all of
`HA_DATABASE_URL`, `HA_KEYCLOAK_ISSUER`, and `HA_KEYCLOAK_CLIENT`. Do not mix
Cognito and Keycloak settings. Keep credentials outside source control. Register
the exact HTTPS origin callback ending in `/api/auth/callback`. Apply migrations
with a separate migration role before starting the service; runtime startup does
not apply them. Credential-free realm and native service instructions are in
KEYCLOAK-IMPLEMENTATION.md and DIGITALOCEAN-IMPLEMENTATION.md. The earlier Cognito
adapter remains optional, but AWS is not required for this selected stack.

Keycloak must require password and OTP, PKCE and browser-bound state. The server
validates signed identity tokens and the required MFA assurance. Sessions and
login handshakes currently reside in one process: use exactly one worker until a
shared session store is implemented. Restarting the service ends sessions.

Document uploads remain unavailable by default. Explicit Spaces/key/ClamD configuration can now wire the service into the existing session; see DOCUMENT-SCANNING.md for deployment and live verification requirements. The S3 adapter and document service have tests, but those tests do not establish cloud deployment readiness.

Run the database-backed test suite using the ignored local PostgreSQL fixture:

```powershell
.\.venv\Scripts\python.exe scripts/dev_postgres.py test
.\.venv\Scripts\python.exe -m scripts.verify_database_restore
```

The restore command creates a separate fictional database and preserves the source. Its report is `docs/DATABASE-RESTORE-EVIDENCE.json`. This proves a local database and encrypted-file restore, including original/corrected bytes and cross-profile denial. It does not prove hosted storage or provider backup recovery. The harness creates separate source/recovery databases and leaves existing test data untouched. Fictional encryption keys are kept in the ignored `.connected-local/recovery-keys` directory, separately from object backups. Do not use this fixture key setup for production.

Remaining release gates include a configured DigitalOcean account, independent identity/storage services and least-privilege runtime roles, hosted MFA verification, document scanning, hosted encrypted object restore, shared sessions, complete tax calculations, official PDF mapping, state workflows, payment-provider agreements, and end-to-end security review. No payment or return submission is enabled.

Independent Keycloak mode and required realm configuration are documented in
`docs/KEYCLOAK-IMPLEMENTATION.md`. Select it explicitly; disabled preview remains
the default. Signed MFA-claim tests do not prove hosted identity controls.

Record review statements require the explicit `confirm_records` grant plus
`read` for the same client/business/year. Migration 004 grants no authority to
existing users. See RECORD-CONFIRMATIONS.md. Apply its table using the migration
role and arrange SELECT access for separately managed backup readers, including
future-object default privileges, before claiming new-table backup coverage.
User statements do not independently verify complete books or authorize filing.

Reserve choices are read-only previews through the protected draft GET. No new
migration or payment permission is needed. Percentage and optional extra amount
clear on refresh or case change. See RESERVE-CHOICE.md for supported values,
rounding, reporting-period behavior and the actual local MFA browser evidence.
