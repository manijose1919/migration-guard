-- A migration full of production footguns. MigrationGuard should flag these.

ALTER TABLE users ADD COLUMN age INTEGER NOT NULL;

CREATE INDEX idx_users_email ON users (email);

ALTER TABLE orders ALTER COLUMN total TYPE bigint;

ALTER TABLE users ADD CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES orgs (id);

ALTER TABLE users DROP COLUMN legacy_flag;
