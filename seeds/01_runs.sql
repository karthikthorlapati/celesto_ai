-- Create runs table for SentinelLab PostgreSQL run ledger
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR(128) PRIMARY KEY,
    sandbox_name VARCHAR(128) NOT NULL,
    problem_id VARCHAR(128) NOT NULL,
    state VARCHAR(32) NOT NULL CHECK (state IN ('created', 'ready', 'running', 'succeeded', 'failed', 'deleted')),
    execution_target VARCHAR(64) NOT NULL CHECK (execution_target = 'celesto_sandbox'),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Idempotent seed run insertion: sbx-seeddemo1
INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target)
VALUES (
    'run-seed-001',
    'sbx-seeddemo1',
    'problem-seed-eval',
    'succeeded',
    'celesto_sandbox'
)
ON CONFLICT (run_id) DO NOTHING;
