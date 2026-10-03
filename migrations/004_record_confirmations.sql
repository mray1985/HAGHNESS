-- Explicit authority only; existing users receive no new grants.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
        WHERE conrelid='ha_connected.grants'::regclass AND conname='grants_action_check'
          AND pg_get_constraintdef(oid) LIKE '%confirm_records%') THEN
        ALTER TABLE ha_connected.grants DROP CONSTRAINT grants_action_check;
        ALTER TABLE ha_connected.grants ADD CONSTRAINT grants_action_check
            CHECK (action IN ('read','post','correct','upload','restore','review_support','save_tax','confirm_records'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS ha_connected.record_confirmations (
    seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    confirmation_id uuid NOT NULL UNIQUE,
    profile_id text NOT NULL,
    business_id text NOT NULL,
    tax_year integer NOT NULL CHECK (tax_year BETWEEN 2023 AND 2026),
    ledger_revision bigint NOT NULL CHECK (ledger_revision >= 0),
    ledger_fingerprint text NOT NULL CHECK (ledger_fingerprint ~ '^[0-9a-f]{64}$'),
    reviewed_through date NOT NULL,
    statement_version text NOT NULL CHECK (statement_version='records-v1'),
    reason text NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 2000),
    actor text NOT NULL CHECK (length(btrim(actor)) BETWEEN 1 AND 1000),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    idempotency_key text NOT NULL CHECK (length(btrim(idempotency_key)) BETWEEN 1 AND 128),
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (extract(year FROM reviewed_through)=tax_year),
    UNIQUE (profile_id,business_id,tax_year,idempotency_key),
    FOREIGN KEY (business_id,profile_id) REFERENCES ha_connected.businesses(business_id,profile_id)
);
CREATE OR REPLACE FUNCTION ha_connected.reject_record_confirmation_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Record confirmation history is append-only' USING ERRCODE='23514';
END $$;
DROP TRIGGER IF EXISTS record_confirmation_append_only ON ha_connected.record_confirmations;
CREATE TRIGGER record_confirmation_append_only BEFORE UPDATE OR DELETE
    ON ha_connected.record_confirmations FOR EACH ROW
    EXECUTE FUNCTION ha_connected.reject_record_confirmation_mutation();
