# Simplified HATax tools and payment flow

Research checked against platform-owned documentation on October 3, 2026. This describes public workflows, not access to competitors' private algorithms. HATax implementation choices below are our design, not claims about their internals.

| Platform | Public pattern | HATax simplification |
| --- | --- | --- |
| TurboTax | Tax Tools / Tools / Delete a form; mailed documents can be removed from their summary. Form 1040 itself cannot be deleted. | Open Tax tools inside the draft; review or remove the selected source document, with confirmation. |
| Intuit ProConnect | Whole-return or partial PDF printing; payment or purchased-return balance may be required. | One Print/download action, then choose the completed return or a specific generated form. |
| H&R Block | Preparation payment and refund delivery have separate options. Refund Transfer collects preparation fees from the refund; fees apply. | Separate “Pay for preparation” from “Receive my refund” and “Pay my tax balance.” |
| FreeTaxUSA | Free self-printed PDF; optional paid services. Card payment and refund transfer are separate choices. Refund transfer involves a banking partner, consent and eligibility. | Show total preparation price and optional transfer charge before the choice; explain what reaches the customer. |
| TaxSlayer | Print/view PDF and filing link to payment; a third-party bank handles pay-with-refund, requiring sufficient refund to cover charges. | Keep fees visible and do not offer transfer if eligibility or available funds are unverified. |

## Implemented checkpoint

The main return has an in-page Tax tools button. It does not navigate away or discard the draft. Review opens the existing matching document. Remove names the form, asks for confirmation and recalculates the estimate. Old saved versions are not erased. The standalone /tools.html is now a simple entry point; the older tax-rule workspace is preserved at /reference.html.

Review flags currently check missing employer/payer and recipient information, tax ID formats and profile mismatches, missing income, invalid dollar amounts, incomplete state labels, unanswered interest special-treatment questions, and server-reported tax-review reasons. Optional blank boxes are not all required. Every form retains a tax-treatment/filing-review flag because this preview has incomplete rules. These checks do not establish compliance, independently verify a TIN, validate every form or implement generated schedules.

Print remains disabled with a reason. No client-side paid checkbox, localStorage purchase flag, fake checkout, payment transmission or official IRS PDF is introduced.

## Payment implementation contract for the next subsystem

Use integer cents for all quoted service prices and charges. Compute service total = preparation items + explicitly selected extras - valid discounts + applicable service taxes. Compute refund delivered = actual refund received by the authorized banking provider - outstanding authorized fees. Do not treat a draft estimate as guaranteed funds. Do not combine federal and state refunds for eligibility unless the provider's agreement supports it. A fee must not be collected twice if more than one refund arrives.

Maintain separate states for the preparation order, payment, refund-transfer agreement, return export, filing submission and government payment. A paid preparation order does not prove that taxes were paid or a return accepted. Print authorization must be checked on the server against the entitled return/version and the completed export artifact. Required preparation payment can be zero under an approved free/waived order; never infer eligibility from a browser flag.

Provider-confirmed payment events need signature verification, an immutable event history, unique provider-event IDs and idempotent processing. Timeouts must keep the same order and allow status lookup before retrying a charge. Refunds, reversed payments and failed/returned transfers need explicit states and receipts. Return edits require revalidation and a newly identified export version; do not silently change an already authorized filing or payment.

For government tax balances, offer the supported government/provider method separately and disclose any processor fee. IRS Direct Pay is a bank-account option; card payments use third-party processors. Actual integrations, provider agreements and operational recovery remain pending. The requested no-extra-charge refund transfer can be a product policy only once the banking terms and the funding of any provider charge are settled; it is not available in this preview.

## Sources

- [TurboTax form deletion](https://ttlc.intuit.com/turbotax-support/en-us/help-article/tax-forms/view-delete-forms-turbotax-online/L7SZhwCHv_US_en_US)
- [ProConnect PDF and print](https://accountants.intuit.com/support/en-us/help-article/print-file/print-return-proconnect-tax/L2XKsTdoI_US_en_US)
- [H&R Block refund and preparation payment](https://www.hrblock.com/tax-offices/tax-refund-payment/)
- [FreeTaxUSA prices and printing](https://www.freetaxusa.com/pricing/)
- [FreeTaxUSA refund-transfer workflow](https://community.freetaxusa.com/kb/articles/315-pay-your-tax-preparation-fees-with-your-refund)
- [TaxSlayer pay with refund](https://support.taxslayer.com/hc/en-us/articles/360015710252-How-can-I-Pay-for-my-E-file-Using-my-Refund)
- [TaxSlayer print/payment policy](https://www.taxslayer.com/policies/refund)
- [IRS Direct Pay](https://www.irs.gov/payments/direct-pay-with-bank-account)
- [IRS card processors](https://www.irs.gov/payments/pay-your-taxes-by-debit-or-credit-card)

TaxMCP was queried for interest/Schedule B research. Its result returned IRC reporting/backup-withholding sections rather than the requested Schedule B guidance; those results were not used as a substitute for current IRS 1040/1099-INT instructions. Taxiger Doc documents Belgian taxi regulation and is outside this U.S. tax-return scope.

## Local evidence

The real-HTTP rendered browser check verifies mixed W-2/interest estimates, review holds, layout changes, two state rows, form review, removal cancellation/confirmation, recalculation, disabled printing and 390px fit. The local real-MFA verifier passed encrypted interest save/reload/reopen. Full PostgreSQL suite at the interest checkpoint: 306 ran, 302 passed, four Linux-only skips. The final tools changes have additional targeted browser verification; hosted money and filing operations remain untested and inactive.
