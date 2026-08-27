-- PAT.09 duplicaba semanticamente PAT.03. PAT.03 queda como codigo canonico.
-- La migracion es idempotente y conserva el historial de las decisiones.

UPDATE diccionario_homologacion
SET codigo_estandar = 'PAT.03', actualizado_en = NOW()
WHERE codigo_estandar = 'PAT.09'
  AND EXISTS (
      SELECT 1 FROM catalogo_maestro WHERE codigo_estandar = 'PAT.03'
  );

UPDATE log_validaciones
SET codigo_sugerido = 'PAT.03'
WHERE codigo_sugerido = 'PAT.09';

UPDATE log_validaciones
SET codigo_validado = 'PAT.03'
WHERE codigo_validado = 'PAT.09'
  AND EXISTS (
      SELECT 1 FROM catalogo_maestro WHERE codigo_estandar = 'PAT.03'
  );

UPDATE historial_diccionario SET codigo_anterior = 'PAT.03'
WHERE codigo_anterior = 'PAT.09';

UPDATE historial_diccionario SET codigo_nuevo = 'PAT.03'
WHERE codigo_nuevo = 'PAT.09';

UPDATE catalogo_maestro
SET nombre_estandar = 'Resultados Acumulados',
    activo = TRUE
WHERE codigo_estandar = 'PAT.03';

UPDATE catalogo_maestro
SET activo = FALSE
WHERE codigo_estandar = 'PAT.09';
