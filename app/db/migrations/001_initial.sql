-- Migration 001: Initial schema
-- Run automatically via SQLAlchemy create_all on startup.
-- Kept here for documentation and manual PostgreSQL migration.

CREATE TABLE IF NOT EXISTS audit_log (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id           TEXT NOT NULL,
    timestamp          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    transaction_id     TEXT NOT NULL,
    user_id            TEXT NOT NULL,
    verdict            TEXT NOT NULL CHECK (verdict IN ('ALLOW', 'REVIEW', 'BLOCK')),
    rule_score         REAL NOT NULL,
    ml_score           REAL NOT NULL,
    final_score        REAL NOT NULL,
    rule_blend_weight  REAL NOT NULL,
    triggered_rules    TEXT NOT NULL,  -- JSON array
    experiment_id      TEXT,
    experiment_variant TEXT,
    model_version      INTEGER NOT NULL,
    latency_ms         REAL NOT NULL,
    api_version        TEXT NOT NULL DEFAULT 'v1',
    request_payload    TEXT           -- JSON blob
);

CREATE INDEX IF NOT EXISTS idx_audit_log_transaction_id ON audit_log (transaction_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log (timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_verdict ON audit_log (verdict);

CREATE TABLE IF NOT EXISTS experiment_assignments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    variant       TEXT NOT NULL,
    assigned_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, experiment_id)
);

CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    window           TEXT NOT NULL,
    total_evaluated  INTEGER NOT NULL DEFAULT 0,
    total_blocked    INTEGER NOT NULL DEFAULT 0,
    total_reviewed   INTEGER NOT NULL DEFAULT 0,
    total_allowed    INTEGER NOT NULL DEFAULT 0,
    fraud_block_rate REAL NOT NULL DEFAULT 0,
    avg_final_score  REAL NOT NULL DEFAULT 0,
    p99_latency_ms   REAL NOT NULL DEFAULT 0,
    rule_hit_rates   TEXT,
    score_percentiles TEXT
);
