# Document-shaped entry implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended here) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build matching source-document entry for the full 1040/1041 recipient-document catalog, starting with a working shared framework and W-2/1099-R slice.

**Architecture:** Browser ES modules own document schemas, validation, memory-only case data, and layouts. The existing Python server serves the entry page; reviewed source facts remain isolated from tax calculations until their adapters are validated. Additional form families extend the registry rather than introduce separate incompatible stores.

**Tech Stack:** Existing Python standard library server, HTML, CSS, browser JavaScript ES modules; Node built-in test runner for pure model tests if available; browser automation for UI verification.

**Spec:** ../specs/2026-10-01-document-entry-design.md (approved by the user).

## Global constraints

- Years 2023 through 2026; distinguish document year from a fiduciary fiscal period.
- Individual and estate/trust cases have separate recipient identities.
- Preserve blank versus zero, decimal strings, leading-zero identifiers, printed box numbers, corrections, and attachments.
- No automatic browser persistence or unencrypted server storage; explicit local JSON export/import only.
- No new external services or dependencies for manual entry.
- Keep taxpayer facts out of logs, URLs, and chat context.
- Repeat state/local rows and coded fields without arbitrary UI count limits.
- Catalogued, manual-entry-supported, extraction-supported, and return-mapping-validated are different statuses.
- Document confirmation does not establish taxable income or filing readiness.

## Review focus

1. Malformed backups must leave the existing workspace unchanged (Task 2).
2. Moving between individual and fiduciary cases must never leak or reassign documents (Tasks 2 and 4).
3. Corrected/consolidated statements must not double count earlier/component records (Tasks 3 and 5).
4. An obsolete form revision must never silently use the current year's fields (Tasks 1 and 5).
5. Source descriptions containing HTML must render as text, including import errors (Task 4).

## Files and interfaces

- `web/documents.html`, `web/documents.css`: standalone document workspace, linked from `web/index.html`.
- `web/documents/catalog.mjs`: `listForms(year, returnType)` and `getSchema(formType, year)`; returns reviewed schemas and explicit coverage statuses.
- `web/documents/model.mjs`: `createWorkspace()`, `createCase(input)`, `createDocument(schema, caseRecord, recipientId)`, `exportWorkspace(workspace)`, `importWorkspace(text)`; pure data functions, no persistence.
- `web/documents/validate.mjs`: `validateDocument(document, schema, caseRecord)` returns `{field, code, severity, message}` issues.
- `web/documents/ui.mjs`: DOM editor, catalog search, repeated groups, case navigation, review, and backup controls.
- `web/documents/schemas/*.json`: year-specific field registries, layout groups, source URLs, supported return contexts, and validation metadata.
- `tests/document-model.test.mjs`: Node model/schema/validation tests with synthetic identifiers only.
- `docs/DOCUMENT-COVERAGE.md`: full form/year/context inventory with implemented status and verified source references.

## Task 1: Verified registry and initial form schemas

- [ ] Inventory the approved families in `docs/DOCUMENT-COVERAGE.md`; record every applicable 2023–2026 revision from IRS/SSA/RRB recipient forms and instructions. Include planned records for all families; do not label them implemented.
- [ ] Write failing catalog tests: `getSchema('W-2', 2025)` exposes boxes 1–20, repeatable boxes 12/14 and state/local groups; `getSchema('1099-R', 2025)` preserves box 2b checkboxes and box 7 codes. `getSchema('unknown', 2025)` and unsupported years raise explicit errors. Confirm year-specific inventories rather than assume all revisions match.
- [ ] Run `node --test tests/document-model.test.mjs`; expect failure before modules exist.
- [ ] Implement `listForms(year:number, returnType:string): Array<FormCoverage>` and `getSchema(formType:string, year:number): Schema` in `catalog.mjs`, with verified W-2/1099-R schemas. Each schema field includes key, box label, type, and layout group; repeat groups include a defined row schema.
- [ ] Run the catalog tests; require passing results and source-review notes. Commit registry/schema slice.

## Task 2: Case/document store and safe backup

- [ ] Add failing tests proving `createDocument` starts monetary fields as empty strings, preserves '0.00' and identifiers beginning with '0', and creates distinct IDs. A 1040 case supports taxpayer/spouse; a 1041 case supports its estate/trust recipient and fiscal period without sharing case data.
- [ ] Add round-trip tests: exported/imported values, rows, ownership and revisions agree. Invalid schema versions, duplicate IDs, invalid case references, oversized inputs (10 MiB maximum), and unknown properties affecting ownership are rejected before mutation. Reject unsafe keys such as `__proto__`.
- [ ] Run the test file and confirm new tests fail.
- [ ] Implement the model signatures above. `importWorkspace(text:string): Workspace` returns a fully validated new workspace or throws; UI replaces its workspace only after success. Reject more than 10,000 documents or rows per backup to bound processing; disclose those technical bounds in backup help.
- [ ] Run tests and commit the model slice.

## Task 3: Source-fact validation and review

