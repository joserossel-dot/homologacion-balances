CREATE TABLE IF NOT EXISTS promotion_outcomes (
    record_fingerprint CHAR(64) PRIMARY KEY CHECK (
        record_fingerprint ~ '^[a-f0-9]{64}$'
    ),
    evaluation_id UUID NOT NULL REFERENCES promotion_policy_metadata(evaluation_id),
    subject_id VARCHAR(300) NOT NULL,
    organization_id VARCHAR(300) NOT NULL,
    actor_id VARCHAR(300) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('APPLIED', 'FAILED', 'INCONSISTENT')),
    promotion_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL,
    error VARCHAR(300),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_promotion_outcome_evaluation
    ON promotion_outcomes(
        organization_id, evaluation_id, occurred_at DESC, record_fingerprint DESC
    );

CREATE INDEX IF NOT EXISTS idx_promotion_outcome_subject
    ON promotion_outcomes(
        organization_id, subject_id, occurred_at DESC, record_fingerprint DESC
    );
