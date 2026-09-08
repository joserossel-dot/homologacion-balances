CREATE TABLE IF NOT EXISTS local_promotion_outcomes (
    record_fingerprint TEXT PRIMARY KEY CHECK (
        length(record_fingerprint) = 64
        AND record_fingerprint NOT GLOB '*[^a-f0-9]*'
    ),
    evaluation_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('APPLIED', 'FAILED', 'INCONSISTENT')),
    promotion_ids_json TEXT NOT NULL DEFAULT '[]',
    occurred_at TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (evaluation_id)
        REFERENCES local_promotion_policy_metadata(evaluation_id)
);

CREATE INDEX IF NOT EXISTS idx_local_promotion_outcome_evaluation
    ON local_promotion_outcomes(
        organization_id, evaluation_id, occurred_at DESC, record_fingerprint DESC
    );

CREATE INDEX IF NOT EXISTS idx_local_promotion_outcome_subject
    ON local_promotion_outcomes(
        organization_id, subject_id, occurred_at DESC, record_fingerprint DESC
    );

CREATE TRIGGER IF NOT EXISTS trg_local_promotion_outcomes_no_update
BEFORE UPDATE ON local_promotion_outcomes
BEGIN
    SELECT RAISE(ABORT, 'promotion outcome is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_local_promotion_outcomes_no_delete
BEFORE DELETE ON local_promotion_outcomes
BEGIN
    SELECT RAISE(ABORT, 'promotion outcome is append-only');
END;
