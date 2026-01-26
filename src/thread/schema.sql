-- Thread-to-Project Mapping Schema
-- SQLite database for persistent thread-project associations

CREATE TABLE IF NOT EXISTS thread_mappings (
    thread_id TEXT PRIMARY KEY,
    project_path TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Index for reverse lookups (project_path → thread_id)
CREATE INDEX IF NOT EXISTS idx_thread_mappings_path ON thread_mappings(project_path);
