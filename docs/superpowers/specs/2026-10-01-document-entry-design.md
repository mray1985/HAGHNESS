# Document-shaped tax entry

Status: proposed written specification, following user confirmation of the conversational design on October 1, 2026. Implementation has not started.

## Purpose

Let taxpayers and preparers enter information in the same arrangement they see on their source documents. Search for a form, select a familiar blank layout, and copy values into matching numbered boxes. Imported documents use the same fields after review. Business, rental, and farm information uses guided worksheets with everyday examples.

The requested scope is all recipient tax documents and supporting statements mailed or electronically delivered for preparation of Form 1040 or Form 1041, for 2023 through 2026. W-2 and 1099-R are the first implementation slice, not the scope limit. Document extraction and Schedule C/E/F worksheets are subsequent deliverables. Each implementation slice needs a focused plan before development.

## Full document catalog and coverage

## Guided simple-return journey (October 2 clarification)

Optimize a single individual with one W-2 for a measured under-ten-minute completion target when documents are ready, supported calculations are complete, and identity/payment integrations succeed. Do not promise every return takes ten minutes or that a signature means IRS acceptance.

1. Client identity: full legal name, complete address, SSN/ITIN, date of birth, and required filing/dependency/residency facts. Existing client facts are prefilled for confirmation. Ask only relevant follow-up questions, preserving current-year verification.
2. Form selection: a top progress/tab strip with Identity, Documents, State, Review, Payment, Money, and Sign/Submit. Show 'Click your form' and smaller help text 'Forms are in alphabetical order, then numerical order where needed.' Use natural numeric sorting (Schedule 1, 2, 3, 10) within an alphabetical family. Tabs preserve work and show incomplete steps; later steps cannot bypass unmet prerequisites. Include 'I have entered all my documents' rather than assume the first W-2 is the entire return.
3. Form confirmation, before layout selection: 'You chose W-2. If that is correct, click Continue.' Allow changing selection.
4. Layout selection: 'Which one looks like yours?' Show actual verified layout previews. Provide a standard-layout fallback; issuer variants remain conditional on reviewed examples.
5. Matching entry: 'Put the numbers and information in exactly the same.' Display source box numbers, prefill confirmed matching identity facts, and show a persistent live federal/state estimate beside entry. Missing or invalid facts visibly make the estimate incomplete; review withholding help is optional and does not interrupt entry repeatedly.
6. State: 'Verify your state.' Then 'We need to run through your state because your state requires a few different things.' Use plain-language questions selected by residency, move dates, work locations, withholding and applicable state rules; state rows on a W-2 are not sufficient to establish residency or all filing obligations.
7. Review: show documents included, missing-data questions, federal/state results, fees and official return preview before payment/signature. A simple case should remain concise without skipping eligibility facts.
8. Preparation payment: straightforward price and payment options. The user's requested refund-transfer option charges the client no additional transfer fee; it requires an integrated provider whose fees are covered by the business or a verified zero-fee arrangement. Do not display that option as available until the arrangement exists. Distinguish a preparation fee paid from the refund from tax payments to government. Explain what happens if the refund is delayed, reduced or offset, and never promise faster IRS processing.
9. Money destination: refund users can select verified direct-deposit destinations and, where supported, eligible refund splits. Offer a Charles Schwab traditional/Roth IRA path only with confirmed account funding instructions, contribution eligibility, limits, contribution year and deadline. Account opening requires a real provider flow. Depositing cash into an IRA does not purchase investments; investment selection needs separate consent. Recalculate if a confirmed deductible traditional IRA contribution changes the return; re-review after any material change. Preserve state refund handling separately.
10. Balance due: present government payment options with amount/date and authorization, separate from preparation payment. Filing acceptance does not prove tax payment settled. Optional withholding planning addresses future paychecks and does not erase the current balance.
11. Verification and signature: relevant identity verification, anti-bot challenge, informed review and authorized e-signature. Security questions/CAPTCHA alone are not a sufficient identity proof. Required provider/transmitter authentication and signature rules determine the production steps. Any material return change invalidates prior review/signature.
12. Submission and outcome: after signing, show queued/submitted/accepted/rejected status separately, with receipts and downloadable official return copies when authorized. Provide actionable rejection recovery. A paper-filing choice clearly says the signed package must be mailed; downloading it is not filing it.

Scope sequencing remains full document coverage, with the one-W-2 journey as the first complete UX scenario. Payments, refund transfers, account funding, authentication, signatures and e-file are real integration work, not simulated success screens.

Repository check on October 2: GitHub main remains f0e8c64, original calculator. Local main includes e4d75e1 design commit plus uncommitted design/plan updates. No matching-form implementation exists yet. Legacy knowledge cards contain materially incorrect credit explanations (including child-tax-credit refundability/carryforward); independently validate and correct rules, cards and tests before using them for live guidance. Passing the existing tests alone is not proof of tax-law accuracy.

