# Correct a recorded entry in HA Bookin

Open your permitted business and tax year, then find the current income or expense entry in Recorded entry history. Choose **Correct this entry**. The entry ID and current amount are filled for you.

For a cash explanation, choose **Add or replace the explanation**, enter the explanation, and explain why the record changed. Leave the amount unchanged if only the explanation changes. Choose **Keep the recorded explanation** for an ordinary amount correction, or **Clear the recorded explanation** to explicitly withdraw it. Save the correction.

The original stays in history. The current correction preserves the original posting date, payment method and supporting-record link. Replacing or clearing an explanation creates a new correction record; it does not edit the original. Clearing a cash explanation makes the missing-explanation question appear again. A previous supporting-information review does not automatically approve the changed entry.

To resolve a missing receipt, upload the document under Supporting documents. A reviewer with explicit permission can select the current entry and current document version under Review supporting records and record a decision. A typed supporting-record ID alone does not establish reviewed support. Book profit, recorded tax payments and money actually confirmed paid remain separate; these controls do not authorize filing or initiate payments.

## API contract for explanation amendments

POST /api/connected/events uses the existing correction envelope and read/post/correct permission boundaries. The optional correction field `support_changes` accepts exactly `{"explanation":"nonblank text up to 2000 characters"}` or `{"explanation":null}`. Omit it to inherit the previous explanation. Empty dictionaries, unknown fields, non-text values and whitespace-only replacements are rejected. The original event and supplied amendment remain in history; server-authenticated actor, existing retry and current-entry rules still apply. Method, posting date, document link and review status cannot be replaced through this field.

Verified locally with fictional data: ledger tests, actual PostgreSQL persistence/review/revocation tests, rendered amendment payload and in-flight form-race checks, and an actual MFA browser save/read journey. Hosted service configuration and filing remain unfinished.
