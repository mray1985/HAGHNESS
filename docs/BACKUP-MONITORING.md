# Backup locator monitoring

The operator can check a known private off-host backup locator after loading the existing backup environment through the service's protected configuration mechanism:

```sh
python -m ha.connected.backup_monitor --prefix ha-recovery/KNOWN_32_HEX_PREFIX/ --max-age-hours 36
```

Replace the prefix with the independently recorded successful job locator. The command uses HA_SPACES_REGION, HA_BACKUP_SPACES_BUCKET, HA_BACKUP_SPACES_ACCESS_KEY and HA_BACKUP_SPACES_SECRET_KEY. Prefer a separate read-only backup credential for monitoring. It offers no write or deletion operation. Do not put credentials on the command line.

Exit 0 means a schema-valid private locator is available and at most 36 hours old. Exit 1 means the available locator is stale. Exit 2 means the check could not establish availability, including missing configuration, provider denial, invalid schema or future completion. JSON output reports freshness only. It explicitly reports archive_integrity_verified=false, recovery_verified=false and deletion_authorized=false. The receipt's completion time and copy claim are not cryptographic recovery evidence.

This check is for an explicitly selected locator. It does not discover the newest backup, prove that every scheduled run succeeded, persist a monitoring catalog, send alerts or authorize retention deletion. Those operational controls and actual provider permissions still require implementation/verification. It does not modify the disabled backup timer.

October 2 evidence: 21 targeted monitor/receipt/runner tests passed. Actual isolated PostgreSQL restore with encrypted objects passed, including current/stale checks against a fictional SDK-shaped storage adapter. The whole restore probe measured 8.777 seconds locally; this is not hosted performance. Independent review found no important defects. See DATABASE-RESTORE-EVIDENCE.json.