Money-flow references: https://www.irs.gov/refunds/frequently-asked-questions-about-splitting-federal-income-tax-refunds, https://www.irs.gov/pub/irs-pdf/f8888.pdf, https://www.irs.gov/irm/part21/irm_21-004-001r and https://www.schwab.com/ira. Provider-specific refund-to-IRA support and zero-extra-charge refund transfers remain unconfigured.

Maintain a versioned inventory for each year with official form name, revision, source instructions, applicable recipient/return types, numbered fields, attachments, layout variants, validation, and destination mapping. Distinguish catalogued, manual-entry-supported, extraction-supported, and return-mapping-validated states. A searchable placeholder is not supported entry. Forms discontinued or introduced during these years appear only for applicable years. Unrecognized statements can be attached and described for preparer review, without claiming automatic tax mapping.

Required families to inventory and implement:

- Employment and benefits: W-2, W-2c, W-2G, SSA-1099/SSA-1042S, RRB-1099/RRB-1099-R, and 1042-S where applicable to the recipient return.
- Form 1099 family: A, B, C, CAP, DA, DIV, G, H (applicable historical years), INT, K, LS, LTC, MISC, NEC, OID, PATR, Q, QA, R, S, SA, and SB; retain a year-specific inventory to capture additional or revised variants.
- Deduction/education statements: 1098, 1098-C, 1098-E, 1098-F, 1098-Q, and 1098-T; 1097-BTC.
- Health coverage: 1095-A, 1095-B, and 1095-C. Distinguish reconciliation inputs from supporting/informational records.
- Contribution and account statements: 5498, 5498-ESA, 5498-QA, and 5498-SA. Prevent reported contributions or rollovers from automatically becoming deductible amounts.
- Pass-through documents: Schedule K-1 for Forms 1065, 1120-S, and 1041; associated K-3s and supplemental statements where relevant. Preserve activity, codes, footnotes, basis, and carryover questions.
- Equity and inherited basis: 3921, 3922, Schedule A (Form 8971), brokerage cost-basis and supplemental statements, and inherited-property basis records.
- Consolidated broker statements: separate component 1099s, transaction lots, covered/noncovered status, basis adjustments, withholding, and corrected statement versions. Prevent duplicate entry of both a consolidated statement and its component forms.
- Supporting mailed documents: mortgage/property-tax statements, charitable acknowledgments, tuition/payment statements, estimated-payment records, foreign income/withholding statements, grantor-trust tax letters, and nominee statements. Use issuer-specific layouts or guided statement entry when there is no universal IRS box layout.

Inventory references checked October 1, 2026: https://www.irs.gov/filing/e-file-information-returns and https://www.irs.gov/businesses/small-businesses-self-employed/a-guide-to-information-returns. These establish form families, not universal applicability to every 1040 or 1041. Verify applicability using each year's recipient instructions.

## Individual and fiduciary return contexts

Select return type before assigning documents. A 1040 case assigns documents to taxpayer or spouse. A 1041 case assigns documents to the estate/trust EIN and preserves entity type, tax-period start/end, fiduciary identity, and beneficiary records. Document calendar year and fiduciary fiscal period are separate facts. Mismatched recipient IDs, decedent-versus-estate ownership, and period allocation require review; never simply move a decedent's personal W-2 into estate income.

For 1041, retain income character, principal/income accounting distinctions, grantor reporting treatment, tax-exempt income, distributions, and beneficiary allocation facts needed by a future fiduciary engine. An incoming K-1 is a source document; beneficiary K-1s generated by this return are outputs. Do not confuse them or assume all estate/trust income belongs to beneficiaries. Completing a matching input form does not implement distributable net income or a complete 1041 calculation.

Fiduciary reference: https://www.irs.gov/instructions/i1041. Beneficiary recipient reference: https://www.irs.gov/instructions/i1041sk1. The return adapter must apply the appropriate year-specific instructions rather than route every statement directly to a taxable-income line.

## Existing project and boundary

The local repository currently contains the original Python standard-library server and browser calculator, matching GitHub commit f0e8c64. A newer cloud prototype exists in earlier chat history but its files are unavailable here. This specification targets the local repository; importing that prototype later requires comparing its data model before integration.

Document entry collects source facts. It must not treat wages or retirement distributions as AGI, assume distribution taxability, or mark a complete return ready. Existing calculation and filing limitations remain in force.

## Recommended approach and alternatives

Use HTML form layouts backed by one versioned document schema per form type. Layout choices change presentation, not field meanings. This supports keyboard access, mobile screens, repeatable rows, and shared import/manual validation.

