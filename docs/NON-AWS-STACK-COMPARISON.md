# Existing stack and non-AWS options

Checked October 2, 2026. Recommendation only: no provider account created, no paid resource provisioned, no taxpayer data used.

## What HAGHNESS actually uses

| Area | Current evidence | What can be reused |
|---|---|---|
| Hosting | Local Python standard-library HTTP server, `ha/server.py`; local connected service `ha/connected/server.py`. No deployment manifest or hosting account configuration found in this checkout. | Python application and HTML/CSS/JavaScript; GitHub source repository |
| Database | Original calculator has no persistent client database. New connected foundation uses psycopg and PostgreSQL, tested against ignored local PostgreSQL on port 55432. | Schema, transactional ledger, scope constraints and PostgreSQL repository |
| Authentication | Original calculator has no client authentication. New connected code has opaque server sessions and a Cognito-specific OAuth adapter, not a configured provider. No matching provider environment variable names found. | Session/CSRF boundary and per-action authorization; provider adapter must change |
| Documents | No configured remote store. New immutable document metadata/service and S3/KMS adapter have local tests. MemoryObjects is an unencrypted test double. Runtime upload is disabled pending scanning. | Version-chain service, hashes, permissions and metadata; storage adapter must change |
| Backups | Actual fictional PostgreSQL dump/restore passed locally, including recovered permission denial. No cloud or document object restore proved. | Recovery comparison and fixture; document backup mechanism still required |

Git remote: https://github.com/mray1985/HAGHNESS.git. Source control is not application hosting, a database or document backup. Repository inspection cannot rule out accounts elsewhere, but the user confirmed no existing hosted MFA and no AWS account.

## Compatible options

Both options retain Python and PostgreSQL. Neither requires an HA-owned AWS account. Provider internal infrastructure is separate from that account choice.

Managed Supabase uses AWS infrastructure underneath. Avoiding an AWS account is different from avoiding AWS infrastructure entirely. If the latter is required, use an independent infrastructure option such as self-hosting on DigitalOcean; that adds patching, key management, monitoring and recovery operations and needs separate sizing and pricing.

| Criterion | DigitalOcean App Platform + Supabase Pro | Render Python service + Supabase Pro |
|---|---|---|
| Published small-instance baseline | $5/month App Platform shared 512 MiB + $25/month Supabase Pro = $30/month baseline | $25/month Supabase Pro plus Render application compute; readable current pricing did not confirm its dollar amount, so no total is asserted |
| Database | Supabase PostgreSQL; retain existing repository and migration, configure TLS, limited runtime role and suitable connection pooling | Same |
| Private per-profile documents | Private Supabase bucket; scope linked through server metadata and policies. Reject cross-profile access regardless of guessed path. Use immutable unique keys for each correction. Never expose service-role keys. | Same |
| MFA session reuse | Supabase TOTP authentication. Server validates issuer, audience, expiry, subject and `aal2` before opening its existing opaque cookie session; Bookin’ and HATax must share the same application origin/session boundary. No second vault password. | Same |
| Backups | Pro includes seven days of daily database backups. Storage objects are excluded: implement separate retained document copies, integrity manifest and independent restore test. PITR/longer retention cost extra. | Same |
| Integration effort | Moderate: adapt authentication and storage, configure Python deployment/TLS/secrets, implement scanning and recovery; no ledger rewrite | Similar: host choice mainly changes deployment configuration |

These amounts are starting arithmetic, not a production quote. Assumes one small application instance and one Supabase Micro project within included quotas. Excludes independent document backups, scanning, email delivery, domain, additional compute, bandwidth/storage overages, PITR, tax and payment providers. Load tests determine whether 512 MiB is sufficient. Free tiers are suitable for fictional experiments, not evidence that live-client access/recovery is ready.

Recommendation: **DigitalOcean App Platform + Supabase Pro** for the first costed candidate. It retains the tested PostgreSQL work, supplies database/auth/private storage through one backend provider, and has a clearly documented $5 application tier. Render is a compatible alternative if deployment experience or its service features justify the difference. This is an engineering recommendation, not approval to purchase.

Supabase is not a drop-in replacement for Cognito or customer-managed KMS. Its MFA assurance must be verified on the server; ordinary sign-in does not suffice. If HA requires customer-held encryption keys outside provider control, add and price a separate key-management/envelope-encryption design before claiming that requirement is met.

## Verification before actual client use

Use fictional documents to prove required MFA, session reuse, logout/revocation, cross-profile read/write/download denial, original/correction preservation, clean-file scanning and restore of both metadata and bytes into a separate recovery destination. Confirm backup retention and keys survive the intended failure scenario. Maintain a recorded final provider quote before deployment. Full tax calculations, official return PDFs and filing/payment integrations remain separate unfinished work.

## Primary sources

- DigitalOcean instance pricing: https://docs.digitalocean.com/products/app-platform/details/pricing/
- Render pricing and compute plans: https://render.com/pricing and https://render.com/docs/compute-plans
- Supabase plans: https://supabase.com/pricing
- Supabase TOTP/MFA and assurance: https://supabase.com/docs/guides/auth/auth-mfa
- Private object access policies and service-key bypass: https://supabase.com/docs/guides/storage/security/access-control
- Database backups and explicit object exclusion: https://supabase.com/docs/guides/platform/backups
