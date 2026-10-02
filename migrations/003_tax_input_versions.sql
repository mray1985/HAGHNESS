-- Saving tax inputs is separate authority; no implicit grants.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conrelid='ha_connected.grants'::regclass
        AND conname='grants_action_check' AND pg_get_constraintdef(oid) LIKE '%save_tax%'
    ) THEN
        ALTER TABLE ha_connected.grants DROP CONSTRAINT grants_action_check;
        ALTER TABLE ha_connected.grants ADD CONSTRAINT grants_action_check
            CHECK (action IN ('read','post','correct','upload','restore','review_support','save_tax'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS ha_connected.tax_input_versions (
    seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_id uuid NOT NULL UNIQUE,
    profile_id text NOT NULL,
    business_id text NOT NULL,
    tax_year integer NOT NULL CHECK (tax_year BETWEEN 2023 AND 2026),
    document_id text NOT NULL,
    version_id text NOT NULL,
    previous_snapshot_id uuid,
    actor text NOT NULL CHECK (length(btrim(actor)) BETWEEN 1 AND 1000),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    reason text NOT NULL CHECK (length(reason) <= 2000),
    idempotency_key text NOT NULL CHECK (length(btrim(idempotency_key)) BETWEEN 1 AND 128),
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (previous_snapshot_id IS NULL OR length(btrim(reason)) >= 1),
    CHECK (previous_snapshot_id IS NULL OR previous_snapshot_id <> snapshot_id),
    UNIQUE (profile_id,business_id,tax_year,idempotency_key),
    UNIQUE (profile_id,business_id,tax_year,document_id,snapshot_id),
    UNIQUE (profile_id,business_id,tax_year,document_id,version_id),
    FOREIGN KEY (profile_id,business_id,tax_year,document_id,version_id)
        REFERENCES ha_connected.document_versions(profile_id,business_id,tax_year,document_id,version_id),
    FOREIGN KEY (profile_id,business_id,tax_year,document_id,previous_snapshot_id)
        REFERENCES ha_connected.tax_input_versions(profile_id,business_id,tax_year,document_id,snapshot_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS tax_input_one_original
    ON ha_connected.tax_input_versions(profile_id,business_id,tax_year)
    WHERE previous_snapshot_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS tax_input_one_successor
    ON ha_connected.tax_input_versions(previous_snapshot_id)
    WHERE previous_snapshot_id IS NOT NULL;

CREATE OR REPLACE FUNCTION ha_connected.reject_tax_input_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Tax input history is append-only' USING ERRCODE='23514';
END $$;
DROP TRIGGER IF EXISTS tax_input_append_only ON ha_connected.tax_input_versions;
CREATE TRIGGER tax_input_append_only BEFORE UPDATE OR DELETE
    ON ha_connected.tax_input_versions FOR EACH ROW
    EXECUTE FUNCTION ha_connected.reject_tax_input_mutation();


-- An existing lower-sequence predecessor makes cycles/disconnected inserts impossible.
CREATE OR REPLACE FUNCTION ha_connected.check_tax_input_predecessor()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE predecessor_seq bigint;
BEGIN
    IF NEW.previous_snapshot_id IS NOT NULL THEN
        SELECT seq INTO predecessor_seq FROM ha_connected.tax_input_versions
        WHERE snapshot_id=NEW.previous_snapshot_id
          AND profile_id=NEW.profile_id AND business_id=NEW.business_id
          AND tax_year=NEW.tax_year AND document_id=NEW.document_id;
        IF predecessor_seq IS NULL OR predecessor_seq >= NEW.seq THEN
            RAISE EXCEPTION 'Recorded earlier tax input predecessor required' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS tax_input_predecessor_guard ON ha_connected.tax_input_versions;
CREATE TRIGGER tax_input_predecessor_guard BEFORE INSERT
    ON ha_connected.tax_input_versions FOR EACH ROW
    EXECUTE FUNCTION ha_connected.check_tax_input_predecessor();
