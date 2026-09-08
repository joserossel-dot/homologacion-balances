from __future__ import annotations

from persistence.neon_store import NeonKnowledgeStore


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []
        self.batches: list[tuple[str, list[tuple]]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None) -> None:
        self.executed.append((sql, params))

    def executemany(self, sql, rows) -> None:
        self.batches.append((sql, list(rows)))


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_instance


def test_seed_baseline_preserves_conflicts_and_records_version() -> None:
    connection = FakeConnection()
    store = NeonKnowledgeStore(
        "postgresql://local", connect=lambda _url: connection,
    )
    result = store.seed_baseline(
        {"AC.01": {
            "codigo_estandar": "AC.01", "nombre_estandar": "Caja",
            "categoria": "activo", "tipo_estado": "balance",
            "naturaleza": "activo",
        }},
        [{"cuenta_original": "Banco", "codigo_estandar": "AC.01"}],
        bundle_version="2026.08.1",
        bundle_checksum="a" * 64,
    )
    assert result == (1, 1)
    statements = [sql for sql, _rows in connection.cursor_instance.batches]
    assert len(statements) == 2
    assert all("ON CONFLICT" in sql and "DO NOTHING" in sql for sql in statements)
    assert all("DO UPDATE" not in sql for sql in statements)
    history = "\n".join(sql for sql, _params in connection.cursor_instance.executed)
    assert "INSERT INTO master_seed_history" in history
    assert "CREATE TABLE" not in history


def test_seed_baseline_rejects_untrusted_version_metadata() -> None:
    store = NeonKnowledgeStore("postgresql://local", connect=lambda _url: FakeConnection())
    try:
        store.seed_baseline({}, [], bundle_version="../../x", bundle_checksum="a" * 64)
    except ValueError as exc:
        assert "bundle_version" in str(exc)
    else:
        raise AssertionError("Debió rechazar bundle_version")
