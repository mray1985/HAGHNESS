CREATE SCHEMA IF NOT EXISTS ha_connected;
CREATE TABLE IF NOT EXISTS ha_connected.profiles (
    profile_id text PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS ha_connected.businesses (
    business_id text PRIMARY KEY,
    profile_id text NOT NULL REFERENCES ha_connected.profiles,
    UNIQUE (business_id, profile_id)
);
CREATE TABLE IF NOT EXISTS ha_connected.grants (
    subject text NOT NULL,
    profile_id text NOT NULL,
    business_id text NOT NULL,
    tax_year integer NOT NULL CHECK (tax_year BETWEEN 2023 AND 2026),
    action text NOT NULL CHECK (action IN ('read','post','correct','upload','restore')),
    PRIMARY KEY (subject,profile_id,business_id,tax_year,action),
    FOREIGN KEY (business_id,profile_id) REFERENCES ha_connected.businesses(business_id,profile_id)
);
CREATE TABLE IF NOT EXISTS ha_connected.ledger_events (
    seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    profile_id text NOT NULL,
    business_id text NOT NULL,
    tax_year integer NOT NULL CHECK (tax_year BETWEEN 2023 AND 2026),
    event_id text NOT NULL,
    record jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (profile_id,business_id,tax_year,event_id),
    FOREIGN KEY (business_id,profile_id) REFERENCES ha_connected.businesses(business_id,profile_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ledger_one_correction
    ON ha_connected.ledger_events(profile_id,business_id,tax_year,(record->>'replaces'))
    WHERE record->>'kind' = 'correction';
CREATE TABLE IF NOT EXISTS ha_connected.document_versions (
    version_id text PRIMARY KEY,
    document_id text NOT NULL,
    profile_id text NOT NULL,
    business_id text NOT NULL,
    tax_year integer NOT NULL CHECK (tax_year BETWEEN 2023 AND 2026),
    object_key text NOT NULL UNIQUE,
    sha256 text NOT NULL CHECK (length(sha256)=64),
    mime text NOT NULL,
    actor text NOT NULL,
    created_at timestamptz NOT NULL,
    previous_version_id text REFERENCES ha_connected.document_versions,
    reason text NOT NULL,
    storage_version text NOT NULL,
    idempotency_key text NOT NULL,
    fingerprint jsonb NOT NULL,
    UNIQUE (profile_id,business_id,tax_year,idempotency_key),
    FOREIGN KEY (business_id,profile_id) REFERENCES ha_connected.businesses(business_id,profile_id)
);
