PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    password_hash TEXT NOT NULL, platform_admin INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1, created INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
    daily_limit INTEGER NOT NULL DEFAULT 1000 CHECK(daily_limit > 0),
    allowed_hosts TEXT NOT NULL DEFAULT '[]', manager_chat_access INTEGER NOT NULL DEFAULT 0,
    created INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id),
    user_id TEXT NOT NULL REFERENCES users(id), role TEXT NOT NULL CHECK(role IN ('admin','member')),
    active INTEGER NOT NULL DEFAULT 1, daily_limit INTEGER NOT NULL CHECK(daily_limit > 0),
    allowed_sources TEXT NOT NULL DEFAULT '[]', UNIQUE(org_id,user_id)
);
CREATE TABLE IF NOT EXISTS invitations (
    id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
    org_id TEXT NOT NULL REFERENCES organizations(id), email TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','member')), daily_limit INTEGER NOT NULL,
    allowed_sources TEXT NOT NULL DEFAULT '[]', expires INTEGER NOT NULL, claim_id TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS login_limits (
    bucket TEXT PRIMARY KEY, window INTEGER NOT NULL, attempts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS connections (
    org_id TEXT PRIMARY KEY REFERENCES organizations(id), id TEXT NOT NULL UNIQUE,
    db_type TEXT NOT NULL, database_name TEXT NOT NULL, uri_cipher TEXT NOT NULL,
    ca_pem TEXT NOT NULL DEFAULT '', allowed_sources TEXT NOT NULL,
    documentation TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1,
    updated INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id),
    user_id TEXT NOT NULL REFERENCES users(id), access_key TEXT NOT NULL,
    title TEXT NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL, busy_turn_id TEXT,
    source_scope TEXT NOT NULL DEFAULT '[]', connection_key TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS chat_owner ON chats(org_id,user_id,access_key,updated);
CREATE TABLE IF NOT EXISTS turns (
    id TEXT PRIMARY KEY, chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    question TEXT NOT NULL, answer TEXT, status TEXT NOT NULL CHECK(status IN ('pending','complete','failed')),
    created INTEGER NOT NULL, UNIQUE(chat_id,id)
);
CREATE INDEX IF NOT EXISTS chat_turns ON turns(chat_id,created,id);
CREATE TABLE IF NOT EXISTS daily_usage (
    bucket TEXT NOT NULL, day TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0,
    reserved INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(bucket,day), CHECK(used >= 0 AND reserved >= 0)
);
CREATE TABLE IF NOT EXISTS reservations (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, user_id TEXT NOT NULL,
    turn_id TEXT NOT NULL UNIQUE, day TEXT NOT NULL, expires INTEGER NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('pending','used','released'))
);
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY, org_id TEXT, actor_id TEXT NOT NULL, action TEXT NOT NULL,
    subject_id TEXT, created INTEGER NOT NULL
);
