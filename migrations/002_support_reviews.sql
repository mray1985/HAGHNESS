-- No existing subject receives review authority automatically.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='ha_connected.grants'::regclass
          AND conname='grants_action_check'
          AND pg_get_constraintdef(oid) LIKE '%review_support%'
    ) THEN
        ALTER TABLE ha_connected.grants DROP CONSTRAINT grants_action_check;
        ALTER TABLE ha_connected.grants ADD CONSTRAINT grants_action_check
            CHECK (action IN ('read','post','correct','upload','restore','review_support'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS document_version_scoped_reference
    ON ha_connected.document_versions(profile_id,business_id,tax_year,document_id,version_id);

CREATE TABLE IF NOT EXISTS ha_connected.support_reviews (
    seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    decision_id uuid NOT NULL UNIQUE,
    profile_id text NOT NULL,
    business_id text NOT NULL,
    tax_year integer NOT NULL CHECK (tax_year BETWEEN 2023 AND 2026),
    event_id text NOT NULL,
    event_fingerprint text NOT NULL CHECK (event_fingerprint ~ '^[0-9a-f]{64}$'),
    document_id text,
    version_id text,
    decision text NOT NULL CHECK (decision IN ('accepted','needs_information')),
    reason text NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 2000),
    actor text NOT NULL CHECK (length(btrim(actor)) BETWEEN 1 AND 1000),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    idempotency_key text NOT NULL CHECK (length(btrim(idempotency_key)) BETWEEN 1 AND 128),
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK ((document_id IS NULL) = (version_id IS NULL)),
    UNIQUE (profile_id,business_id,tax_year,idempotency_key),
    FOREIGN KEY (profile_id,business_id,tax_year,event_id)
        REFERENCES ha_connected.ledger_events(profile_id,business_id,tax_year,event_id),
    FOREIGN KEY (profile_id,business_id,tax_year,document_id,version_id)
        REFERENCES ha_connected.document_versions(profile_id,business_id,tax_year,document_id,version_id)
);

CREATE OR REPLACE FUNCTION ha_connected.reject_support_review_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Support review history is append-only' USING ERRCODE='23514';
END $$;
DROP TRIGGER IF EXISTS support_reviews_append_only ON ha_connected.support_reviews;
CREATE TRIGGER support_reviews_append_only BEFORE UPDATE OR DELETE
    ON ha_connected.support_reviews FOR EACH ROW
    EXECUTE FUNCTION ha_connected.reject_support_review_mutation();
