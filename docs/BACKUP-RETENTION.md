# Backup retention controls

October 2, 2026. Implemented planning policy; hosted scheduling and enforcement remain unconfigured.

Keep every snapshot from the last 35 days, including the exact boundary. Keep the newest snapshot in each of the current and previous eleven UTC calendar months. Always keep the latest available snapshot, even if older, and every snapshot with an explicit hold.

This policy concerns backup snapshots only. It does not delete original documents, corrections, ledger entries, keys or audit records. Monthly backups must include the database and matching immutable document inventory; a database dump alone is not a complete document recovery point.

An operator can supply an inventory of objects containing `snapshot_id`, timezone-aware ISO `created_at`, and boolean `held`, then run:

```powershell
.venv/Scripts/python.exe -m scripts.plan_backup_retention inventory.json
```

The command prints retained IDs and expiry candidates. It cannot delete or authorize deletion. Invalid IDs, duplicates, future timestamps, naive timestamps and non-boolean hold flags fail validation. Normalize all calendar buckets to UTC.

Before activating hosted expiry, verify a complete recent restore with the separately managed recovery key, validate inventory completeness and provider version IDs, apply legal/operational holds, review candidates, and preserve an auditable deletion record. Retention cannot substitute for cross-provider recovery or key availability. Actual hosted storage lifecycle behavior needs provider-specific tests.

Four focused tests cover daily/monthly/latest retention, hold protection, malformed inventory and the twelve-month UTC boundary. The existing isolated PostgreSQL suite passed with 129 tests before the fourth focused case was added; that case then passed separately. Independent review found no important planner defect.
