# Document-shaped tax entry

Status: proposed written specification, following user confirmation of the conversational design on October 1, 2026. Implementation has not started.

## Purpose

Let taxpayers and preparers enter information in the same arrangement they see on their source documents. Search for a form, select a familiar blank layout, and copy values into matching numbered boxes. Imported documents use the same fields after review. Business, rental, and farm information uses guided worksheets with everyday examples.

The first deliverable is manual W-2 and 1099-R entry. Document extraction and Schedule C/E/F worksheets are subsequent deliverables, described here to preserve the agreed direction. Each needs a separate implementation plan before development.

## Existing project and boundary

The local repository currently contains the original Python standard-library server and browser calculator, matching GitHub commit f0e8c64. A newer cloud prototype exists in earlier chat history but its files are unavailable here. This specification targets the local repository; importing that prototype later requires comparing its data model before integration.

Document entry collects source facts. It must not treat wages or retirement distributions as AGI, assume distribution taxability, or mark a complete return ready. Existing calculation and filing limitations remain in force.

## Recommended approach and alternatives

Use HTML form layouts backed by one versioned document schema per form type. Layout choices change presentation, not field meanings. This supports keyboard access, mobile screens, repeatable rows, and shared import/manual validation.

A PDF overlay would resemble an official form closely but makes responsive entry and variable state rows harder. A conversational interview could collect the same facts but does not satisfy the user's primary goal of copying matching boxes. HTML replicas are therefore the recommended first implementation.

## First deliverable: form library and manual entry

Provide a searchable document library with W-2 and 1099-R cards and layout previews. Begin with one faithful standard layout per form and a compact mobile presentation. Add employer/payer layout variants only after checking real examples; do not claim to match every issuer's layout.

Select tax year and document owner (taxpayer or spouse) before entering values. Support years 2023 through 2026 as document metadata even where the existing calculation engine lacks year coverage. Changing owner or year must not silently move entered facts to another return.

Each document has an ID, schema version, form type, tax year, owner, selected layout, source method, review status, and structured fields. Preserve empty versus explicit zero values, identifiers as strings, monetary values as decimal strings, checkbox states, and source box references. Multiple documents of either type are supported.

W-2 fields include employer/employee identity, wage and withholding boxes, Social Security and Medicare amounts, repeatable Box 12 code/amount entries, Box 13 checkboxes, Box 14 label/amount entries, and state/local entries. State records preserve boxes 15–17; local records preserve boxes 18–20 and their associated source row. Allow additional rows without an arbitrary UI count limit, subject to documented request-size bounds. Do not infer that combined state wages equal federal wages.

1099-R fields include payer/recipient identity, gross distribution, taxable amount, taxable-amount-not-determined and total-distribution checkboxes, withholding, employee contributions, distribution codes, IRA/SEP/SIMPLE checkbox, and the remaining applicable numbered boxes for the selected year's form. Support repeatable state/local blocks. Distribution code and checkbox combinations require review; entering the form does not settle rollover, basis, or taxable-income treatment.

Verify each year's box inventory against official IRS forms before implementing its template. Preserve identifiers with leading zeros and mask sensitive identifiers outside active editing.

## Editing and review

Keep source box numbers visible, provide short field help, and enable keyboard navigation. Use a responsive stacked view on narrow screens with the same box labels. Users can add, edit, duplicate, and delete documents; deletion requires a clear local confirmation when values exist. A duplicated document is marked for duplicate review.

Show field errors beside the affected box and in a navigable review summary. Validate syntax and required identifiers without silently correcting source facts. Suspicious arithmetic or unusual combinations produce review items rather than invented values. A blank taxable amount is not automatically zero. Record corrected-document status separately.

The first deliverable keeps data in memory and supports explicit local JSON export/import with schema validation and a warning that backups contain personal information. No automatic browser persistence or unencrypted server storage. Reloading without an export loses unsaved entry; communicate this clearly. Future durable storage requires its own security design.

## Subsequent deliverable: document import

Accept supported PDFs and images, show the source beside matching fields, and retain page/box provenance. Extraction remains local unless a separately approved integration is introduced. Do not present a file viewer as working OCR.

