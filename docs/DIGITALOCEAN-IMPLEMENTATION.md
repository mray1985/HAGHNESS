# DigitalOcean implementation and review handoff

User selected DigitalOcean and authorized pushing the updates on October 2, 2026.

DigitalOcean supplies computers and managed cloud services on which HA can run. It is separate from GitHub, which stores the source. No AWS account is required for the selected direction.

## Implemented in this change

- DigitalOcean App Platform deployment specification at `deploy/digitalocean/app.yaml`, sourcing `codex/connected-books` without automatic deploys.
- Linux container definition, restricted runtime user and build-context exclusions for credentials, daily documents and local databases.
- Explicit HTTPS-proxy runtime mode for App Platform ingress.
- Default authentication provider is disabled. Cognito is now an explicit optional adapter rather than an implicit requirement.
- Locked fictional-data preview, durable PostgreSQL domain/repository, correction history, per-action client/business/year permission checks and recovery test harness.

The deployment spec starts only the locked preview. Importing it creates a chargeable application; it does not create a database, identity provider or document bucket. No deployment was performed by this change. Local Docker is unavailable, so the container build remains unverified; Python/browser tests do not substitute for that build.

## Fully independent target

Use DigitalOcean App Platform for Python, DigitalOcean managed PostgreSQL for the existing database schema, and a separately hosted OIDC identity service with required TOTP MFA, such as Keycloak on DigitalOcean. Use private document storage with immutable version keys and external key management. Select and verify storage encryption/versioning capabilities before adapting the existing S3/KMS-specific adapter; API compatibility alone does not establish those controls. Managed Supabase is excluded from this fully independent target because its hosting uses AWS underneath.

The independent Keycloak code/PKCE adapter and signed MFA-claim checks are implemented; required realm configuration and hosted verification are in docs/KEYCLOAK-IMPLEMENTATION.md. Identity deployment, live policy verification, scanning and hosted encrypted storage/recovery remain unfinished. Local encrypted document recovery is verified separately. The present server does not silently accept an arbitrary OIDC provider or ordinary non-MFA tokens. One application origin and opaque session should serve both Bookin’ and HATax. Session storage currently limits operation to one application process; a shared transactional session store is required before scaling.

## Deployment sequence

1. Review this branch and current resource prices. Build the Dockerfile for Linux AMD64 and verify the locked preview.
2. Connect the user-controlled DigitalOcean account to this GitHub repo. Import the app spec for a fictional-data preview; public ingress must enforce HTTPS.
3. Provision managed PostgreSQL separately, use TLS and trusted-source restrictions, apply migrations through a migration role, and grant only necessary runtime privileges.
4. Implement and configure independent MFA identity and document scanning/storage. Store credentials outside GitHub. No credentials should be pasted into chat.
5. Prove cross-profile denials, session revocation, original/correction preservation and actual recovery of both database and document bytes with fictional fixtures.
6. Complete tax engine/PDF/state/payment work before claiming a usable filing product.

The previously quoted $30 DigitalOcean-plus-Supabase baseline does **not** price this independent target. Include application, identity host, database, storage, scanning, external keys, backups, egress, email and operations in the final quote.

## ChatGPT review entry points

Read this file, `docs/CONNECTED-PROGRESS.md`, `docs/DATABASE-RESTORE-EVIDENCE.json`, the approved plans under `docs/superpowers/plans/`, `ha/connected/`, migrations and connected tests. Current local tests establish domain/API/database behavior, not live tax correctness or hosted MFA. Daily source PDFs are retained locally and intentionally excluded from this push.

Official references: https://docs.digitalocean.com/products/app-platform/ and https://docs.digitalocean.com/products/app-platform/reference/app-spec/ .


HATax is now included in the same connected-service container at `/tax`. The
HA Bookin header links to the form-first preview. This is stateless arithmetic
with page-memory drafts, not protected persistence or filing. Local integration
preview: `http://127.0.0.1:8768/`; hosted deployment remains unprovisioned.
