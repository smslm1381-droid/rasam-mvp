CREATE TABLE IF NOT EXISTS admin_operations (
    request_id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('new', 'extend', 'revoke', 'quota')),
    license_hash TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS admin_operations_created ON admin_operations(created_at);
