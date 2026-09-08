CREATE TABLE IF NOT EXISTS local_promotion_policy_metadata (
    evaluation_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    policy_mode TEXT NOT NULL CHECK (policy_mode = 'manual_supervisor'),
    decision_allowed INTEGER NOT NULL CHECK (decision_allowed IN (0, 1)),
    decision_reasons_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    supervisor_actor_id TEXT NOT NULL,
    supervisor_role TEXT NOT NULL CHECK (supervisor_role IN ('supervisor', 'admin')),
    organization_id TEXT NOT NULL,
    conflict_count INTEGER NOT NULL CHECK (conflict_count >= 0),
    evaluated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    reversal_reference TEXT NOT NULL,
    record_fingerprint TEXT NOT NULL CHECK (
        length(record_fingerprint) = 64
        AND record_fingerprint NOT GLOB '*[^a-f0-9]*'
    ),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_local_promotion_policy_org_subject
    ON local_promotion_policy_metadata(
        organization_id, subject_id, evaluated_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_local_promotion_policy_expiration
    ON local_promotion_policy_metadata(organization_id, expires_at);

CREATE TRIGGER IF NOT EXISTS trg_local_promotion_policy_no_update
BEFORE UPDATE ON local_promotion_policy_metadata
BEGIN
    SELECT RAISE(ABORT, 'promotion policy metadata is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_local_promotion_policy_no_delete
BEFORE DELETE ON local_promotion_policy_metadata
BEGIN
    SELECT RAISE(ABORT, 'promotion policy metadata is append-only');
END;
