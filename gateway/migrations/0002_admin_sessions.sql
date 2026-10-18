CREATE TABLE IF NOT EXISTS admin_sessions (
    token_hash TEXT PRIMARY KEY,
    credential_tag TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS admin_sessions_expiry ON admin_sessions(expires_at);

CREATE TABLE IF NOT EXISTS admin_login_limits (
    bucket TEXT PRIMARY KEY,
    window INTEGER NOT NULL,
    attempts INTEGER NOT NULL CHECK (attempts > 0)
);
