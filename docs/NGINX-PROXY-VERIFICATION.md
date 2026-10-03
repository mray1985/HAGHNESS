# Local nginx proxy verification

October 3, 2026. Actual nginx 1.24.0 (Ubuntu), loopback only, fictional upstream and disposable certificate/key/files. No provider resources were created. The fixture changes only fixed template locators; proxy body, buffering, TLS and logging policies remain those in the deployment template. The wrapper deliberately enables inherited logs to detect missing server-level privacy settings.

The baseline HTTP redirect recorded a fictional callback/query marker through inherited access logging. Both HTTP and HTTPS server blocks now explicitly disable request-bearing access/error logs. After this fix, two focused unit tests and the actual local probe passed.

The probe checks certificate and hostname verification using an explicitly trusted ephemeral certificate, exact 308 redirect, callback location/cookie preservation, exact length and SHA-256 of fixed-length and chunked 27 MiB uploads and a 27 MiB response, 31 MiB rejection before upstream, forwarded host/protocol, and a 502 after upstream shutdown. Linux inotify watches all configured temporary directories for create/write events, including files removed before final inspection. Covered requests produced no such events or inherited request logs. Owned services stop and temporary files are removed after the run.

Run from the repository root on Linux with Python requirements and a reviewed nginx executable available:

```sh
python3 scripts/verify_nginx_proxy.py --nginx /path/to/nginx --report docs/NGINX-PROXY-EVIDENCE.json
python3 -m unittest tests.test_nginx_proxy_probe
```

The saved report includes the SHA-256 of the template used. The local distribution package was unpacked under ignored `.connected-local/nginx`; no system nginx service was installed or started. These checks cover the specified synthetic requests, not every traffic pattern or resource-exhaustion condition. The application, MFA and private storage are not exercised through this proxy fixture. Hosted ingress, publicly trusted certificates/renewal, native service activation, sanitized operational monitoring and recovery still need verification.

Primary references: [nginx request buffering](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_request_buffering), [response buffering](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering), and [client body buffering](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_body_buffer_size). The template uses HTTP/1.1 to the upstream, including the chunked request path.

## Real connected application mode

The existing Keycloak session verifier accepts optional `--nginx-proxy /path/to/nginx`. This requires `--connected-session` and retains the unchanged direct HTTPS default when omitted. In proxy mode HA listens on an ephemeral loopback HTTP port; nginx terminates HTTPS on the fixture's existing callback origin at port 8844. The fixture copies its certificate/key into a separate disposable proxy directory, keeps the committed proxy policy and checks inherited logs and temporary-file activity after the application journey. Publicly reachable HTTP upstreams are not introduced.

With the established local PostgreSQL16, ClamD, Python, Keycloak and optional Windows Edge/Node fixture dependencies:

```sh
python3 scripts/verify_keycloak_runtime.py --distribution .connected-local/keycloak/keycloak-26.8.0 --realm-file deploy/digitalocean/keycloak/ha-realm.json --mfa-login --connected-session --nginx-proxy .connected-local/nginx/runtime/usr/sbin/nginx --report docs/KEYCLOAK-NGINX-SESSION-EVIDENCE.json
```

Set the existing `HA_MFA_BROWSER_NODE` environment variable to the Windows Node executable to include the rendered browser journey; otherwise the report explicitly records it as not run. Python HTTPS requests verify the trusted fixture certificate and hostname. The local browser fixture explicitly tolerates its self-signed certificate; this does not prove browser trust for a hosted certificate. The upstream uses real HA, PostgreSQL and ClamD with AES-GCM encrypted local objects; Spaces, hosted identity, native service activation and operational recovery remain outside this fixture.

October 3 result: the actual composed proxy run passed, including the rendered password/OTP callback, permitted case choice, receipt downloads, cash explanation correction/persistence, Bookin period totals, HATax draft save/reload/reopen, unrelated-scope clearing and logout denial. API checks separately pass original/correction preservation, CSRF and edit-grant denial, EICAR rejection without publishing, active-session revocation and callback replay rejection. Book profit remains $1,180 and the refund/balance estimate remains held pending business tax review. Proxy temporary create/write events were absent, inherited logs empty and the owned proxy stopped. Seven targeted Linux tests passed; independent code review found no important issues. Browser portion measured 7.6 seconds in one fictional local run, excluding startup and fixture waits, not customer completion timing. Full suite was not rerun for this verifier-only change. Evidence: KEYCLOAK-NGINX-SESSION-EVIDENCE.json.
