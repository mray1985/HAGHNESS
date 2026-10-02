# Linux Droplet deployment draft

Prepared October 2, 2026. Templates only: no provisioned host, live scanner or hosted security/recovery proof. Local Ubuntu systemd-analyze parsed the unit but reported the absent ClamAV service and /opt/ha/venv executable, plus Windows-mounted file permissions; activation validation remains incomplete. nginx and clamconf are not installed in that local environment. These files do not deploy Keycloak or create database, bucket, keys or backups.

Use an Ubuntu/systemd host with a dedicated `ha` service account, a supported Python runtime and virtual environment at `/opt/ha/venv`. Install a reviewed release at `/opt/ha/current`, owned by an administrator and read-only to `ha`. Install the pinned requirements from requirements-connected.txt. The container remains an alternative; this service unit uses a native virtual environment.

Install distribution ClamAV daemon/freshclam packages. Merge the scanner settings with the installed configuration after checking the installed version's sample/manual. Retain its distribution database/user settings. Ensure no TCP listener or conflicting socket activation exposes the scanner. The `clamav` group must traverse the socket directory; the service has this supplementary group. Keep freshclam running and alert on failed/stale signature updates. Startup ordering is not a clean-scan readiness check. Verify actual scanner clean, EICAR, encrypted and size-limit behavior before permitting documents.

Create `/etc/ha/connected.env` from the example with root ownership and mode 0600. Replace all placeholders. Database TLS uses the provider CA and verify-full, with a separate least-privilege runtime role. Configure the live Keycloak realm using docs/KEYCLOAK-IMPLEMENTATION.md; it must require and emit the verified password/OTP claims.

Administer `/etc/ha/keys` independently from source. Its owner must be `ha` and mode 0700 so the non-root service can traverse it. Each `<key-id>.key` must be 32 binary bytes, owned by `ha`, mode 0400. Keep historical keys for authorized old-version reads and independent protected recovery copies. Root-owned 0700 directories would be unreadable by this service. The unit exposes this path read-only; it does not generate keys or establish a key-management service.

Install the unit under `/etc/systemd/system/ha-connected.service`. The unit listens only on 127.0.0.1:8080, uses one process and cannot write application code or key files. Sessions are currently process-local; a restart signs clients out. Do not scale this into multiple application processes yet.

Configure nginx with the chosen domain and publicly trusted certificate, adapting the example. Restrict public ingress to HTTPS and restricted administration; never expose 8080, PostgreSQL or ClamD publicly. Public and environment origins must exactly match. Keep default-server handling and certificate renewal in the site's nginx configuration. Review proxy memory budgets: a request can consume 30 MiB, and the Python server additionally processes decoded bytes. The example disables request-bearing nginx access/error logs; provide separate sanitized health/error monitoring and verify failed-upstream behavior with fictional query values before client use. Avoid plaintext body/error debugging and ensure scanner temporary storage follows the host's protection policy.

Before activation on Linux, run `systemd-analyze verify /etc/systemd/system/ha-connected.service`, `nginx -t` and `clamconf`; fix all diagnostics. Start freshclam/ClamD and verify the protected socket. Start HA, then verify health, real MFA/login/logout, authorized reads/uploads/corrections, unrelated-profile denial, original versions and actual database/object/key recovery with fictional fixtures. Stop activation if any gate fails. Do not paste secrets or diagnostic configuration dumps into chat.

Backups remain a separate unfinished deployment step. Native VM backups do not replace the required retained database/object backups or independent key recovery. Record hosted costs, latency and restore results; these templates are not filing readiness.

Official implementation references:
- [systemd execution options](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)
- [nginx proxy directives](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [ClamAV configuration](https://docs.clamav.net/manual/Usage/Configuration.html)
- [ClamAV sample settings](https://github.com/Cisco-Talos/clamav/blob/main/etc/clamd.conf.sample)
