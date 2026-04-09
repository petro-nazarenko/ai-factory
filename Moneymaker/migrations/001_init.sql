-- Moneymaker v5 — initial schema
-- Run once against the Postgres instance before starting the swarm.
-- SQLAlchemy's create_tables() will handle this automatically,
-- but this file is kept for auditing and manual recovery.

CREATE TABLE IF NOT EXISTS runs (
    id             SERIAL PRIMARY KEY,
    run_id         VARCHAR(64) UNIQUE NOT NULL,
    started_at     TIMESTAMPTZ DEFAULT NOW(),
    ended_at       TIMESTAMPTZ,
    signals_mined  INTEGER DEFAULT 0,
    ideas_generated INTEGER DEFAULT 0,
    ideas_passed   INTEGER DEFAULT 0,
    plans_built    INTEGER DEFAULT 0,
    deployed_url   TEXT DEFAULT '',
    total_revenue  FLOAT DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS ideas (
    id            SERIAL PRIMARY KEY,
    run_id        VARCHAR(64) REFERENCES runs(run_id) NOT NULL,
    source        VARCHAR(64) DEFAULT '',
    problem       TEXT DEFAULT '',
    target_user   TEXT DEFAULT '',
    solution      TEXT DEFAULT '',
    passed        INTEGER DEFAULT 0,
    score         FLOAT DEFAULT 0.0,
    reject_reason VARCHAR(64) DEFAULT '',
    mvp_format    VARCHAR(64) DEFAULT '',
    deployed_url  TEXT DEFAULT '',
    features      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ideas_run_id ON ideas(run_id);
CREATE INDEX IF NOT EXISTS idx_ideas_passed ON ideas(passed);
CREATE INDEX IF NOT EXISTS idx_ideas_reject_reason ON ideas(reject_reason) WHERE reject_reason != '';

CREATE TABLE IF NOT EXISTS metrics (
    id           SERIAL PRIMARY KEY,
    idea_id      INTEGER REFERENCES ideas(id) NOT NULL,
    tracking_id  VARCHAR(64) DEFAULT '',
    clicks       INTEGER DEFAULT 0,
    signups      INTEGER DEFAULT 0,
    payments     INTEGER DEFAULT 0,
    revenue      FLOAT DEFAULT 0.0,
    timestamp    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_tracking_id ON metrics(tracking_id);
CREATE INDEX IF NOT EXISTS idx_metrics_idea_id ON metrics(idea_id);

CREATE TABLE IF NOT EXISTS weights (
    feature     VARCHAR(128) PRIMARY KEY,
    weight      FLOAT DEFAULT 1.0,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default weights so the first cycle has a baseline
INSERT INTO weights (feature, weight) VALUES
    ('source_reddit',          1.0),
    ('source_producthunt',     1.0),
    ('source_indiehackers',    1.0),
    ('source_jobboards',       1.0),
    ('format_landing_page',    1.0),
    ('format_telegram_bot',    1.0),
    ('format_google_form_manual', 1.0),
    ('format_api_wrapper',     1.0)
ON CONFLICT (feature) DO NOTHING;
