CREATE TABLE IF NOT EXISTS promotion_policy_metadata (
    evaluation_id UUID PRIMARY KEY,
    subject_id VARCHAR(300) NOT NULL,
    policy_mode VARCHAR(40) NOT NULL CHECK (policy_mode = 'manual_supervisor'),
    decision_allowed BOOLEAN NOT NULL,
    decision_reasons JSONB NOT NULL CHECK (jsonb_typeof(decision_reasons) = 'array'),
    evidence JSONB NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    supervisor_actor_id VARCHAR(300) NOT NULL,
    supervisor_role VARCHAR(20) NOT NULL CHECK (supervisor_role IN ('supervisor', 'admin')),
    organization_id VARCHAR(300) NOT NULL,
    conflict_count INTEGER NOT NULL CHECK (conflict_count >= 0),
    evaluated_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL CHECK (expires_at > evaluated_at),
    reversal_reference VARCHAR(300) NOT NULL,
    record_fingerprint CHAR(64) NOT NULL CHECK (record_fingerprint ~ '^[a-f0-9]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_promotion_policy_org_subject
    ON promotion_policy_metadata(organization_id, subject_id, evaluated_at DESC);

CREATE INDEX IF NOT EXISTS idx_promotion_policy_expiration
    ON promotion_policy_metadata(expires_at);
