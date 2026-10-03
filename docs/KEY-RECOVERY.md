# Document key rotation and recovery

Mounted document keys belong outside the application checkout. Each file is named KEY_ID.key and contains exactly 32 raw bytes. The directory must be private (0700), each key file private (0600), and ownership must satisfy the running service's MountedKeys policy. Symlinks are rejected. The service must actually be able to read the private files; root-only permissions alone do not grant a non-root service access.

A new active key encrypts new document versions. Historical versions retain their original embedded key identifier and require that historical key to decrypt. Rotation does not rewrite originals or corrections. Retaining only the new key loses access to old documents and saved tax inputs. Keep all keys required by live versions and retained backup inventories, including held recovery points. Key destruction requires a separate dependency/custody review; a retention candidate never authorizes key deletion.

Prepare a fresh 256-bit key and an independently protected recovery copy through the operator's chosen key-custody system. Verify recovery of that copy before changing HA_DOCUMENT_ACTIVE_KEY_ID. Keep historical files mounted, apply the new active ID through the protected service environment and restart/reconfigure using the deployment's approved procedure. Current opaque sessions are in memory, so a process restart requires users to sign in again. Verify one new upload and exact reads of both old and new versions. Test recovery on an isolated host from independently retrieved keys and encrypted backups. Record IDs, evidence and custody locations; never record raw keys in Git, documents, logs or chat.

The implementation does not provide an off-site key-custody provider or prove one is available. Copies of keys on the same host are insufficient evidence of disaster recovery. No key was destroyed or hosted service rotated in this checkpoint.

## Local evidence

Run on Linux with the repository dependencies:

```sh
python -m scripts.verify_mounted_key_rotation
```

The ephemeral fixture uses real Linux permission checks, the runtime MountedKeys loader, the SpacesObjects encryption adapter and fictional SDK-shaped versioned storage. It encrypts originals/corrections under separate keys, preserves exact reads after rotation, denies the old version when its key is absent and continues reading the new version. A separately created local recovery directory restores both keys. Exact encoded W-2 original/correction inputs preserve blanks, leading-zero amounts and multiple states. Broad key permissions and symlinks fail closed; plaintext is absent from encrypted objects. Temporary keys are removed with the owned fixture directory.

Actual Linux probe passed; 16 targeted storage/configuration/codec tests passed. Independent review found no important defects or evidence overclaims. KEY-ROTATION-EVIDENCE.json records scope explicitly: fictional storage, no hosted Spaces, external custody unverified, no database/MFA claim in this probe. Existing database/MFA evidence remains separate.
