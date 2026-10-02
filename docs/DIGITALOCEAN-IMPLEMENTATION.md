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

Use a Linux DigitalOcean Droplet for the document-enabled Python service and ClamD, with HTTPS ingress and a protected Unix scanner socket. Use a separate Keycloak host, managed PostgreSQL and private versioned Spaces. Document encryption keys must be mounted outside the application checkout, with independent protected recovery copies. This matches the implemented Unix-socket scanner and mounted-key runtime; App Platform is currently only a locked preview option.

The Keycloak PKCE adapter, signed MFA-claim checks, client-encrypted Spaces adapter and fail-closed ClamD integration are implemented. Live identity policy, scanner/signature operation, bucket controls and hosted recovery remain unverified. One origin and opaque session serve Bookin and HATax; sessions currently support one application process. See KEYCLOAK-IMPLEMENTATION.md, DOCUMENT-SCANNING.md and SPACES-DOCUMENT-STORAGE.md.

## Deployment sequence

1. Review DIGITALOCEAN-COST-PLAN.md and confirm account, region and available database edition before provisioning. No paid resources have been created.
2. Build and verify the Linux image. Prepare the Droplet service, HTTPS proxy, scanner socket permissions and external key mounts. The existing App Platform spec does not configure these document dependencies.
3. Provision managed PostgreSQL with TLS, trusted sources and separate migration/runtime roles. Isolate Keycloak database credentials and privileges from the application.
4. Configure Keycloak password/OTP policy, private Spaces versioning and fresh ClamD signatures. Keep credentials outside GitHub and chat.
5. Verify real MFA, scanner clean/infected/error cases, cross-profile denials, preserved versions, logout and recovery with fictional documents. Measure hosted timings and actual charges.
6. Configure and prove 35-day/12-month backup retention, independent key recovery and outage procedures. Complete tax engine/PDF/state/payment work before claiming a filing product.

The earlier $30 DigitalOcean-plus-Supabase estimate does not price this target. The new component subtotal is a planning scenario, not a complete operating quote or tested capacity commitment.

## ChatGPT review entry points

Read this file, `docs/CONNECTED-PROGRESS.md`, `docs/DATABASE-RESTORE-EVIDENCE.json`, the approved plans under `docs/superpowers/plans/`, `ha/connected/`, migrations and connected tests. Current local tests establish domain/API/database behavior, not live tax correctness or hosted MFA. Daily source PDFs are retained locally and intentionally excluded from this push.

Official references: https://docs.digitalocean.com/products/app-platform/ and https://docs.digitalocean.com/products/app-platform/reference/app-spec/ .


HATax is included in the connected service at `/tax`. The protected handoff reads authorized Bookin projections and holds the refund estimate when business records need tax review. Personal form drafts remain in page memory; protected durable form saving and filing are unfinished. See BOOKIN-HATAX-HANDOFF.md.

Linux native-service, nginx and ClamD settings templates are now in deploy/digitalocean/droplet/. See its README for explicit activation gates and current validation limits.
