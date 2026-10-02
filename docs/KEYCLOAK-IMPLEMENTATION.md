# Independent MFA implementation · Keycloak

The runtime supports `HA_AUTH_PROVIDER=keycloak` alongside disabled preview
and optional Cognito. This is code and synthetic-token verification, not a
configured identity service or a passed hosted MFA journey. DigitalOcean account
provisioning and identity hosting remain pending.

## Required identity setup

Use a dedicated HA realm on an HTTPS Keycloak host with a maintained supported
release. Configure a public OIDC client with Standard Flow only, PKCE S256
required, direct grants and implicit flow disabled. Register the exact HA HTTPS
callback `/api/auth/callback`; restrict redirect URIs and web origins to HA.

Configure realm ACR mapping `2` to LoA 2 and the client minimum ACR value 2.
The level-2 flow must require password plus OTP, including OTP enrollment when
absent. An optional conditional-OTP execution is insufficient. Set execution
references `pwd` and `otp`; add the AMR protocol mapper to the ID token so it
reports successfully completed executions. Keep the normal ACR mapper. Do not
map ACR or AMR from editable user attributes or hardcoded claims.

The adapter requests essential ACR 2 and fresh authentication. It then validates
signature, issuer, audience, authorized client, ID-token type, nonce, freshness,
ACR 2 and both completed password/OTP references. A request for a level alone
is not accepted as evidence. HA then creates one opaque Secure/HttpOnly session
for the connected products; document permission checks continue server-side.

## Application settings

Set outside source control: `HA_AUTH_PROVIDER=keycloak`, `HA_DATABASE_URL`,
`HA_KEYCLOAK_ISSUER` (for example `https://identity.example/realms/ha`) and
`HA_KEYCLOAK_CLIENT`. Database TLS/trusted-source restrictions and least-privilege
roles remain deployment requirements. Do not mix Cognito settings into this mode.
Identity permission subjects use `<issuer>|<subject>`; grants must be explicitly
provisioned for that identity. Changing issuer does not inherit old grants.

One process remains required because sessions and pending OAuth exchanges are
not yet shared. Restart ends sessions. Storage/scanning remains unavailable in
the runtime until separately integrated. No real taxpayer onboarding yet.

## Required hosted evidence

Prove OTP enrollment and challenge, rejection of password-only and modified ACR
requests, correct signed AMR/ACR, expired/replayed callback rejection, session
reuse for Bookin and tax records, logout/revocation, and unrelated-profile denial.
Also verify recovery codes/helpdesk reset policy, backups, patches and HTTPS.
Synthetic tests do not replace these gates. Never store tokens, OTP secrets or
identity recovery credentials in repository evidence.

References: [Keycloak authentication and step-up configuration](https://www.keycloak.org/docs/latest/server_admin/index.html),
[Keycloak ID-token construction](https://github.com/keycloak/keycloak/blob/main/services/src/main/java/org/keycloak/protocol/oidc/TokenManager.java).


## Local real-runtime preparation

October 2: installed Ubuntu OpenJDK 25 and downloaded official Keycloak 26.8.0 using scripts/setup_local_keycloak.py. The published GitHub asset SHA-256 matches the saved archive. Local files remain under ignored .connected-local/keycloak; no identity credentials are committed. The setup now stages downloads/extraction and publishes completed results, with an extraction completion marker. The marker records original extraction provenance, not a continuous integrity check of every mutable runtime file.

scripts/verify_keycloak_runtime.py starts its own HTTPS-only loopback dev runtime with a temporary certificate and isolated temporary H2 database. It verifies master discovery, exact issuer/JWKS URL and RSA key availability using certificate and hostname verification. It terminates its own process group. The saved KEYCLOAK-RUNTIME-EVIDENCE.json does not claim password/OTP or application-realm verification.

Development H2 and a locally trusted test certificate are fixture choices, not hosted configuration. Next: build the required application realm/client/OTP flow, prove signed ACR/AMR from actual completed authentication, then connect HA's session and document access. The independent hosted MFA requirement remains incomplete.

Official setup source: [Keycloak OpenJDK guide](https://www.keycloak.org/getting-started/getting-started-zip).

## Importable application realm

`deploy/digitalocean/keycloak/ha-realm.json` targets the installed Keycloak 26.8.0 release. It contains no users, passwords, OTP secrets or administrative credentials. Replace the reserved `https://ha.example` callback and origin with the exact application HTTPS origin before a hosted import. Import into a new dedicated realm; do not overwrite a live realm without reviewing its existing clients and users.

The browser flow has one conditional LoA2 subflow requiring username/password and OTP. LoA lifetime is zero, so that level must be completed on each new authentication. Completed-execution references `pwd` and `otp` have a 600-second AMR reporting window. The AMR ID-token mapper uses actual completed executions; the default Keycloak ACR scope supplies ACR. Client minimum ACR is 2, and S256 PKCE is required. Public registration, automatic password reset, implicit grants and password direct grants are disabled. Recovery and controlled onboarding still require implementation and verification.

The real-runtime probe accepts `--realm-file deploy/digitalocean/keycloak/ha-realm.json`. It changes only the fixture callback/origin to loopback, imports into its temporary H2 database and probes HTTPS discovery for `/realms/ha`. It also checks missing-PKCE rejection, exact redirect restriction, password challenge availability and explicit direct-grant rejection. Evidence is saved separately in `KEYCLOAK-REALM-EVIDENCE.json`. These checks do not complete OTP enrollment/login or prove signed AMR/ACR. Application sessions and hosted recovery remain outstanding.

Configuration keys were checked against [Keycloak 26.8 authentication flow documentation](https://github.com/keycloak/keycloak/blob/26.8.0/docs/documentation/server_admin/topics/authentication/flows.adoc) and [its execution reference and ACR constants](https://github.com/keycloak/keycloak/blob/26.8.0/server-spi-private/src/main/java/org/keycloak/models/Constants.java).

The missing-PKCE probe deliberately does not follow OAuth redirects to the inactive callback. It requires Keycloak 26.8's exact callback error redirect (`invalid_request` describing `code_challenge`), rather than accepting an arbitrary HTTP 400. No callback code or identity token is written into evidence.