- [ ] Add failing tests for invalid monetary strings, recipient/return mismatch, missing year, unknown box codes, blank versus zero taxable amount, suspicious W-2 state totals, and corrected/superseded document links. Unusual values create review issues; they do not overwrite source values. Missing 1099-R taxable amount is unresolved, not zero.
- [ ] Run tests and confirm the new assertions fail.
- [ ] Implement `validateDocument(document:Document, schema:Schema, caseRecord:Case): Array<Issue>`. Separate blocking syntax/ownership errors from review warnings. Add `reviewStatus` and explicit confirmed-facts state without claiming confirmed tax treatment.
- [ ] Run tests, verify no calculation endpoint is invoked, and commit validation slice.

## Task 4: Working matching-form workspace

- [ ] Define browser checks for catalog search, 1040 taxpayer/spouse and 1041 case selection, adding/editing W-2 and 1099-R, three state rows, three locality rows, repeated box codes, document duplication/deletion, masked identifiers, review links, and export/import.
- [ ] Implement `documents.html`, CSS, and `ui.mjs`; add a document-entry link in `index.html`. Render numbered form groups with editable boxes on wide screens and the same labeled fields stacked on mobile. Keep UI renderers driven by schema metadata.
- [ ] Add clear copy: 'Unsaved entries are lost when this page reloads. Export a backup to keep them.' Exports explain that files contain personal information. Use textContent/DOM nodes for user values and no HTML interpolation of untrusted source strings.
- [ ] Run model tests and `python -m unittest discover -s tests -t .`; expect all tests passing.
- [ ] Run browser checks on desktop and 390px width. Verify keyboard access, case isolation, a hostile description such as `<img src=x onerror=alert(1)>` rendering as text, and failed imports preserving current data. Check no external requests or values in server logs.
- [ ] Update README with workspace URL and exact limits; commit working first slice.

## Task 5: Full manual-entry catalog expansion

Execute each family as its own verified schema/UI slice using Tasks 1–4's interfaces. Write failing form-specific tests, implement schemas and repeat groups, run tests/browser checks, and update coverage before committing each family. No family is omitted merely because it is uncommon.

- [ ] Common income: 1099-INT/DIV/NEC/MISC/G and W-2G; tests preserve income character, withholding, and state rows.
- [ ] Benefits/contributions: SSA/RRB statements, remaining retirement and 5498 variants; tests preserve informational status and prevent automatic contribution deductions.
- [ ] Deductions/health: applicable 1098/1095/1097 variants; tests preserve 1095-A monthly rows and distinguish informational coverage records.
- [ ] Investments/equity: 1099-B/DA/OID/CAP, 3921/3922, inherited basis and consolidated statements; tests preserve lots, missing basis, acquisition/sale dates, corrected versions, and duplicate component review.
- [ ] Pass-through/fiduciary: incoming 1065/1120-S/1041 K-1s, relevant K-3s and supplements, grantor letters; tests preserve code/amount pairs, attachments, activity/basis questions, and incoming versus outgoing K-1 direction.
- [ ] Specialist/other: all remaining inventoried 1099/1098 variants, W-2c, 1042-S and supporting statement templates. Tests preserve recipient applicability and corrections, and obsolete-year forms fail explicitly rather than taking current fields.
- [ ] Audit the complete inventory against authoritative catalogs. Every applicable form/year needs source references, complete field entry, context validation and documented routing status before claiming full manual-entry coverage.

## Separate follow-on plans

These approved design areas are not falsely included in manual-entry completion; prepare focused executable plans for each after the shared framework works:

1. Local document viewing/extraction: supported PDF/image formats, uncertain-reading review, page/box provenance, duplicate detection and correction retention. Select an actual local extraction implementation after checking available runtimes; a viewer alone cannot satisfy OCR support.
2. Schedule C/E/F guided worksheets: ten navigation groups with schedule-specific subcategories, inventory/assets/personal separation and examples.
3. Vehicle and asset worksheets: year/date mileage rates, method eligibility/history, allocation, asset classifications, depreciation elections and state differences, checked against applicable authorities.
4. Tax adapters: per-form/year/context source-fact mapping into separately tested 1040 and 1041 engines. Require eligibility, carryovers and fiduciary accounting facts; manual entry alone never enables full return preparation.

## Completion evidence and handoff

- [ ] Mark only implemented tasks complete; record model, Python and browser results and uncovered limitations.
- [ ] Review final coverage report against every spec family and check no support badges overstate extraction or calculation.
- [ ] Save code and documentation in Git. Confirm the remote state before reporting GitHub synchronization; pushing requires the user's authorized scope and any sandbox approval.

Self-review: initial deliverable requirements map to Tasks 1–4. Full catalog expansion maps to Task 5. Import extraction, schedule worksheets, mileage/depreciation and return engines are separate subsystems explicitly assigned follow-on plans, not silently dropped. All five review-focus conditions have owning tests. Execution recommendation: implement directly in this session because the schema, store, validation and renderer share sequential interfaces.
