-- No altera registros existentes. Aplicar con el inicializador explícito.
CREATE OR REPLACE FUNCTION reject_promotion_policy_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'promotion policy metadata is append-only'
        USING ERRCODE = '23514';
END;
$$;

CREATE OR REPLACE TRIGGER trg_promotion_policy_immutable
BEFORE UPDATE OR DELETE ON promotion_policy_metadata
FOR EACH ROW EXECUTE FUNCTION reject_promotion_policy_mutation();

CREATE OR REPLACE TRIGGER trg_promotion_policy_no_truncate
BEFORE TRUNCATE ON promotion_policy_metadata
FOR EACH STATEMENT EXECUTE FUNCTION reject_promotion_policy_mutation();
