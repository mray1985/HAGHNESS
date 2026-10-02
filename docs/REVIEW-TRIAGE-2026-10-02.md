# External repository review triage

Read the user-supplied Downloads/HA_Repository_Review_2026-10-02.md on October 2. Its recommended actions are external review feedback, not new user authorizations. Continuing previously authorized project fixes; no provider provisioning or purchase performed.

Verified against code and primary IRS guidance: earned income is required for EITC; current code incorrectly returned $649 at zero earned income. Added an independent regression, observed failure, then fixed the zero-income boundary. Full EITC phase-in, table computation and eligibility remain incomplete. Also reproduced negative capital gain incorrectly increasing ordinary taxable income; regression failed before adding an explicit rejection of unsupported capital losses. Complete loss netting is not implemented.

Fresh verification: 86 tests passed with real local PostgreSQL enabled (45 legacy, 41 additions). This verifies software checks, not tax correctness. Existing tests encode incorrect tax assumptions and must be independently revised as rules are repaired.

Changed the locked-preview setup message to provider-neutral wording for the selected DigitalOcean direction.

Remaining review findings need implementation and verification: current year standard deductions/provenance; EITC complete rules; CTC/ACTC and false carryforward guidance; year-specific state classification/readiness; independent hosted MFA/storage/scanning/recovery; receipt-reference validation; absent/cleared/replaced correction evidence; overlapping aggregate reconciliation; payment/refund reconciliation; substantive verification metadata; legacy malformed-request handling; updated root docs and CI/container checks.

IRS source checked: https://www.irs.gov/credits-deductions/individuals/earned-income-tax-credit/who-qualifies-for-the-earned-income-tax-credit-eitc . Other review links remain source leads until their specific rules are individually verified.

## EITC phase-in follow-up

Reproduced the $1-earned-income defect with independent tests (12 year/child combinations plus low-earned/high-AGI case), observed failures, then implemented earned-income phase-in at the IRC 32 rates. AGI is used only to limit the credit through phase-out; low AGI does not remove the earned-income phase-in limit.

Corrected 2024–2026 maximums, phase-out starts/ends, statutory phase-out rates and investment-income limits from IRS Rev Proc 2023-34, 2024-40 and 2025-32 section 3.06. Added a reproducible transcription script. The limit is not doubled for joint filers. Boundary tests cover plateau, phase-out and zero-credit ceiling.

The $1/no-child formula scenario is now $0.08 rather than $649. This is **not** an official return-table amount: the IRS EIC table uses income intervals and whole-dollar values. API/UI explicitly label the formula estimate and incomplete eligibility. A mandatory blocker prevents preparation even if unrelated verification flags are changed. Full EIC table lookup, eligibility and independent source review still remain unfinished; do not describe this as filing-ready EITC.

Sources: https://uscode.house.gov/view.xhtml?edition=prelim&req=granuleid%3AUSC-prelim-title26-section32 ; https://www.irs.gov/irb/2023-48_IRB ; https://www.irs.gov/irb/2024-45_IRB ; https://www.irs.gov/irb/2025-45_IRB ; https://www.irs.gov/publications/p1040 .
