# External repository review triage

Read the user-supplied Downloads/HA_Repository_Review_2026-10-02.md on October 2. Its recommended actions are external review feedback, not new user authorizations. Continuing previously authorized project fixes; no provider provisioning or purchase performed.

Verified against code and primary IRS guidance: earned income is required for EITC; current code incorrectly returned $649 at zero earned income. Added an independent regression, observed failure, then fixed the zero-income boundary. Full EITC phase-in, table computation and eligibility remain incomplete. Also reproduced negative capital gain incorrectly increasing ordinary taxable income; regression failed before adding an explicit rejection of unsupported capital losses. Complete loss netting is not implemented.

Fresh verification: 86 tests passed with real local PostgreSQL enabled (45 legacy, 41 additions). This verifies software checks, not tax correctness. Existing tests encode incorrect tax assumptions and must be independently revised as rules are repaired.

Changed the locked-preview setup message to provider-neutral wording for the selected DigitalOcean direction.

Remaining review findings need implementation and verification: current year standard deductions/provenance; EITC complete rules; CTC/ACTC and false carryforward guidance; year-specific state classification/readiness; independent hosted MFA/storage/scanning/recovery; receipt-reference validation; absent/cleared/replaced correction evidence; overlapping aggregate reconciliation; payment/refund reconciliation; substantive verification metadata; legacy malformed-request handling; updated root docs and CI/container checks.

IRS source checked: https://www.irs.gov/credits-deductions/individuals/earned-income-tax-credit/who-qualifies-for-the-earned-income-tax-credit-eitc . Other review links remain source leads until their specific rules are individually verified.
