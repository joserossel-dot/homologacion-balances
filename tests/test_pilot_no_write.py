import app_validacion as app
from pilot_mode import pilot_mode_active


def test_pilot_mode_recognizes_explicit_values(monkeypatch):
    for value in ("1", "true", "TRUE", " yes ", "on"):
        monkeypatch.setenv("PILOT_MODE", value)
        assert pilot_mode_active()
        assert app._modo_piloto_activo()
        assert not app._shadow_mode_activo()

    for value in ("", "0", "false", "off", "pilot"):
        monkeypatch.setenv("PILOT_MODE", value)
        assert not pilot_mode_active()


def test_pilot_persistence_functions_do_not_instantiate_neon(monkeypatch):
    monkeypatch.setenv("PILOT_MODE", "1")

    def should_not_be_called():
        raise AssertionError("Neon must not be instantiated for a pilot write")

    monkeypatch.setattr(app, "NeonKnowledgeStore", should_not_be_called)

    assert app._persistir_validacion(
        nombre="Clientes",
        codigo="AC.03",
        fuente="validacion_humana",
        agregar_diccionario=True,
    )
    assert app._persistir_validaciones_lote([])
    assert app._persistir_catalogo({"codigo_estandar": "AC.99"})


def test_pilot_keeps_operational_dictionary_read_only(monkeypatch):
    monkeypatch.setenv("PILOT_MODE", "1")

    class ReadOnlyStore:
        enabled = True

        def load_dictionary(self):
            return [{"cuenta_original": "Clientes", "codigo_estandar": "AC.03"}]

    monkeypatch.setattr(app, "NeonKnowledgeStore", ReadOnlyStore)
    app.cargar_diccionario_base.clear()
    try:
        assert app.cargar_diccionario_base() == [
            {"cuenta_original": "Clientes", "codigo_estandar": "AC.03"}
        ]
    finally:
        app.cargar_diccionario_base.clear()
