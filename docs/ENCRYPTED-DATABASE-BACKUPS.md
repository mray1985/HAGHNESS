# Encrypted database backup recovery

October 2, 2026. ha/connected/backup_archive.py adds streaming AES-256-GCM encryption for database dumps. Document ciphertext alone does not protect ledger/profile rows in a database backup.

The archive contains a format header and random nonce prefix, sequential authenticated frames and an authenticated ending. Frame metadata and sequence are authenticated; truncation, altered frames, wrong keys and trailing bytes fail recovery. One-MiB frames bound memory use. Recovery uses a private sibling temporary file and publishes via an atomic hard link only after authentication and fsync; existing destinations are never replaced. Errors remove the temporary file. A crash may leave a private temporary file, which an operator must handle in its protected staging directory. The filesystem must support hard links. This does not authenticate the archive's provenance against someone holding its key.

The key is supplied separately, never stored in the archive. Administrators must maintain private staging-directory permissions, protected historical recovery keys and independent key backups. POSIX temporary files use mode 0600; Windows directory ACLs require separate administrative verification. A decrypted dump is private plaintext and must be handled as such before pg_restore. No routine client can call this module through an API.

The fictional recovery harness now encrypts its pg_dump output and restores from the authenticated decrypted archive. Saved DATABASE-RESTORE-EVIDENCE.json confirms all five tables match, six ledger events, both document versions and cross-profile denials. The harness intentionally retains synthetic plaintext working dump/restore files under ignored .connected-local for diagnostics; it does not prove an operational plaintext-retention policy. Actual client backup tooling must restrict and clean its staging files.

Tests cover multi-frame roundtrip, wrong-key cleanup, tampering, truncation, appended bytes, empty dumps, existing-destination preservation and failed atomic publication. Independent review identified early publication of partial files; the implementation now stages privately before atomic publication.

Hosted backup scheduling, consistent database/object-version inventory, off-host archive copies, 35-day/12-month retention enforcement and hosted recovery remain unfinished. This module is a recoverable encrypted dump primitive, not a complete backup system.
