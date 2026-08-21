from pipeline.homologation_pipeline import HomologationPipeline


def test_regex_contextual_clasifica_venta_sin_codigo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual('VENTA MOTOS', 'GANANCIA')

    assert result['standard_code'] == 'ER.01'
    assert result['method'] == 'regex_contextual'
    assert result['confidence'] < 0.85


def test_regex_contextual_clasifica_costo_sin_codigo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual(
        'COSTO REPUESTOS Y ACCESORIOS', 'PERDIDA'
    )

    assert result['standard_code'] == 'ER.02'


def test_regex_contextual_descarta_categoria_incompatible(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    assert pipeline._classify_by_regex_contextual('VENTA MOTOS', 'ACTIVO') is None


def test_fallback_de_origen_clasifica_y_exige_revision():
    result = HomologationPipeline._classify_by_origin_fallback('', 'PERDIDA')

    assert result['standard_code'] == 'ER.18'
    assert result['method'] == 'origin_fallback'
    assert result['confidence'] < 0.85


def test_fallback_de_origen_no_sustituye_codigo_existente():
    assert HomologationPipeline._classify_by_origin_fallback(
        '4.01.01', 'PERDIDA'
    ) is None


def test_pasivo_admite_categoria_patrimonio():
    assert HomologationPipeline._is_code_allowed_for_tipo('PAT.01', 'PASIVO')


def test_contra_activo_sin_codigo_se_clasifica_como_activo_fijo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual(
        'DEPRECIACION ACUMULADA ACTIVOS', 'ACTIVO'
    )

    assert result['standard_code'] == 'ANC.01'
    assert result['confidence'] < 0.85
