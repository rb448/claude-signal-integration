-- Session Persistence Schema
-- SQLite database for durable session storage

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    status TEXT NOT NULL,
    context TEXT,  -- JSON blob
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Index for faster list() queries ordered by created_at
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at DESC);

-- Index for thread_id lookups (future use)
CREATE INDEX IF NOT EXISTS idx_sessions_thread_id ON sessions(thread_id);
