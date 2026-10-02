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


## Actual Linux engine probe

October 2: installed ClamAV 1.5.4 in the existing local Ubuntu test environment and fetched/tested official main, daily and bytecode signature databases. scripts/verify_live_scanner.py launches its own temporary Unix-socket daemon, then terminates it. No application uploads were activated.

Clean text was accepted; EICAR and an encrypted fictional PDF were rejected. The adapter rejected input over 20 MiB and an unavailable socket. The actual socket had mode 0660. However, an expanding ZIP fixture was returned clean despite configured MaxFileSize 25M, MaxScanSize 100M and AlertExceedsMax. Both 26 MiB and 101 MiB zero-filled expansions were probed. The saved latest report explicitly marks verification_passed false; this gate must be investigated rather than treated as passing. ZIP uploads are not an allowed document type, but that fact does not prove embedded-content limit behavior is safe.

See LIVE-SCANNER-EVIDENCE.json. Official project discussion also records scan-limit edge cases: [AlertExceedsMax issue](https://github.com/Cisco-Talos/clamav/issues/633). That discussion is context, not proof of the cause in this run. Expanded-content behavior, malformed samples, production signature freshness monitoring and hosted verification remain open. The local daemon test is stronger evidence than protocol mocks, but does not establish the full document protection policy.


## Additional container metadata control

A project-maintained ha-container-policy.cdb now complements AlertExceedsMax, using ClamAV's [official container metadata signature format](https://docs.clamav.net/manual/Signatures/ContainerMetadata.html). It flags declared expanded member sizes above 25 MiB. It uses a full unsigned 64-bit upper range; no assertion is made that forged metadata or ZIP64 behavior is comprehensively verified.

An isolated database overlay retained official signatures and added only this policy. The nine saved checks in LIVE-SCANNER-POLICY-EVIDENCE.json passed: clean text, EICAR, encrypted PDF, 101 MiB expanded member, exact 25 MiB boundary, 26 MiB member, nested 26 MiB member, adapter input limit and missing socket. The report records the policy hash. LIVE-SCANNER-EVIDENCE.json preserves the failing baseline rather than overwriting it. Independent review found the initial 4 GiB range cap; it was removed and the real-engine run passed again.

This closes the reproduced local member-size case with the additional policy. It does not make a clean verdict a safety guarantee or finish malformed/embedded-format testing, freshness monitoring, hosted integration or runtime activation. Deployment must install and preserve the policy alongside official signatures, verify its hash, and rerun all activation gates.
