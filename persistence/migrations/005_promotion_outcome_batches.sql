ALTER TABLE promotion_outcomes
    ADD COLUMN IF NOT EXISTS promotion_ids JSONB NOT NULL DEFAULT '[]'::jsonb;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='promotion_outcomes' AND column_name='promotion_id'
    ) THEN
        EXECUTE 'UPDATE promotion_outcomes '
                'SET promotion_ids = jsonb_build_array(promotion_id) '
                'WHERE promotion_ids = ''[]''::jsonb AND promotion_id IS NOT NULL';
    END IF;
END $$;
