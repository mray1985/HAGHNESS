-- Operator template for a fresh dedicated HA backup group role.
-- Run against the HA database; no password or LOGIN account is shipped.
-- Grant this role to a separately provisioned, protected backup service login.
-- Apply future-object defaults separately as the actual object-creating owner.
CREATE ROLE ha_backup_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA ha_connected TO ha_backup_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA ha_connected TO ha_backup_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA ha_connected TO ha_backup_reader;
-- For future tables/sequences, execute as each actual object-creating owner:
-- ALTER DEFAULT PRIVILEGES IN SCHEMA ha_connected GRANT SELECT ON TABLES TO ha_backup_reader;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA ha_connected GRANT SELECT ON SEQUENCES TO ha_backup_reader;
-- CONNECT and TLS/network restrictions are configured for the dedicated login.
