# Independent MFA implementation Ã‚Â· Keycloak

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

## Real password/OTP protocol probe

The runtime script's optional `--mfa-login` mode injects a newly generated fictional user into the private temporary realm import. Its password and pre-enrolled TOTP secret are temporary fixture data, never deployment credentials. The dedicated helper `scripts/verify_keycloak_mfa.py` uses verified HTTPS, cookies and restricted form destinations to exercise password and OTP challenges. It requires an OTP challenge after password alone and after an incorrect OTP, completes a correct OTP, exchanges the state-bound authorization code with PKCE, and passes the resulting signed ID token to the application's actual KeycloakVerifier. Reusing the authorization code must be rejected. Evidence contains booleans, not tokens or secrets.

Run from the repository on Linux with project JWT dependencies installed, using the same `--distribution`, `--realm-file` and `--report` arguments plus `--mfa-login`. The local Linux dependency cache is ignored; the project pins PyJWT in requirements-connected.txt. No live user is created or updated, and the entire fixture database is removed after the probe.

This is a protocol integration test, not a visual browser test or proof of OTP enrollment. The fixture begins with an enrolled OTP credential. Recovery, enrollment, protected HTTP callback/session creation, reuse across Bookin/HATax/documents and hosted deployment remain required.

OTP fixture encoding was checked against [Keycloak 26.8's credential model](https://github.com/keycloak/keycloak/blob/26.8.0/server-spi/src/main/java/org/keycloak/models/credential/OTPCredentialModel.java). The local TOTP generator also passes the RFC 6238 SHA-1 time-59 reference vector at six digits.

## Composed local connected-session proof

October 2: `--mfa-login --connected-session` passed in actual Linux Keycloak, HA HTTPS, PostgreSQL 16, ClamD and AES-GCM local object storage. The saved `KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json` reports the composed journey separately from the initial standalone MFA probe. It begins a new login through `/api/auth/login`, follows the real password/OTP flow, sends the state-bound code and login cookie through `/api/auth/callback`, and receives HA's Secure/HttpOnly opaque session cookie. The server performs the actual PKCE token exchange and signed-claim verification; the test does not inject a principal or session.

That one cookie accesses books, the connected HATax draft and document upload/read/correction. Explicit test grants are inserted for the verified issuer/subject, profile, business and year. Card/cash entries, missing receipt, a book correction and recorded owner tax payments yield $1,180 book profit. The combined refund remains withheld pending business-tax review. Another profile is denied; deleting grants denies books/documents while the identity session remains active. CSRF-free uploads fail. The real scanner rejects EICAR without publishing metadata or objects. Original/corrected documents remain separately readable; stored object bytes do not contain the receipt plaintext. Callback replay and access after logout fail.

The new fixture uses its own temporary PostgreSQL cluster under the installed `postgres` account, with a private Unix socket, no TCP listener and rejected host authentication. Root orchestration is needed only for this fixture's OS-user boundary. Existing clusters are untouched. Startup failures attempt owned-cluster shutdown; shutdown failure preserves private cluster files instead of deleting potentially live data. Two Linux tests cover these failure cases. The actual composed run left zero owned fixture services running. The separate Windows regression suite passed 164 tests and skipped these two Linux-only tests; both passed on Linux.

For the local run, add `--connected-session` to the MFA probe command and execute the fixture as Linux root. The helper waits for the next TOTP period because the initial standalone probe already consumed the fixture's current code. This fixture wait is not a production login-latency measurement.

This proves the local server/API connection. It does not prove hosted DigitalOcean/Spaces, real-user OTP enrollment/recovery, browser interaction, document backup scheduling, final tax calculations or filing. Local object keys are ephemeral fixture keys; external recovery and Spaces still require their own end-to-end evidence.


## Real MFA support-review session extension

October2 composed local probe now includes the support-review API under the actual Keycloak password/OTP to HA HTTPS callback session. Missing CSRF and missing explicit review permission fail before a fictional grant is inserted. The same opaque cookie accepts scanned receipt support, preserves retry/history, and reopens advertising review after document correction. Foreign review history and active-session read/write after grant revocation fail. Actual PostgreSQL16, ClamD and AES-GCM fixture objects participate. Saved KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json identifies these checks separately. This is API/protocol evidence, not a live rendered browser, hosted Spaces, enrollment or recovery proof. Runtime uploads remain unactivated.


## Real MFA saved-tax-input checkpoint

October 2: the completed local Keycloak password/OTP to HA HTTPS callback probe now saves and reopens tax inputs under the same actual opaque session used for books, tax estimates, documents and support review. Actual PostgreSQL 16, ClamD and AES-GCM local objects participate. Original and correction inputs and server metadata reopen exactly, including leading-zero amounts, blanks and multiple states. Retry preserves the original response; stale edits, missing CSRF, missing edit authority, foreign scope, revoked grants and access after logout are rejected. Revoking edit permission still permits explicitly authorized reading.

Recalculating the reopened correction produces wages of $200 and book profit of $1,180. Refund and balance remain held, and preparation authority remains false. The saved KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json records each check. The final probe exited successfully, and no owned Java, PostgreSQL or ClamD fixture services remained running afterward. Two Linux cleanup tests also passed.

This is actual local MFA/API evidence with fictional taxpayer data. The separate rendered-browser checks use fictional API responses; a combined rendered browser with real MFA remains pending. Hosted DigitalOcean/Spaces, real-user enrollment and recovery, external key recovery, retention execution and filing remain unverified. Runtime uploads remain unactivated.


## Rendered browser with actual MFA session

October 2: optional HA_MFA_BROWSER_NODE extension passed in actual headless Edge against the live local fixture, with no mocked API routes. The opaque cookie from the verified password/OTP callback is passed in memory through subprocess stdin, never written as browser state or logged. The protected /tax screen reopens the saved correction, saves a new fictional correction, reloads and reopens it again. Three saved versions are listed. Browser storage is empty, no page errors occur and the 390-pixel mobile viewport has no horizontal overflow. The final composed probe exited successfully; no owned fixture services remained running.

This verifies rendered tax save/reload/reopen with actual PostgreSQL, ClamD and encrypted local objects under an actual MFA-created session. It reuses that session rather than entering password/OTP in the browser. The browser accepts the disposable self-signed fixture certificate; browser certificate trust is not proven. Separate protocol checks still verify hostname and certificate trust. Hosted DigitalOcean/Spaces, real-user enrollment/recovery, external key recovery, retention execution and filing remain pending.

The extension requires the Windows Node executable via HA_MFA_BROWSER_NODE and the installed Playwright/Edge runtime. HA_PLAYWRIGHT_MODULE can override the module location. It is an optional local verifier, never a production authentication bypass. Authentication reuse follows the Playwright BrowserContext cookie API: https://playwright.dev/docs/api/class-browsercontext.


## Connected rendered journey checkpoint

October 2: the actual-session Edge verifier now opens HA Bookin, checks recorded income $1,500, corrected expenses $320 and book profit $1,180, then verifies October monthly, quarterly and annual API and rendered totals without double counting. It checks owner payments recorded $100 versus government-confirmed $0 and the reopened advertising support question. Downloading the corrected receipt through the screen returns exact fictional bytes. Opening an unauthorized profile clears prior totals/documents; returning to the permitted scope and following Open HATax preserves the case. Tax correction/save/reload/reopen still passes. No API routes are mocked.

The final probe passed; no owned Keycloak, PostgreSQL or ClamD processes remained afterward. The browser portion measured 3.7 seconds for one automated local fictional run, excluding MFA/runtime startup. This is not a customer completion-time claim. Browser certificate trust, hosted DigitalOcean/Spaces, real-user enrollment/recovery, external key recovery, retention execution and filing remain unverified. Detailed evidence is KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json.


## Actual rendered password and OTP login

October 2: the latest composed Edge probe now performs password and OTP entry on the real local Keycloak screens and receives its own HA session through the HTTPS callback. It no longer injects the protocol fixture's opaque cookie. Disposable credentials travel through subprocess stdin only; credential form destinations are checked before filling. Secure/HttpOnly/SameSite/Path session cookie properties pass. The same browser session then passes Bookin totals and period views, corrected receipt download, denied-profile clearing, HATax handoff and saved correction/reload/reopen. Clicking Sign out denies subsequent protected tax access. No API routes are mocked.

The browser journey measured 6.3 seconds in one automated fictional run, including browser password/OTP but excluding runtime startup and the fixture's unused-TOTP-period wait. Actual PostgreSQL16, ClamD and AES-GCM local objects participate. The successful probe left no owned services running. Four targeted fixture parser/OTP tests passed on Windows, with two Linux cleanup tests skipped there. Independent review found no important defects in credential/session handling.

Windows could not reach the local Java IPv6-mapped loopback listener during initial rendered-login attempts. The local fixture now uses -Djava.net.preferIPv4Stack=true; socket inspection confirmed 127.0.0.1:8843, and the full rendered journey passed. This follows Oracle's networking property documentation: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/net/doc-files/net-properties.html. This fixture-specific choice does not alter hosted configuration. Failure diagnostics contain fixed step/error-type or network-code labels only.

Browser trust of the disposable self-signed certificate remains bypassed explicitly for this fixture, while separate protocol checks verify hostname/certificate trust. Real-user OTP enrollment/recovery, hosted DigitalOcean/Spaces, external key recovery, operational retention/alerts and filing remain unverified. The latest KEYCLOAK-CONNECTED-SESSION-EVIDENCE.json supersedes earlier cookie-reuse-only checkpoints.


## First-time OTP enrollment evidence - October 3

The disposable local Keycloak26.8.0 probe now supports `--mfa-login --otp-enrollment` with the credential-free realm template. It imports a separate fictional account containing only a fresh password credential and the CONFIGURE_TOTP required action. Password login reaches the setup challenge; an incorrect setup code retains that challenge, a valid code configures the device, and a fresh password/OTP login is accepted by HA's signed-token verifier. Password alone still requires OTP and code replay is rejected. No configuration changes are made to hosted accounts or the committed realm template.

The required-action page is reached through a legitimate same-origin redirect. The verifier follows at most five redirects and only within the exact identity origin's `/realms/ha/login-actions/` path. It does not follow the HA callback as a page; callback state/destination/code checks remain explicit. OTP secrets/passwords stay in memory and the private disposable identity database, which is removed after the probe; neither appears in reports. A new time period is used before fresh OTP login to avoid reusing the setup code.

Actual Linux HTTPS protocol probe passed with verified hostname/certificate, invalid setup-code rejection, completed setup, fresh signed-token MFA acceptance and replay denial. Six targeted fixture/form/OTP/redirect tests passed. The local identity process stopped afterward. See KEYCLOAK-ENROLLMENT-EVIDENCE.json. Existing connected-session evidence separately covers the rendered pre-enrolled password/OTP workflow; this new enrollment probe does not exercise QR scanning or render the setup screen.

For eventual user onboarding, an authorized identity administrator must assign Configure OTP during account setup as appropriate. Test the actual hosted realm/user provisioning policy before inviting people. The fixture's explicit required action does not establish that all hosted new accounts automatically receive it. Lost-device recovery, account identity verification, recovery messaging, rendered enrollment and hosted behavior remain unverified; do not bypass MFA to recover access.

Primary sources: [Keycloak26.8.0 administration guide](https://www.keycloak.org/docs/26.8.0/server_admin/) and [Keycloak OTP setup template](https://github.com/keycloak/keycloak/blob/26.8.0/themes/src/main/resources/theme/base/login/login-config-totp.ftl). This verifier follows the setup form's totpSecret/totp/userLabel fields without changing its authentication policy.


## Rendered first-time enrollment - October 3

The optional `--rendered-enrollment` extension now passes against actual local Keycloak screens in headless Edge. A separate fictional password-only account reaches visible setup instructions and QR. An incorrect setup code retains the challenge; correct setup completes, cookies are cleared, and a fresh password login requires the newly enrolled OTP. The next-period OTP completes the fresh login. No browser page errors occurred. Eight targeted fixture/parser/OTP tests and the Node RFC6238 six-digit vector passed. Independent review found no remaining important issues.

Identity screens and routes are real. Only the HA callback is intercepted to verify destination, state and code presence; this rendered enrollment check does not create or claim an HA application session. The separate protocol enrollment check in the same successful run verifies signed-token acceptance and authorization-code replay denial. Existing connected-session evidence covers actual HA cookies, books, documents and saved tax inputs. The setup screenshot masks the entire QR/instructions section and code field; secrets, passwords and tokens are not written to reports or browser state.

Initial rendered attempts rejected a fresh code despite matching setup secret and submitted code. Windows and WSL clocks differed by about five seconds. The verifier now receives the Linux fixture timestamp privately through stdin, uses that clock for both codes, waits to the next period midpoint, and asserts an advanced counter and different code. The run passed after consistent timing. Earlier failures did not record server counters, so their precise cause is not conclusively proven. This changes only disposable test timing, not MFA policy or host clocks. TOTP time-step requirements and test vectors: [RFC6238](https://www.rfc-editor.org/rfc/rfc6238.html).

Successful evidence: KEYCLOAK-ENROLLMENT-EVIDENCE.json. The owned identity runtime stopped after the run. Browser acceptance of the self-signed fixture certificate remains explicit; separate protocol checks verify certificate/hostname trust. Scanning with a physical authenticator, hosted default onboarding, lost-device recovery, DigitalOcean/Spaces and filing remain unverified. This entry supersedes the earlier rendered-enrollment-not-run limitation, not those other gates.


## Automatic required enrollment - October 3

The `--automatic-enrollment` verification mode removes the explicitly assigned CONFIGURE_TOTP action from both disposable enrollment accounts. Each account starts with only a fresh password and an empty requiredActions list. The unchanged credential-free HA realm still requires setup during password login: actual protocol and Edge checks passed visible instructions/QR, incorrect setup-code rejection, completed setup, and a fresh password/OTP login. Signed-token acceptance and authorization-code replay rejection pass separately in the same run. No page errors occurred. Nine targeted tests passed; independent review found no actionable issues. The owned identity runtime stopped afterward.

Evidence is KEYCLOAK-AUTOMATIC-ENROLLMENT-EVIDENCE.json, including account_setup_action_preassigned=false and the unchanged realm template hash. The configured REQUIRED OTP execution with userSetupAllowed explains the observed behavior; that mechanism attribution is an inference from configuration and [Keycloak's OTP authenticator source](https://github.com/keycloak/keycloak/blob/26.8.0/services/src/main/java/org/keycloak/authentication/authenticators/browser/OTPFormAuthenticator.java), whose setRequiredActions schedules Configure OTP in the authentication session. The observed required setup itself is actual runtime evidence.

This supersedes the earlier recommendation that an administrator must manually assign Configure OTP for every new account using this imported realm. It does not prove an eventual hosted realm has this configuration, approve account identity or recovery, or exercise a physical authenticator scan. Public self-registration remains disabled; authorized private account provisioning and hosted onboarding must still be checked before invitations. The rendered fixture intercepts only the HA callback and explicitly bypasses trust for its self-signed certificate; actual HA-session evidence remains the separately recorded connected-session workflow. Passwords, secrets and tokens remain absent from reports and saved browser state.

Reproduce locally with the existing Linux fixture dependencies, explicit HA_MFA_BROWSER_NODE and:
`python3 scripts/verify_keycloak_runtime.py --distribution .connected-local/keycloak/keycloak-26.8.0 --realm-file deploy/digitalocean/keycloak/ha-realm.json --mfa-login --otp-enrollment --automatic-enrollment --rendered-enrollment --report docs/KEYCLOAK-AUTOMATIC-ENROLLMENT-EVIDENCE.json`.

October 3 application proxy integration: optional --nginx-proxy requires --connected-session and puts the real HA fixture behind the committed nginx template; direct HTTPS remains the default. Actual password/OTP callback, PostgreSQL16/ClamD/encrypted local document APIs and rendered Bookin/HATax correction/download/save/reopen/logout checks passed through nginx. Proxy inherited logs and watched temporary directories remained empty. Seven targeted Linux checks and independent review passed. Evidence: KEYCLOAK-NGINX-SESSION-EVIDENCE.json; reproduction and explicit self-signed browser trust/provider/activation/recovery limits: NGINX-PROXY-VERIFICATION.md. This fixture uses a pre-enrolled fictional account; automatic enrollment remains proven by its separate earlier fixture.
