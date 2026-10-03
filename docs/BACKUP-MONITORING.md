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