Extracted values are suggestions until reviewed. Unread or uncertain fields remain unresolved, never become zero by default, and prevent document confirmation when required. Detect possible duplicate imports and corrected forms, allowing the preparer to resolve them. Preserve source values and reviewed corrections separately. Apply file size/type limits and prohibit arbitrary file-path access.

## Subsequent deliverable: Schedule C, E, and F worksheets

Create separate activities for each business, rental property, or farm. Use approximately ten expandable navigation groups: supplies; inventory/cost of goods; advertising; labor; premises; utilities; insurance/professional costs; travel/meals; vehicles; equipment/other expenses. These are navigation groups, not ten universal deductible tax lines.

Each activity uses schedule-specific subcategories and plain examples that map to the appropriate tax lines. Include a searchable 'Where does this expense go?' helper and an Other item requiring a description. Distinguish inventory, operating expenses, asset purchases, personal costs, and restricted deductions. Schedule E must distinguish rentals from pass-through K-1 entry; K-1 information belongs in document-shaped entry rather than generic rental expenses.

## Vehicle worksheet

Ask whether the user wants to compare eligible standard mileage with actual expenses. Collect vehicle ownership/lease facts, acquisition and first business-use dates, prior deduction methods, business/total/commuting miles, and dated mileage records where rates change within a year. Collect actual costs and business-use allocation without assuming all driving is business driving.

Display the applicable IRS rate beside its year/date period. Eligibility and prior elections constrain available methods. Mileage must not also deduct fuel, repairs, insurance, or depreciation already covered by that method. Track potentially separate parking/tolls and other eligible items according to verified rules. Comparisons must state their assumptions and distinguish federal from state treatment.

Reference checked October 1, 2026: https://www.irs.gov/tax-professionals/standard-mileage-rates lists 2026 business rates of 72.5 cents for January–June and 76 cents for July–December. Reverify authoritative notices when implementing. Vehicle method rules: https://www.irs.gov/publications/p463.

## Asset and depreciation worksheet

Ask what was purchased, with examples such as a computer, furniture, machinery, vehicle, or building improvement. Collect description, cost/basis, acquisition and placed-in-service dates, business-use percentage, prior depreciation/elections, and asset-specific facts. Retain one asset record across years.

Derive recovery period and permitted methods from verified asset classifications; twenty years is one class, not a universal duration. Present eligible regular depreciation, Section 179, and bonus depreciation with limits and reasons. Do not promise every equipment purchase is immediately deductible. Separate land from depreciable improvements and track federal/state differences, carryovers, dispositions, and potential recapture.

Reference: https://www.irs.gov/publications/p946. Use year-specific authoritative rules when implementing calculations; this design does not certify deduction eligibility.

## Components and data flow

The form catalog selects a year-specific schema and layout. The document editor writes source facts to an isolated document store. Validation produces review items. The review screen confirms document facts; an eventual return adapter consumes only reviewed facts and retains their source references. Imported suggestions pass through the same editor and validator.

Keep catalog/schema definitions, store/export logic, validation, and presentation separate. Use the existing local server to serve static assets; the first deliverable does not require new external services or dependencies. Keep document data out of logs, URLs, chat context, and existing calculation endpoints unless an explicit adapter has been implemented and tested.

## Acceptance criteria for the first deliverable

- Users can find W-2 and 1099-R forms, select owner/year, and enter boxes with visible source numbering.
- Multiple documents, Box 12 entries, state rows, and local rows preserve independent values through editing and export/import.
- Empty/zero distinctions, leading-zero identifiers, checkbox combinations, and monetary precision survive round trips.
- Incorrect-year, duplicate, and distribution-taxability questions remain visible review items rather than automatic tax conclusions.
- Invalid imports fail clearly without partially replacing existing data.
- Keyboard and narrow-screen entry remain usable; field labels and review links are accessible.
- Browser checks cover adding/editing documents, repeated rows, owner isolation, validation, and export/import. Existing Python tests remain passing.
- No automatic persistence, third-party requests, or accidental taxpayer values in logs. No new claim of complete-return or filing readiness.

## Review and implementation handoff

The conversational design was confirmed. Review of this written specification is the next required stage. After approval, write a focused implementation plan for the first deliverable. Later extraction, schedule, vehicle, and depreciation work must keep the same reviewed-source-fact boundaries and receive their own focused plans.
