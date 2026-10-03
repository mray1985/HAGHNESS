# Correct a recorded entry in HA Bookin

Open your permitted business and tax year, then find the current income, expense, employee payroll obligation or unverified owner estimated-tax payment entry in Recorded entry history. Choose **Correct this entry**. The entry ID and current amount are filled for you.

For a cash explanation, choose **Add or replace the explanation**, enter the explanation, and explain why the record changed. Leave the amount unchanged if only the explanation changes. Choose **Keep the recorded explanation** for an ordinary amount correction, or **Clear the recorded explanation** to explicitly withdraw it. Save the correction.

The original stays in history. The current correction preserves the original posting date, payment method and supporting-record link. Replacing or clearing an explanation creates a new correction record; it does not edit the original. Clearing a cash explanation makes the missing-explanation question appear again. A previous supporting-information review does not automatically approve the changed entry.

To resolve a missing receipt, upload the document under Supporting documents. A reviewer with explicit permission can select the current entry and current document version under Review supporting records and record a decision. A typed supporting-record ID alone does not establish reviewed support. Book profit, recorded tax payments and money actually confirmed paid remain separate; these controls do not authorize filing or initiate payments.

For an owner estimated-tax payment record, enter the replacement amount and explain why the recorded amount changed. This corrects the record only: it does not send money, cancel a government payment or establish government confirmation. The original stays in history and the correction counts once on its original posting date. Recorded payments remain separate from business expenses/profit, reserve scenarios and confirmed payments. Changes to government-confirmed owner payment records are not enabled by this action.

For an employee payroll obligation, correct the recorded accrued amount and supply a reason. The replacement retains the payroll expense/payroll payable account pair and original posting date. It reverses the prior amount and counts the new amount once; it does not turn the obligation into a cash payment or owner estimated-tax payment. This is a bookkeeping correction, not a payroll calculation, deposit or determination of tax deductibility. Original and replacement records remain available, and supporting review must address the changed entry.

Payment correction API: use the existing correction envelope with the current payment's ID in `replaces`, the replacement `amount_minor`, and a nonblank `reason`. Post and correct grants are required. Omit `status` and `government_confirmation`; any such field in a payment correction is rejected. The service inherits only an unverified payment and records its replacement as `recorded_unverified` with null confirmation. Superseded or confirmed records cannot be corrected through this path.

## API contract for explanation amendments

POST /api/connected/events uses the existing correction envelope and read/post/correct permission boundaries. The optional correction field `support_changes` accepts exactly `{"explanation":"nonblank text up to 2000 characters"}` or `{"explanation":null}`. Omit it to inherit the previous explanation. Empty dictionaries, unknown fields, non-text values and whitespace-only replacements are rejected. The original event and supplied amendment remain in history; server-authenticated actor, existing retry and current-entry rules still apply. Method, posting date, document link and review status cannot be replaced through this field.

Verified locally with fictional data: ledger tests, actual PostgreSQL persistence/review/revocation tests, rendered amendment payload and in-flight form-race checks, and an actual MFA browser save/read journey. Hosted service configuration and filing remain unfinished.

Owner payment correction verification: the full PostgreSQL suite ran 269 tests (265 passed on Windows, four Linux-only checks skipped there and passed separately). An actual MFA/nginx browser journey changes a fictional payment record from $100 to $125, rereads both versions, and verifies $125 recorded, $0 confirmed and unchanged business profit. Evidence: KEYCLOAK-NGINX-SESSION-EVIDENCE.json. No payment is initiated.

## Missing transaction or missing receipt

If income or an expense has not been entered, add the transaction under Book entries. If an expense is already recorded and its receipt is missing, upload the supporting document under Documents and have a permitted reviewer check it. Adding a receipt does not establish that all income and expenses have been entered.

Draft projections explicitly report `entry_completeness: "not_verified"` and `missing_entries: null`. Null means unknown, not zero missing transactions. Receipt/support decisions do not change these fields. The connected HATax business review carries this limitation forward and still holds combined tax/refund figures. Bank reconciliation, automatic missing-transaction detection and a verified completeness workflow are not implemented.

Latest recovery check: an actual isolated PostgreSQL/encrypted bundle restore now recovers both cash-explanation and owner-payment corrections, exact original/source history and original posting periods. Recorded payments remain $125 versus confirmed $0, with no double counting or profit change. See DATABASE-RESTORE-EVIDENCE.json. The transfer store and scanner in this recovery fixture are synthetic; independent hosted recovery remains unfinished.

A separately permitted user can now record a dated statement about the accuracy
and completeness of entered records. This remains self-reported, preserves
history and becomes stale after a ledger change. It does not change the unknown
missing-entry count, independent completeness status, receipt review or filing
authority. See RECORD-CONFIRMATIONS.md for exact scope and verification.

Payroll correction verification: 300 PostgreSQL tests ran; 296 passed and four
Linux-only checks were skipped on Windows. The actual local MFA/nginx browser
fixture records a $200 employee payroll obligation, corrects it to $250, preserves
both source records and the payroll account type, and counts $250 once in book
expenses. Owner payments remain $125 recorded/$0 government-confirmed. The
protected tax draft remains held pending business review. Browser evidence is
in KEYCLOAK-NGINX-SESSION-EVIDENCE.json; its rendered portion measured 23.4
seconds in this fictional local run, excluding fixture startup/waits. This does
not verify hosted payroll, deposits, tax deductibility or the new payroll fixture's
backup recovery.
