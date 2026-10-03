# Backup locator monitoring

The operator can check a known private off-host backup locator after loading the existing backup environment through the service's protected configuration mechanism:

```sh
python -m ha.connected.backup_monitor --prefix ha-recovery/KNOWN_32_HEX_PREFIX/ --max-age-hours 36
```

Replace the prefix with the independently recorded successful job locator. The command uses HA_SPACES_REGION, HA_BACKUP_SPACES_BUCKET, HA_BACKUP_SPACES_ACCESS_KEY and HA_BACKUP_SPACES_SECRET_KEY. Prefer a separate read-only backup credential for monitoring. It offers no write or deletion operation. Do not put credentials on the command line.

Exit 0 means a schema-valid private locator is available and at most 36 hours old. Exit 1 means the available locator is stale. Exit 2 means the check could not establish availability, including missing configuration, provider denial, invalid schema or future completion. JSON output reports freshness only. It explicitly reports archive_integrity_verified=false, recovery_verified=false and deletion_authorized=false. The receipt's completion time and copy claim are not cryptographic recovery evidence.

This check is for an explicitly selected locator. It does not discover the newest backup, prove that every scheduled run succeeded, persist a monitoring catalog, send alerts or authorize retention deletion. Those operational controls and actual provider permissions still require implementation/verification. It does not modify the disabled backup timer.

October 2 evidence: 21 targeted monitor/receipt/runner tests passed. Actual isolated PostgreSQL restore with encrypted objects passed, including current/stale checks against a fictional SDK-shaped storage adapter. The whole restore probe measured 8.777 seconds locally; this is not hosted performance. Independent review found no important defects. See DATABASE-RESTORE-EVIDENCE.json.


## Scheduled attempt evidence

The runner emits newline-delimited JSON records with format ha-backup-attempt-v1. Each invocation has a fresh attempt_id shared by its started and terminal completed/failed records. Completion requires the encrypted off-host copy and published/read-back locator to be verified. Records contain UTC timestamps and bounded non-secret counts/locators; they never contain exception details, credentials or document data. Recovery and deletion authority remain false.

The service template explicitly sends stdout/stderr to the systemd journal under ha-backup. Operators can inspect `journalctl -u ha-backup.service --output=cat` and the service exit status. A started record without a terminal record means completion is unknown, including interruption. An older completed record must not hide a newer failed or unfinished attempt. Journal retention, external collection and alert delivery still require provider/operator configuration; the template has not been installed or activated here.

Verification: 23 targeted tests passed. An actual disabled runner invocation emitted started/failed with matching identifiers and exited 1, confirming failure evidence without attempting capture. Hosted successful scheduling is unverified. Output changed from prose to structured JSON; update any external parser before activation.


## Assessing the latest observed attempt

```sh
journalctl -u ha-backup.service --output=cat --since "48 hours ago" --no-pager | python -m ha.connected.backup_attempts
```

Supply an ordered window containing complete attempt records. The reader accepts at most 1 MiB and 2,048 events. Unknown fields, duplicate JSON fields, unmatched/duplicate terminal events, future or out-of-order times fail closed. A truncated window starting with a terminal record is invalid; widen the window to include its start. Mixed non-JSON service messages also cause an invalid window rather than being silently ignored.

The latest observed start determines the attempt being assessed. A newer failure or unfinished attempt overrides an older completed attempt, including when an older overlapping attempt finishes later. Exit 0 means the latest observed attempt reports completion within 36 hours; exit 1 means failed, unfinished, stale or no attempt observed; exit 2 means invalid/unavailable journal evidence. The result describes only the supplied journal window. It does not prove that no newer attempt exists elsewhere, verify the current off-host locator, authenticate archives, grant deletion authority or send alerts. Check locator availability separately.

Actual disabled-runner output piped into this reader reported failed and exited 1. No backup capture or hosted service activation occurred. Targeted tests include late old completions, newer failures, interrupted attempts, stale/empty windows, malformed transitions, duplicate fields, oversize input and sanitized output.


## Discovering the newest observed locator

```sh
python -m ha.connected.backup_monitor --discover --max-age-hours 36
```

This alternative to `--prefix` lists only `ha-recovery/` top-level bundle directories, following `NextContinuationToken` until the provider reports a complete listing. It reads each bounded private receipt and selects the most recent UTC completion time, with prefix as a deterministic tie-breaker. A prefix with `NoSuchKey` for its receipt is an incomplete upload and is counted but not selected. Access denial, malformed/future receipts, inconsistent locators, repeated tokens/prefixes, unexpected root objects or listing errors fail the whole check; an older successful subset is never reported after an incomplete scan. The monitor performs list/get operations only and needs a separate credential permitted to list the backup bucket and read its receipts.

Limits: 100 listing pages, 5,000 distinct bundle directories, 1,000 directories per page, and 64 KiB per receipt. Exceeding a limit exits 2; do not interpret it as fresh backup evidence. Existing 5-second connection and 15-second read timeouts with two total SDK attempts apply to each request. Large inventories can require many sequential reads; this command is an operator tool, not a low-latency application endpoint. No retention or catalog deletion is implemented.

Exit 0 means the newest valid receipt observed during the completed scan is current; exit 1 means stale or `no_locator_observed`; exit 2 means unavailable or invalid discovery. Output includes the selected prefix and observed directory/receipt counts, without keys or client facts. Concurrent uploads may be absent or incomplete during pagination; this is explicitly an observed listing, not an atomic catalog or proof that no newer attempt exists. Continue assessing the latest attempt journal separately. Archive authentication, actual restore, key recovery and external alert delivery remain separate requirements.

Implementation references: [Boto3 ListObjectsV2](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/list_objects_v2.html) for delimiter and continuation semantics, and [DigitalOcean Spaces S3 compatibility](https://docs.digitalocean.com/products/spaces/reference/s3-compatibility/). Boto3 targets the configured DigitalOcean HTTPS endpoint; this does not introduce AWS hosting.

Verification: 34 targeted discovery/monitor/receipt/runner/attempt tests pass. They cover pagination and time ordering, missing completion receipts, invalid schema/time, bounded scans, repeated continuation tokens, provider denial, sanitized CLI failures and no recovery/deletion authority. Actual isolated PostgreSQL backup/restore probe also exercises a paginated fictional object-store inventory with older and incomplete runs. This is local evidence; no live Spaces listing or hosted permissions were tested.
