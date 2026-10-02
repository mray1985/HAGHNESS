# Private DigitalOcean document storage

October 2, 2026. Selected target: DigitalOcean Spaces Standard Storage, client-encrypted documents, private access and API-enabled versioning. The adapter is implemented; no bucket has been provisioned or verified.

## Verified provider contract

[DigitalOcean's compatibility documentation](https://docs.digitalocean.com/products/spaces/reference/s3-compatibility/) documents private ACLs, bucket versioning, time-based lifecycle rules and SSE-C. It does not offer the AWS KMS contract used by the older adapter. [Versioning documentation](https://docs.digitalocean.com/products/spaces/how-to/enable-versioning/) says versioning is disabled by default and must be enabled through the API.

HA uses AES-256-GCM before upload. The external resolver supplies a key by a non-secret key identifier; the envelope contains that identifier and a fresh nonce, never the key. Authentication binds each encrypted object to its bucket, document UUID and key identifier. A copied object in another bucket must be deliberately decrypted and re-encrypted through an authorized recovery process, not read as if it were in the original bucket.

`ha/connected/spaces_storage.py` requests private ACL and generic binary content type, requires a non-null provider version ID, and fetches exactly that version. Reads are size-bounded and close their streams even on failure. Rotating the active key leaves older versions readable only while their historical keys remain recoverable. Loss of a key makes those versions unrecoverable.

Application corrections use new UUID object keys and preserve original metadata. This is application version preservation, not a claim of provider object-lock/WORM enforcement. A storage administrator can still change policies or remove versions; protect administrative access and separate backup credentials.

## Deployment gates

1. Create a private Standard Space with CDN and public listing disabled. Enable versioning through the regional Spaces endpoint. Verify the resulting configuration and unauthenticated read denial with fictional files.
2. Use a dedicated scoped access key and explicitly configured HTTPS regional endpoint with the S3 SDK. API compatibility does not require an AWS account. Do not fall back to ambient AWS credentials or an arbitrary endpoint.
3. Configure a separately administered key service and recovery process. Secrets must not be embedded in application code, database metadata, document storage or GitHub. Check that historical key IDs can be recovered independently of the running app.
4. Wire an actual fail-closed scanner before constructing the runtime Documents service. The present build_server deliberately continues to pass no document service; uploaded taxpayer documents are unavailable until storage, keys and scanning are configured.
5. Verify session/CSRF/scope checks, original and corrected reads, corrupt-object denial and revoked access against the live provider. Then back up complete database metadata and exact encrypted object versions to a separately controlled location and restore a fictional business.
6. Apply the reviewed [retention plan](BACKUP-RETENTION.md) to backup snapshots after recovery and hold checks. Provider lifecycle rules must not indiscriminately expire source originals or held records.

## Evidence and limits

Six injected-client tests verify ciphertext/private uploads, exact versions, original recovery across key rotation, wrong key/corruption/swapped-object denial, invalid inputs, stream bounds/closing, missing keys and cross-bucket denial. Independent review found no important defect. These are adapter tests, not hosted bucket-policy, live provider or scan verification.

The existing isolated encrypted-file/PostgreSQL recovery proof remains useful local evidence. It does not prove a Spaces backup or independent recovery-key service. Hosted provisioning, quote, backup schedule and the complete signed-in client journey remain unfinished.
