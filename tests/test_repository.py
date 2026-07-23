import pytest
import json
import tempfile
from pathlib import Path
from knowledge.concept import Concept
from knowledge.repository import Repository


class TestRepository:
    @pytest.fixture
    def repo(self, tmp_path):
        r = Repository(tmp_path / "test_cmcc.json")
        r.load()
        return r

    def test_load_empty(self, repo):
        assert repo.count() == 0

    def test_add_and_count(self, repo):
        c = Concept(id="TEST.01", codigo="TEST.01", nombre="Test",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        repo.add(c)
        assert repo.count() == 1

    def test_add_duplicate_raises(self, repo):
        c = Concept(id="TEST.01", codigo="TEST.01", nombre="Test",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        repo.add(c)
        with pytest.raises(ValueError):
            repo.add(c)

    def test_find_by_id(self, repo):
        c = Concept(id="FIND.ID", codigo="FIND.CODE", nombre="Findable",
                     categoria="pasivo_corriente", tipo_estado_financiero="balance")
        repo.add(c)
        found = repo.find_by_id("FIND.ID")
        assert found is not None
        assert found.nombre == "Findable"

    def test_find_by_id_not_found(self, repo):
        assert repo.find_by_id("NONEXIST") is None

    def test_find_by_codigo(self, repo):
        c = Concept(id="C.01", codigo="C.01", nombre="Code Test",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        repo.add(c)
        found = repo.find_by_codigo("C.01")
        assert found is not None

    def test_find_by_name_exact(self, repo):
        c = Concept(id="N.01", codigo="N.01", nombre="Exact Name",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        repo.add(c)
        results = repo.find_by_name("Exact Name", exact=True)
        assert len(results) == 1

    def test_find_by_name_partial(self, repo):
        c = Concept(id="N.02", codigo="N.02", nombre="Partial Name Match",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        repo.add(c)
        results = repo.find_by_name("Partial", exact=False)
        assert len(results) >= 1

    def test_find_candidates(self, repo):
        c = Concept(id="C.01", codigo="C.01", nombre="Caja Bancos",
                     categoria="activo_corriente", tipo_estado_financiero="balance",
                     palabras_clave=["caja", "bancos"])
        repo.add(c)
        candidates = repo.find_candidates({"caja", "bancos"})
        assert len(candidates) >= 1
        assert candidates[0][0].id == "C.01"

    def test_find_candidates_empty_tokens(self, repo):
        assert repo.find_candidates(set()) == []

    def test_save_and_reload(self, repo, tmp_path):
        c = Concept(id="SAVE.01", codigo="SAVE.01", nombre="Save Test",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        repo.add(c)
        repo.save()

        r2 = Repository(tmp_path / "test_cmcc.json")
        r2.load()
        assert r2.count() == 1
        assert r2.find_by_id("SAVE.01") is not None

    def test_remove(self, repo):
        c = Concept(id="RM.01", codigo="RM.01", nombre="Remove Me",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        repo.add(c)
        assert repo.count() == 1
        repo.remove("RM.01")
        assert repo.count() == 0

    def test_remove_nonexistent(self, repo):
        assert repo.remove("NONEXIST") is False

    def test_list_all(self, repo):
        c1 = Concept(id="L1", codigo="L1", nombre="List1",
                      categoria="activo_corriente", tipo_estado_financiero="balance")
        c2 = Concept(id="L2", codigo="L2", nombre="List2",
                      categoria="activo_corriente", tipo_estado_financiero="balance")
        repo.add(c1)
        repo.add(c2)
        all_c = repo.list_all()
        assert len(all_c) == 2

    def test_find_by_name_with_synonym(self, repo):
        c = Concept(id="S.01", codigo="S.01", nombre="Principal",
                     categoria="activo_corriente", tipo_estado_financiero="balance",
                     sinonimos=["Alternativo"])
        repo.add(c)
        results = repo.find_by_name("Alternativo", exact=True)
        assert len(results) >= 1


if __name__ == "__main__":
    pytest.main([__file__])
