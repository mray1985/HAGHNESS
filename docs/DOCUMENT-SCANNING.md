# Document scanning and runtime configuration

October 2, 2026. ClamD stream adapter and explicit Spaces/runtime wiring implemented. Live engine, signature freshness, Linux permissions and hosted journey are not verified.

## Upload behavior

The existing MFA session authorizes the profile/business/year and upload or correction action before processing. The Documents service validates size/type, then scans bytes before encryption/storage and metadata publication. A rejected or unavailable scan publishes nothing. An exact retry can reuse its previously accepted version; it does not upload new bytes.

The [official ClamD protocol](https://docs.clamav.net/manual/Usage/ClamdProtocol.html) defines INSTREAM length-prefixed chunks and terminated replies. HA sends bounded chunks over a protected local Unix socket. Only one complete `stream: OK` record is accepted. Threats, errors, truncated/multiple replies, connection failures and the overall ten-second deadline fail closed. The adapter creates no plaintext application file; the daemon's temporary-file handling must be configured separately.

[ClamAV scanning documentation](https://docs.clamav.net/manual/Usage/Scanning.html) says TCP traffic is unauthenticated and warns that some size settings skip files as clean. HA's adapter therefore does not offer remote TCP configuration. The daemon must have stream/file limits covering HA's 20 MiB input limit, sufficient total scan limits, alerts for exceeded limits and encrypted/uninspectable documents, PDF/archive scanning enabled, and current signatures maintained with freshclam. Verify actual behavior with clean, EICAR test, encrypted, oversized/expanding and malformed fictional samples before activation. A clean scanner response is not a guarantee that a document is safe or accurate.

## Explicit runtime settings

Without `HA_DOCUMENT_STORAGE`, uploads stay unavailable. The supported configured value is `spaces`, requiring all of:

| Setting | Meaning |
|---|---|
| HA_SPACES_REGION | Regional code, such as nyc3; endpoint is constructed as HTTPS regional Spaces |
| HA_SPACES_BUCKET | Private versioned Standard Space |
| HA_SPACES_ACCESS_KEY / HA_SPACES_SECRET_KEY | Dedicated scoped provider credentials, supplied securely |
| HA_DOCUMENT_KEY_DIRECTORY | Externally administered secret mount outside application code |
| HA_DOCUMENT_ACTIVE_KEY_ID | Non-secret identifier of the active 32-byte binary key |
| HA_CLAMD_SOCKET | Protected absolute Unix socket path |

Each key is a binary file named `<key-id>.key`. Linux requires a directory with no group/other permissions and regular, non-symlink key files with no group/other permissions, owned by root or the runtime user. The runtime must have read access. The active key is checked on startup; historical keys are resolved by ID on read. No keys or credentials belong in GitHub, database metadata or document objects. Independent encrypted key backups and rotation/recovery administration remain necessary. Mounted files are a deployment option; this implementation does not claim a hosted key-management service.

Storage uses explicit Spaces credentials and regional endpoint, with bounded SDK connection/read timeouts and retries. Missing repository/authentication or partial/mixed storage configuration cannot activate uploads. Authorization remains in the same server/session as bookkeeping.

## Hosting implication

The current Unix-socket scanner requires a Linux runtime sharing a protected socket with ClamD. A DigitalOcean Droplet can host the application and daemon as separate managed services, behind HTTPS, while using managed PostgreSQL and Spaces. The existing App Platform container has no scanner/socket/key mount provisioned; its configuration alone does not make private uploads available. Choose and verify this deployment arrangement before enabling document settings; do not expose ClamD's port publicly to bridge that gap.

## Verification limits

Tests exercise framing, fragmented replies, rejection paths, total deadline, no publication after scan failure, explicit configuration, key-file size and POSIX policy simulation, and same-session server wiring. Independent review found no important defect. Windows tests do not establish Linux filesystem permissions or a working ClamAV engine. Actual provider/scanner integration, key recovery, scheduled backups and the signed-in end-to-end journey remain open.
