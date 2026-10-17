CREATE TABLE IF NOT EXISTS licenses (
    token_hash TEXT PRIMARY KEY,
    customer TEXT NOT NULL,
    plan TEXT NOT NULL CHECK (plan IN ('monthly', 'yearly')),
    expires_at INTEGER NOT NULL,
    daily_limit INTEGER NOT NULL CHECK (daily_limit > 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    usage_day TEXT NOT NULL DEFAULT '',
    used INTEGER NOT NULL DEFAULT 0 CHECK (used >= 0)
);
