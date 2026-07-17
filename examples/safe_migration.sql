-- The safe expand/contract equivalents. MigrationGuard should pass these.

-- Nullable column with a default is a metadata-only change on modern Postgres.
ALTER TABLE users ADD COLUMN age INTEGER DEFAULT 0;

-- Concurrent index build does not block writes.
CREATE INDEX CONCURRENTLY idx_users_email ON users (email);

-- Foreign key added NOT VALID, validated separately (lightweight lock).
ALTER TABLE users ADD CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES orgs (id) NOT VALID;
