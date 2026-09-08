CREATE TABLE IF NOT EXISTS master_seed_history (
    bundle_checksum TEXT PRIMARY KEY,
    bundle_version TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL,
    catalog_rows INTEGER NOT NULL CHECK (catalog_rows >= 0),
    dictionary_rows INTEGER NOT NULL CHECK (dictionary_rows >= 0)
);

CREATE INDEX IF NOT EXISTS idx_master_seed_history_applied_at
    ON master_seed_history(applied_at DESC);
