-- Notification preferences schema
-- Stores per-thread notification preferences with event-level granularity

CREATE TABLE IF NOT EXISTS notification_preferences (
    thread_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (thread_id, event_type)
);

-- Index for querying all preferences for a thread
CREATE INDEX IF NOT EXISTS idx_thread_preferences ON notification_preferences(thread_id);
