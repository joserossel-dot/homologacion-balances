from persistence.neon_store import NeonKnowledgeStore, normalize_account_name
from pipeline.homologation_pipeline import HomologationPipeline


class FakeCursor:
    def __init__(self):
        self.calls = []

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None): self.calls.append((sql, params))
    def executemany(self, sql, params): self.calls.append((sql, list(params)))
    def fetchone(self): return None


class FakeConnection:
    def __init__(self): self.cursor_instance = FakeCursor()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.cursor_instance


def test_normaliza_nombre_contable():
    assert normalize_account_name("  IVA Crédito   Fiscal ") == "iva credito fiscal"


def test_normaliza_nombre_ignora_rayas_y_puntuacion_ocr():
    assert normalize_account_name("— Fondo Fijo") == "fondo fijo"
    assert normalize_account_name("Fondo-Fijo") == "fondo fijo"


def test_sin_database_url_el_store_esta_deshabilitado(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert not NeonKnowledgeStore().enabled


def test_validacion_y_diccionario_se_guardan_en_una_transaccion():
    connection = FakeConnection()
    store = NeonKnowledgeStore("postgresql://test", connect=lambda _: connection)
    store.save_validation(
        account_name="IVA Crédito Fiscal",
        validated_code="AC.08",
        suggested_code="AC.07",
        suggested_method="regex",
        suggested_confidence=0.88,
        source="validacion_humana",
    )
    assert len(connection.cursor_instance.calls) == 4
    upsert_params = connection.cursor_instance.calls[1][1]
    log_params = connection.cursor_instance.calls[3][1]
    assert upsert_params[1] == "iva credito fiscal"
    assert upsert_params[2] == "AC.08"
    assert log_params[6] is True


def test_lote_de_validaciones_reutiliza_una_sola_conexion():
    connection = FakeConnection()
    connections = []

    def connect(_):
        connections.append(connection)
        return connection

    store = NeonKnowledgeStore("postgresql://test", connect=connect)
    store.save_validations([
        {
            "account_name": "Caja", "validated_code": "AC.01",
            "source": "validacion_humana_lote",
            "suggested_code": "AC.02", "add_to_dictionary": True,
        },
        {
            "account_name": "Banco", "validated_code": "AC.01",
            "source": "validacion_humana_lote",
            "suggested_code": None, "add_to_dictionary": True,
        },
    ])

    assert len(connections) == 1
    assert len(connection.cursor_instance.calls) == 8
    assert connection.cursor_instance.calls[1][1][0] == "Caja"
    assert connection.cursor_instance.calls[5][1][0] == "Banco"


def test_lote_vacio_no_abre_conexion():
    calls = []
    store = NeonKnowledgeStore(
        "postgresql://test", connect=lambda _: calls.append(True)
    )

    store.save_validations([])

    assert calls == []


def test_seed_omite_codigos_que_no_existen_en_catalogo():
    connection = FakeConnection()
    store = NeonKnowledgeStore("postgresql://test", connect=lambda _: connection)
    counts = store.seed(
        {"AC.01": {"nombre_estandar": "Disponible", "categoria": "activo_corriente",
                   "tipo_estado": "balance", "naturaleza": "deudora"}},
        [
            {"cuenta_original": "Caja", "codigo_estandar": "AC.01"},
            {"cuenta_original": "Excluir", "codigo_estandar": "__EXCLUIR__"},
        ],
    )
    assert counts == (1, 1)
    assert len(connection.cursor_instance.calls) == 2


def test_guarda_categoria_en_neon():
    connection = FakeConnection()
    store = NeonKnowledgeStore("postgresql://test", connect=lambda _: connection)
    store.save_catalog_entry({
        "codigo_estandar": "AC.99", "nombre_estandar": "Prueba",
        "categoria": "activo_corriente", "tipo_estado": "balance",
        "naturaleza": "deudora",
    })
    assert connection.cursor_instance.calls[0][1][0] == "AC.99"


def test_pipeline_carga_diccionario_desde_neon(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(
        NeonKnowledgeStore,
        "load_dictionary",
        lambda self: [
            {"cuenta_original": "Cuenta aprendida", "codigo_estandar": "AC.01"},
            {"cuenta_original": "Omitir", "codigo_estandar": "__EXCLUIR__"},
        ],
    )
    assert HomologationPipeline._load_dictionary() == [
        {"cuenta_original": "Cuenta aprendida", "codigo_estandar": "AC.01"}
    ]


def test_healthcheck_confirma_conexion():
    connection = QueryConnection(QueryCursor(one=(1,)))
    store = NeonKnowledgeStore("postgresql://test", connect=lambda _: connection)
    assert store.healthcheck() is True


class QueryCursor(FakeCursor):
    def __init__(self, one=None, many=None):
        super().__init__()
        self.one = one
        self.many = many or []

    def fetchone(self): return self.one
    def fetchall(self): return self.many


class QueryConnection(FakeConnection):
    def __init__(self, cursor): self.cursor_instance = cursor


def test_estadisticas_de_aprendizaje():
    connection = QueryConnection(QueryCursor(one=(62, 876, 10, 15, 4)))
    store = NeonKnowledgeStore("postgresql://test", connect=lambda _: connection)
    assert store.learning_statistics() == {
        "catalog_entries": 62, "dictionary_entries": 876,
        "human_learned": 10, "validations": 15, "corrections": 4,
    }


def test_validaciones_recientes_limita_consulta():
    row = ("Caja", "AC.02", "AC.01", "regex", 0.88, True, "ana", "b.pdf", "hoy")
    cursor = QueryCursor(many=[row])
    store = NeonKnowledgeStore(
        "postgresql://test", connect=lambda _: QueryConnection(cursor)
    )
    result = store.recent_validations(500)
    assert result[0]["codigo_validado"] == "AC.01"
    assert cursor.calls[0][1] == (100,)


class SequenceCursor(FakeCursor):
    def __init__(self, rows):
        super().__init__()
        self.rows = iter(rows)

    def fetchone(self): return next(self.rows)


def test_rollback_restaura_codigo_anterior_si_cambio_sigue_vigente():
    cursor = SequenceCursor([
        ("Caja", "caja", "AC.02", "AC.01"),
        ("AC.01",),
    ])
    store = NeonKnowledgeStore(
        "postgresql://test", connect=lambda _: QueryConnection(cursor)
    )
    assert store.rollback_dictionary_change(7, reviewer="ana") is True
    assert any("SET codigo_estandar=%s" in sql for sql, _ in cursor.calls)


def test_rollback_rechaza_historial_obsoleto():
    cursor = SequenceCursor([
        ("Caja", "caja", "AC.02", "AC.01"),
        ("AC.03",),
    ])
    store = NeonKnowledgeStore(
        "postgresql://test", connect=lambda _: QueryConnection(cursor)
    )
    assert store.rollback_dictionary_change(7) is False
