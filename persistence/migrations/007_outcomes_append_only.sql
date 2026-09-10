-- Ejecutar después de 005, que convierte el formato histórico de identificadores.
CREATE OR REPLACE FUNCTION reject_promotion_outcome_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'promotion outcome is append-only'
        USING ERRCODE = '23514';
END;
$$;

CREATE OR REPLACE TRIGGER trg_promotion_outcomes_immutable
BEFORE UPDATE OR DELETE ON promotion_outcomes
FOR EACH ROW EXECUTE FUNCTION reject_promotion_outcome_mutation();

CREATE OR REPLACE TRIGGER trg_promotion_outcomes_no_truncate
BEFORE TRUNCATE ON promotion_outcomes
FOR EACH STATEMENT EXECUTE FUNCTION reject_promotion_outcome_mutation();