A PDF overlay would resemble an official form closely but makes responsive entry and variable state rows harder. A conversational interview could collect the same facts but does not satisfy the user's primary goal of copying matching boxes. HTML replicas are therefore the recommended first implementation.

## First deliverable: form library and manual entry

Provide a searchable document library with W-2 and 1099-R cards and layout previews. Begin with one faithful standard layout per form and a compact mobile presentation. Add employer/payer layout variants only after checking real examples; do not claim to match every issuer's layout.

Select tax year, return case, and recipient before entering values, using the individual/fiduciary ownership rules above. Support years 2023 through 2026 as document metadata even where the existing calculation engine lacks year coverage. Changing recipient or year must not silently move entered facts to another return.

Each document has an ID, schema version, form type/revision, document year, return-case ID, recipient ID, selected layout, source method, review status, corrected/superseded relationships, supplemental attachments, and structured fields. Preserve empty versus explicit zero values, identifiers as strings, monetary values as decimal strings, checkbox states, and source box references. Multiple documents of each type are supported.

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

## Live estimates, official PDFs, and withholding planning

User additions: map reviewed calculations into the appropriate year-specific official IRS return PDFs and schedules, and update a running refund/balance estimate as document fields change after initial client facts are entered. Use one calculation snapshot for both visible totals and PDF field mapping. Invalidate stale results immediately when inputs change; do not display a previous calculation as current. Recalculate after valid edits with a short debounce. Preserve incomplete input and show unresolved questions instead of fabricating values.

Show federal and each applicable state's estimate separately, with 'Based on documents entered so far' and missing-data indicators. Prior-year client information is a starting point requiring current-year confirmation, not silently reused current income, credits, or payments. Unsupported calculation paths produce an unavailable/incomplete estimate. A 1041 estimate requires a fiduciary engine rather than the individual engine. Print-ready PDF release requires complete reviewed calculations and verified year/form field mappings, rendered and checked against the official pages.

When a partial estimate shows tax due, offer a withholding checkup without treating it as a final shortfall or immediately changing payroll elections. Separate the return being prepared from future-year planning. Ask pay frequency, remaining pay dates, latest paystub gross/taxable pay and federal withholding, year-to-date wages/withholding, expected changes, spouse/other jobs, other income, deductions, credits, estimated payments, and current W-4 entries. Prior W-2s may seed a clearly labeled historical scenario but cannot alone support an accurate current payroll recommendation.

Calculate additional withholding per paycheck as max(0, projected annual tax + chosen refund target - projected annual payments) divided by remaining paychecks assigned to the chosen job; projected payments include withholding already made and future baseline withholding, avoiding double counting an existing extra amount. Offer a next-full-year scenario separately. Reject zero remaining paychecks and suggest a different payment/planning path. Payroll baseline calculations use the applicable year's Publication 15-T and actual W-4 settings.

Do not automatically instruct a married taxpayer to select Single. W-4 is an official signed certificate, not an arbitrary withholding control. Current W-4s no longer use allowances; Step 3 uses credit amounts, not the old 'claim zero' allowance count. Eligible credits may be left out for higher withholding, but distinguish that election from claiming the taxpayer has no dependents on their return. Use truthful status and the applicable multiple-job guidance; Step 4(c) specifies additional dollars per paycheck.

Allow optional user-selected 3%–10% cushions as scenarios, explicitly defined as a percentage of gross pay and converted to dollars per paycheck. Do not present those percentages as IRS-required or universally sufficient. Show the effect on take-home pay and projected refund/balance; a target-based amount is the primary recommendation. Recheck after payroll implements changes. W-4 guidance applies to wage recipients, not automatically to an estate/trust or pension recipient; pension planning may require W-4P/W-4R.

References checked October 2, 2026: https://www.irs.gov/publications/p15t, https://www.irs.gov/publications/p505, https://www.irs.gov/individuals/tax-withholding-estimator-faqs, and https://www.irs.gov/pub/irs-pdf/fw4.pdf. These additions require focused calculation/PDF/withholding plans and meaningful regression cases before implementation.

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

The conversational design was confirmed and the user expanded the scope to all relevant mailed documents for 1040 and 1041. Review of this revised written specification is the next required stage. After approval, write the initial implementation plan and a coverage-driven sequence for the entire catalog: shared document framework and W-2/1099-R; common income statements; deductions/health/contributions; investment lots and consolidated statements; K-1/K-3 and fiduciary statements; specialist and supporting records. This sequence is delivery order, not permission to omit less common documents.

Full-scope acceptance requires every inventoried applicable form/year to have reviewed fields, source references, manual-entry validation, and documented return-routing behavior. Track incomplete extraction and calculation support separately and visibly. Later extraction, schedule, vehicle, and depreciation work must keep the same reviewed-source-fact boundaries and receive their own focused plans.
