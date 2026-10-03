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


HATax is included in the connected service at `/tax`. The protected handoff reads authorized Bookin projections and holds the refund estimate when business records need tax review. Protected encrypted form draft saving and reopening are now exercised in the local composed MFA journey; hosted saving and filing remain unverified. See BOOKIN-HATAX-HANDOFF.md and KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json.

Linux native-service, nginx and ClamD settings templates are now in deploy/digitalocean/droplet/. See its README for explicit activation gates and current validation limits.

October 3: actual isolated local nginx now validates the proxy template and fictional redirect/callback, large upload/download, oversized-body rejection and upstream failure paths. An inherited HTTP redirect request-log leak was reproduced and fixed. No temporary-body create/write events or inherited request logs were observed in the covered paths. See NGINX-PROXY-VERIFICATION.md and NGINX-PROXY-EVIDENCE.json. This does not establish hosted ingress or application MFA/storage through nginx; account setup, activation and operational recovery remain pending.

The subsequent optional composed proxy mode now also passes real HA password/OTP, PostgreSQL16, ClamD and encrypted local documents through nginx, including the rendered Bookin/HATax journey. This supersedes the application-through-proxy gap above for local fictional fixtures only. See KEYCLOAK-NGINX-SESSION-EVIDENCE.json and NGINX-PROXY-VERIFICATION.md. Hosted ingress, provider database/Spaces, browser certificate trust, activation and operational recovery remain unverified.


## Read-only account prerequisite check

With a DigitalOcean token already supplied through the operator's protected environment, run:

```powershell
.venv/Scripts/python.exe -m scripts.check_digitalocean_account
```

The command reads DIGITALOCEAN_ACCESS_TOKEN and performs only HTTPS GET https://api.digitalocean.com/v2/account. Use account:read scope; it does not need resource creation permissions. It refuses redirects and bounds/validates the response. Output includes only status/email-verification booleans and explicit resources_created=false/deployment_verified=false. Account email, name, UUID, status message, token and provider error details are not printed. Do not put the token in command arguments, source files or chat.

Exit 0 means the account prerequisite is active with verified email; exit 1 means an account warning/lock/unverified condition; exit 2 means missing token or inability to establish account status. Passing does not confirm billing, resource quotas, correct team, Spaces policies, deployment permissions, backups or recovery. Confirm the intended account/team in the provider console before paid provisioning.

Official endpoint and scope reference: https://docs.digitalocean.com/reference/api/reference/account/. Five focused tests passed. The actual local invocation reported token_not_configured; no provider account or resource was verified or changed. Deployment remains pending user-controlled account setup.

October 3 Spaces prerequisite: `python -m scripts.check_spaces_configuration` provides a read-only versioning/bucket-ACL check for an existing explicit bucket using privately supplied Spaces credentials. It restricts signed requests to the selected regional HTTPS endpoint and only the two required GET operations; no ambient AWS fallback or provider mutation. Eight local tests pass, including actual SDK serialization with synthetic transport. The local invocation reports configuration_not_supplied; live object privacy, CDN/policies, provider recovery and deployment remain false/unverified. See SPACES-DOCUMENT-STORAGE.md for permissions, exit codes and limits. This is not authorization to activate document uploads.
