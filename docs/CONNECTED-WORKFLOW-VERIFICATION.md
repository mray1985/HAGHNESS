# Connected workflow verification

October 2, 2026. Run `.venv/Scripts/python.exe -m scripts.verify_connected_workflow` after the isolated PostgreSQL fixture is configured. The runner rejects nonlocal or nonfixture database settings and creates a new database, preserving existing data.

## Observed behavior

Five fictional trials exercised the actual HTTP API over TLS with certificate and hostname verification, real PostgreSQL transactions and encrypted local document files. One opaque session served books and documents. No second document login occurred in this local fixture.

Each trial posted $1,000 card income, $500 aggregate cash income, $100 supplies and $200 advertising without a receipt. Correcting supplies to $120 changed the book profit from $1,200 to $1,180. The original ledger event remained in history. Retrying the card sale left the revision at six instead of duplicating income.

October, fourth-quarter and annual projections agreed on $1,180; November contained no October entries. The advertising entry remained flagged as missing a receipt. The 25% reserve scenario was $375 of recorded receipts and moved no money. A recorded $100 owner estimated-tax payment remained unconfirmed and did not reduce operating profit or establish government receipt.

An original document and its corrected version were separately retrieved, with the prior-version link preserved. Anonymous access, missing CSRF, access to an existing unrelated profile and access after logout were rejected. The saved JSON report is [CONNECTED-WORKFLOW-EVIDENCE.json](CONNECTED-WORKFLOW-EVIDENCE.json).

## Measured times

The five automated API journeys took 3.2507, 2.2000, 2.4927, 2.2277 and 2.6166 seconds in this run. The observed median was 2.4927 seconds; nearest-rank p95 was 3.2507 seconds. Five local samples are limited evidence, not a capacity study or public performance promise. Database/certificate/fixture setup, human entry, hosted login and financial settlement are outside this measurement.

## What this does not prove

Identity uses a locally signed token with the required MFA claims; it does not exercise an actual Keycloak realm, OTP interaction or hosted OAuth exchange. Scanning is an explicit synthetic bypass; the ClamAV adapter and daemon must be verified separately. Storage is encrypted local files, not a live Spaces bucket. TLS trusts the generated local certificate only for this loopback test.

This proves the combined local book/document projection path under those conditions. It does not establish a complete 1040/1041 tax calculation, official PDF mapping, filing authorization, actual bank reserve transfer, IRS payment, provider recovery or the production browser journey. The full Day 8 goal remains open.

Independent review found no important verifier defect. Two guardrail tests ensure that nonfixture databases and incorrect draft/payment/filing results cannot be accepted by the runner.
