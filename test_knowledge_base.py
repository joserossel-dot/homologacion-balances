from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from knowledge_base.account import FinancialAccount
from knowledge_base.taxonomy import Taxonomy
from knowledge_base.synonym import SynonymEntry, SynonymManager
from knowledge_base.relation import Relation, RelationManager
from knowledge_base.rule import Rule, RuleManager
from knowledge_base.repository import Repository
from knowledge_base.loader import Loader
from knowledge_base.validator import Validator
from knowledge_base.exporter import Exporter
from knowledge_base.version import VERSION

logging.disable(logging.CRITICAL)


# ---------------------------------------------------------------------------
# FinancialAccount
# ---------------------------------------------------------------------------

def test_account_defaults():
    a = FinancialAccount()
    assert a.account_id == ""
    assert a.standard_code == ""
    assert a.class_ == ""
    assert a.status == "active"
    assert a.learning_weight == 1.0


def test_account_full_creation():
    a = FinancialAccount(
        account_id="AC.01",
        standard_code="AC.01",
        standard_name="Caja y Bancos",
        class_="activo",
        subclass="corriente",
        group="disponible",
        semantic_type="asset",
        financial_statement="balance",
        economic_nature="deudora",
        normal_balance="deudor",
        presentation_order=10,
        current=True,
        monetary=True,
        ifrs=["NIC 1", "NIC 7"],
        industry_tags=["general"],
        kpi_tags=["liquidez"],
        synonyms=["Caja", "Bancos", "Disponible"],
        keywords=["caja", "banco", "efectivo"],
        contra_accounts=[],
        related_accounts=["PC.02"],
        status="active",
    )
    assert a.account_id == "AC.01"
    assert a.standard_name == "Caja y Bancos"
    assert a.class_ == "activo"
    assert a.current is True
    assert "NIC 1" in a.ifrs
    assert "liquidez" in a.kpi_tags
    assert "Caja" in a.synonyms


def test_account_to_dict():
    a = FinancialAccount(
        account_id="PC.01",
        standard_code="PC.01",
        standard_name="Proveedores",
        class_="pasivo",
    )
    d = a.to_dict()
    assert d["account_id"] == "PC.01"
    assert d["class"] == "pasivo"
    assert d["status"] == "active"
    assert d["learning_weight"] == 1.0


def test_account_from_dict():
    data = {
        "account_id": "ER.01",
        "standard_code": "ER.01",
        "standard_name": "Ventas",
        "class": "resultado",
        "semantic_type": "revenue",
        "ifrs": ["NIIF 15"],
        "kpi_tags": ["rentabilidad"],
        "synonyms": ["Ingresos", "Ventas Netas"],
    }
    a = FinancialAccount.from_dict(data)
    assert a.standard_code == "ER.01"
    assert a.class_ == "resultado"
    assert "NIIF 15" in a.ifrs
    assert "Ingresos" in a.synonyms


def test_account_from_dict_uses_code_as_id():
    data = {"standard_code": "AC.03", "standard_name": "Clientes"}
    a = FinancialAccount.from_dict(data)
    assert a.account_id == "AC.03"
    assert a.standard_name == "Clientes"


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

def test_taxonomy_empty():
    t = Taxonomy()
    assert t.root.key == "root"
    assert t.root.children == []


def test_taxonomy_build():
    accounts = [
        FinancialAccount(account_id="AC.01", standard_code="AC.01", standard_name="Caja",
                         class_="activo", subclass="corriente", group="disponible"),
        FinancialAccount(account_id="AC.03", standard_code="AC.03", standard_name="Clientes",
                         class_="activo", subclass="corriente", group="deudores"),
        FinancialAccount(account_id="ANC.01", standard_code="ANC.01", standard_name="Activo Fijo",
                         class_="activo", subclass="no_corriente", group="propiedades"),
        FinancialAccount(account_id="PC.01", standard_code="PC.01", standard_name="Proveedores",
                         class_="pasivo", subclass="corriente", group="proveedores"),
    ]
    t = Taxonomy(accounts)
    assert len(t.root.children) == 2
    activo = t.get_node("activo")
    assert activo is not None
    assert len(activo.children) == 2


def test_taxonomy_find_by_class():
    accounts = [
        FinancialAccount(account_id="A1", standard_code="A1", standard_name="A1",
                         class_="activo"),
        FinancialAccount(account_id="P1", standard_code="P1", standard_name="P1",
                         class_="pasivo"),
    ]
    t = Taxonomy(accounts)
    assert len(t.find_accounts_by_class("activo")) == 1
    assert len(t.find_accounts_by_class("pasivo")) == 1
    assert len(t.find_accounts_by_class("patrimonio")) == 0


def test_taxonomy_find_by_subclass():
    accounts = [
        FinancialAccount(account_id="AC.01", standard_code="AC.01", standard_name="Caja",
                         class_="activo", subclass="corriente"),
        FinancialAccount(account_id="ANC.01", standard_code="ANC.01", standard_name="AF",
                         class_="activo", subclass="no_corriente"),
    ]
    t = Taxonomy(accounts)
    assert len(t.find_accounts_by_subclass("corriente")) == 1
    assert len(t.find_accounts_by_subclass("no_corriente")) == 1


def test_taxonomy_path():
    a = FinancialAccount(account_id="AC.01", standard_code="AC.01", standard_name="Caja",
                         class_="activo", subclass="corriente", group="disponible")
    t = Taxonomy([a])
    path = t.path_to(a)
    assert path == ["activo", "corriente", "disponible", "Caja"]


def test_taxonomy_to_dict():
    accounts = [
        FinancialAccount(account_id="AC.01", standard_code="AC.01", standard_name="Caja",
                         class_="activo"),
    ]
    t = Taxonomy(accounts)
    d = t.to_dict()
    assert d["key"] == "root"
    assert len(d["children"]) == 1


# ---------------------------------------------------------------------------
# Synonym
# ---------------------------------------------------------------------------

def test_synonym_entry():
    e = SynonymEntry(term="Caja", account_id="AC.01")
    assert e.term == "Caja"
    assert e.active is True
    assert e.confidence == 1.0


def test_synonym_entry_to_from_dict():
    e = SynonymEntry(term="Bancos", account_id="AC.01", source="learning", confidence=0.85)
    d = e.to_dict()
    assert d["term"] == "Bancos"
    assert d["confidence"] == 0.85
    e2 = SynonymEntry.from_dict(d)
    assert e2.term == "Bancos"
    assert e2.source == "learning"


def test_synonym_manager_add():
    m = SynonymManager()
    m.add(SynonymEntry(term="Caja", account_id="AC.01"))
    assert m.count() == 1


def test_synonym_manager_no_duplicates():
    m = SynonymManager()
    m.add(SynonymEntry(term="Caja", account_id="AC.01"))
    m.add(SynonymEntry(term="Caja", account_id="AC.01"))
    assert m.count() == 1


def test_synonym_manager_find_by_term():
    m = SynonymManager()
    m.add(SynonymEntry(term="Caja", account_id="AC.01"))
    m.add(SynonymEntry(term="Clientes", account_id="AC.03"))
    assert len(m.find_by_term("Caja")) == 1
    assert len(m.find_by_term("NoExiste")) == 0


def test_synonym_manager_find_by_account():
    m = SynonymManager()
    m.add(SynonymEntry(term="Caja", account_id="AC.01"))
    m.add(SynonymEntry(term="Bancos", account_id="AC.01"))
    assert len(m.find_by_account("AC.01")) == 2
    assert len(m.find_by_account("AC.03")) == 0


def test_synonym_manager_remove():
    m = SynonymManager()
    m.add(SynonymEntry(term="Caja", account_id="AC.01"))
    assert m.remove("Caja", "AC.01") is True
    assert m.count() == 0
    assert m.remove("NoExiste", "X") is False


def test_synonym_manager_has_duplicates():
    m = SynonymManager()
    m.add(SynonymEntry(term="Caja", account_id="AC.01"))
    m.add(SynonymEntry(term="Caja", account_id="AC.03"))
    dups = m.has_duplicates()
    assert len(dups) > 0


def test_synonym_manager_all_entries():
    m = SynonymManager()
    m.add(SynonymEntry(term="Caja", account_id="AC.01"))
    m.add(SynonymEntry(term="Clientes", account_id="AC.03"))
    assert len(m.all_entries()) == 2


# ---------------------------------------------------------------------------
# Relation
# ---------------------------------------------------------------------------

def test_relation_creation():
    r = Relation(source_id="ANC.01", target_id="ER.07", relation_type="contra_of")
    assert r.source_id == "ANC.01"
    assert r.relation_type == "contra_of"
    assert r.weight == 1.0


def test_relation_to_from_dict():
    r = Relation(source_id="A", target_id="B", relation_type="related_to",
                 weight=0.8, bidirectional=True, metadata={"note": "test"})
    d = r.to_dict()
    assert d["weight"] == 0.8
    assert d["bidirectional"] is True
    r2 = Relation.from_dict(d)
    assert r2.source_id == "A"
    assert r2.bidirectional is True


def test_relation_manager_add():
    m = RelationManager()
    m.add(Relation(source_id="A", target_id="B", relation_type="parent_of"))
    assert m.count() == 1


def test_relation_manager_invalid_type():
    m = RelationManager()
    try:
        m.add(Relation(source_id="A", target_id="B", relation_type="invalid_type"))
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_relation_manager_find():
    m = RelationManager()
    m.add(Relation(source_id="A", target_id="B", relation_type="parent_of"))
    r = m.find("A", "B", "parent_of")
    assert r is not None
    assert m.find("A", "C", "parent_of") is None


def test_relation_manager_find_by_source():
    m = RelationManager()
    m.add(Relation(source_id="A", target_id="B", relation_type="parent_of"))
    m.add(Relation(source_id="A", target_id="C", relation_type="related_to"))
    assert len(m.find_by_source("A")) == 2
    assert len(m.find_by_source("B")) == 0


def test_relation_manager_find_by_target():
    m = RelationManager()
    m.add(Relation(source_id="A", target_id="B", relation_type="parent_of"))
    assert len(m.find_by_target("B")) == 1
    assert len(m.find_by_target("A")) == 0


def test_relation_manager_find_by_type():
    m = RelationManager()
    m.add(Relation(source_id="A", target_id="B", relation_type="parent_of"))
    m.add(Relation(source_id="C", target_id="D", relation_type="related_to"))
    assert len(m.find_by_type("parent_of")) == 1
    assert len(m.find_by_type("related_to")) == 1


def test_relation_manager_find_by_account():
    m = RelationManager()
    m.add(Relation(source_id="A", target_id="B", relation_type="parent_of"))
    m.add(Relation(source_id="C", target_id="A", relation_type="related_to"))
    assert len(m.find_by_account("A")) == 2


def test_relation_manager_remove():
    m = RelationManager()
    m.add(Relation(source_id="A", target_id="B", relation_type="parent_of"))
    assert m.remove("A", "B", "parent_of") is True
    assert m.count() == 0
    assert m.remove("X", "Y", "parent_of") is False


def test_relation_supported_types():
    m = RelationManager()
    types = m.supported_types()
    assert "parent_of" in types
    assert "child_of" in types
    assert "contra_of" in types
    assert "related_to" in types


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------

def test_rule_creation():
    r = Rule(rule_id="R01", name="Contra asset in income",
             description="Detect contra assets in income statement",
             rule_type="validation", severity="error")
    assert r.rule_id == "R01"
    assert r.severity == "error"
    assert r.active is True


def test_rule_to_from_dict():
    r = Rule(rule_id="R01", name="Test Rule", metadata={"key": "val"})
    d = r.to_dict()
    assert d["metadata"]["key"] == "val"
    r2 = Rule.from_dict(d)
    assert r2.rule_id == "R01"


def test_rule_manager_add():
    m = RuleManager()
    m.add(Rule(rule_id="R01", name="Rule 1"))
    assert m.count() == 1


def test_rule_manager_get():
    m = RuleManager()
    m.add(Rule(rule_id="R01", name="Rule 1"))
    r = m.get("R01")
    assert r is not None
    assert r.name == "Rule 1"
    assert m.get("R99") is None


def test_rule_manager_remove():
    m = RuleManager()
    m.add(Rule(rule_id="R01", name="Rule 1"))
    assert m.remove("R01") is True
    assert m.count() == 0
    assert m.remove("R99") is False


def test_rule_manager_find_by_type():
    m = RuleManager()
    m.add(Rule(rule_id="R01", name="R1", rule_type="validation"))
    m.add(Rule(rule_id="R02", name="R2", rule_type="audit"))
    m.add(Rule(rule_id="R03", name="R3", rule_type="validation"))
    assert len(m.find_by_type("validation")) == 2
    assert len(m.find_by_type("audit")) == 1
    assert len(m.find_by_type("unknown")) == 0


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

def test_repository_empty():
    r = Repository()
    assert r.count_accounts() == 0
    assert r.list_accounts() == []


def test_repository_crud():
    r = Repository()
    a = FinancialAccount(account_id="AC.01", standard_code="AC.01", standard_name="Caja")
    r.add_account(a)
    assert r.count_accounts() == 1
    assert r.get_account("AC.01") is a
    assert r.get_account_by_code("AC.01") is a

    a2 = FinancialAccount(account_id="AC.01", standard_code="AC.01", standard_name="Caja y Bancos")
    assert r.update_account(a2) is True
    assert r.get_account("AC.01").standard_name == "Caja y Bancos"

    assert r.update_account(FinancialAccount(account_id="NUEVO", standard_code="NUEVO", standard_name="Nuevo")) is False

    assert r.delete_account("AC.01") is True
    assert r.count_accounts() == 0
    assert r.delete_account("NOEXISTE") is False


def test_repository_find_by():
    r = Repository()
    r.add_account(FinancialAccount(account_id="A1", standard_code="A1", standard_name="A",
                                   class_="activo", subclass="corriente",
                                   semantic_type="asset", kpi_tags=["liquidez"],
                                   industry_tags=["general"]))
    r.add_account(FinancialAccount(account_id="P1", standard_code="P1", standard_name="P",
                                   class_="pasivo", subclass="corriente",
                                   semantic_type="liability", kpi_tags=["endeudamiento"],
                                   industry_tags=["general"]))
    assert len(r.find_by_class("activo")) == 1
    assert len(r.find_by_subclass("corriente")) == 2
    assert len(r.find_by_semantic_type("asset")) == 1
    assert len(r.find_by_kpi("liquidez")) == 1
    assert len(r.find_by_industry_tag("general")) == 2


def test_repository_find_by_status():
    r = Repository()
    r.add_account(FinancialAccount(account_id="A1", standard_code="A1", standard_name="A",
                                   status="active"))
    r.add_account(FinancialAccount(account_id="A2", standard_code="A2", standard_name="B",
                                   status="inactive"))
    assert len(r.find_by_status("active")) == 1
    assert len(r.find_by_status("inactive")) == 1
    assert len(r.find_by_status("deprecated")) == 0


def test_repository_find_by_keyword():
    r = Repository()
    r.add_account(FinancialAccount(account_id="AC.01", standard_code="AC.01", standard_name="Caja",
                                   synonyms=["Caja", "Bancos"], keywords=["efectivo"]))
    r.add_account(FinancialAccount(account_id="AC.03", standard_code="AC.03", standard_name="Clientes",
                                   synonyms=["Deudores"], keywords=["clientes"]))
    assert len(r.find_by_keyword("caja")) == 1
    assert len(r.find_by_keyword("efectivo")) == 1
    assert len(r.find_by_keyword("clientes")) == 1


def test_repository_synonyms():
    r = Repository()
    r.add_synonym(SynonymEntry(term="Caja", account_id="AC.01"))
    assert r.synonyms.count() == 1
    assert r.remove_synonym("Caja", "AC.01") is True
    assert r.synonyms.count() == 0


def test_repository_relations():
    r = Repository()
    r.add_relation(Relation(source_id="A", target_id="B", relation_type="parent_of"))
    assert r.relations.count() == 1
    assert r.remove_relation("A", "B", "parent_of") is True
    assert r.relations.count() == 0


def test_repository_rules():
    r = Repository()
    r.add_rule(Rule(rule_id="R01", name="Test"))
    assert r.rules.count() == 1
    assert r.remove_rule("R01") is True
    assert r.rules.count() == 0


def test_repository_build_taxonomy():
    r = Repository()
    r.add_account(FinancialAccount(account_id="AC.01", standard_code="AC.01", standard_name="Caja",
                                   class_="activo", subclass="corriente"))
    t = r.build_taxonomy()
    assert len(t.find_accounts_by_class("activo")) == 1


def test_repository_find_contra_accounts():
    r = Repository()
    r.add_account(FinancialAccount(account_id="ANC.01", standard_code="ANC.01", standard_name="AF",
                                   contra_accounts=["DEP.AC"]))
    r.add_account(FinancialAccount(account_id="DEP.AC", standard_code="DEP.AC", standard_name="Dep Ac"))
    result = r.find_contra_accounts("ANC.01")
    assert len(result) == 1
    assert result[0].account_id == "DEP.AC"


def test_repository_find_related_accounts():
    r = Repository()
    r.add_account(FinancialAccount(account_id="AC.01", standard_code="AC.01", standard_name="Caja",
                                   related_accounts=["PC.02"]))
    r.add_account(FinancialAccount(account_id="PC.02", standard_code="PC.02", standard_name="Oblig Bancarias"))
    result = r.find_related_accounts("AC.01")
    assert len(result) == 1


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def test_loader_from_dict():
    r = Repository()
    loader = Loader(r)
    data = {
        "meta": {"version": "1.0"},
        "accounts": [
            {"account_id": "AC.01", "standard_code": "AC.01", "standard_name": "Caja",
             "class": "activo"},
            {"account_id": "PC.01", "standard_code": "PC.01", "standard_name": "Proveedores",
             "class": "pasivo"},
        ],
        "synonyms": [
            {"term": "Caja", "account_id": "AC.01"},
        ],
        "relations": [
            {"source_id": "AC.01", "target_id": "PC.01", "relation_type": "related_to"},
        ],
        "rules": [
            {"rule_id": "R01", "name": "Test Rule"},
        ],
    }
    count = loader.load_from_dict(data)
    assert count == 2
    assert r.count_accounts() == 2
    assert r.synonyms.count() == 1
    assert r.relations.count() == 1
    assert r.rules.count() == 1


def test_loader_from_json():
    r = Repository()
    loader = Loader(r)
    data = {
        "accounts": [
            {"account_id": "AC.01", "standard_code": "AC.01", "standard_name": "Caja",
             "class": "activo"},
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        tmp_path = f.name
    try:
        count = loader.load_from_json(tmp_path)
        assert count == 1
        assert r.count_accounts() == 1
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def test_validator_no_errors():
    r = Repository()
    r.add_account(FinancialAccount(account_id="AC.01", standard_code="AC.01",
                                   standard_name="Caja", status="active"))
    v = Validator(r)
    errors = v.validate_all()
    assert errors == []


def test_validator_duplicate_codes():
    r = Repository()
    r.add_account(FinancialAccount(account_id="ID1", standard_code="AC.01",
                                   standard_name="Caja", status="active"))
    r.add_account(FinancialAccount(account_id="ID2", standard_code="AC.01",
                                   standard_name="Caja 2", status="active"))
    v = Validator(r)
    errors = v.validate_all()
    codes = {e.code for e in errors}
    assert "DUPLICATE_CODE" in codes


def test_validator_nonexistent_contra():
    r = Repository()
    r.add_account(FinancialAccount(account_id="AC.01", standard_code="AC.01",
                                   standard_name="Caja", status="active",
                                   contra_accounts=["NO_EXISTE"]))
    v = Validator(r)
    errors = v.validate_all()
    codes = {e.code for e in errors}
    assert "NONEXISTENT_CONTRA_ACCOUNT" in codes


def test_validator_nonexistent_related():
    r = Repository()
    r.add_account(FinancialAccount(account_id="AC.01", standard_code="AC.01",
                                   standard_name="Caja", status="active",
                                   related_accounts=["NO_EXISTE"]))
    v = Validator(r)
    errors = v.validate_all()
    codes = {e.code for e in errors}
    assert "NONEXISTENT_RELATED_ACCOUNT" in codes


def test_validator_invalid_status():
    r = Repository()
    r.add_account(FinancialAccount(account_id="AC.01", standard_code="AC.01",
                                   standard_name="Caja", status="invalid_status"))
    v = Validator(r)
    errors = v.validate_all()
    codes = {e.code for e in errors}
    assert "INVALID_STATUS" in codes


def test_validator_missing_code():
    r = Repository()
    r.add_account(FinancialAccount(account_id="ID1", standard_code="",
                                   standard_name="Sin Codigo", status="active"))
    v = Validator(r)
    errors = v.validate_all()
    codes = {e.code for e in errors}
    assert "MISSING_CODE" in codes


def test_validator_missing_name():
    r = Repository()
    r.add_account(FinancialAccount(account_id="ID1", standard_code="AC.01",
                                   standard_name="", status="active"))
    v = Validator(r)
    errors = v.validate_all()
    codes = {e.code for e in errors}
    assert "MISSING_NAME" in codes


def test_validator_cycle():
    r = Repository()
    r.add_account(FinancialAccount(account_id="A", standard_code="A",
                                   standard_name="A", status="active",
                                   contra_accounts=["B"]))
    r.add_account(FinancialAccount(account_id="B", standard_code="B",
                                   standard_name="B", status="active",
                                   related_accounts=["A"]))
    v = Validator(r)
    errors = v.validate_all()
    codes = {e.code for e in errors}
    assert "CYCLE_DETECTED" in codes


def test_validator_invalid_relation():
    r = Repository()
    r.add_account(FinancialAccount(account_id="A", standard_code="A",
                                   standard_name="A", status="active"))
    r.add_relation(Relation(source_id="A", target_id="NO_EXISTE", relation_type="related_to"))
    v = Validator(r)
    errors = v.validate_all()
    codes = {e.code for e in errors}
    assert "INVALID_RELATION_TARGET" in codes


def test_validator_duplicate_synonyms():
    r = Repository()
    r.add_account(FinancialAccount(account_id="AC.01", standard_code="AC.01",
                                   standard_name="Caja", status="active"))
    r.add_account(FinancialAccount(account_id="AC.03", standard_code="AC.03",
                                   standard_name="Clientes", status="active"))
    r.add_synonym(SynonymEntry(term="Caja", account_id="AC.01"))
    r.add_synonym(SynonymEntry(term="Caja", account_id="AC.03"))
    v = Validator(r)
    errors = v.validate_all()
    codes = {e.code for e in errors}
    assert "DUPLICATE_SYNONYM" in codes


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------

def test_exporter_to_dict():
    r = Repository()
    r.add_account(FinancialAccount(account_id="AC.01", standard_code="AC.01",
                                   standard_name="Caja", class_="activo"))
    r.add_synonym(SynonymEntry(term="Caja", account_id="AC.01"))
    r.add_relation(Relation(source_id="AC.01", target_id="PC.02", relation_type="related_to"))
    r.add_rule(Rule(rule_id="R01", name="Test"))
    e = Exporter(r)
    data = e.to_dict()
    assert data["meta"]["total_accounts"] == 1
    assert data["meta"]["total_synonyms"] == 1
    assert data["meta"]["total_relations"] == 1
    assert data["meta"]["total_rules"] == 1
    assert len(data["accounts"]) == 1
    assert len(data["synonyms"]) == 1
    assert len(data["relations"]) == 1
    assert len(data["rules"]) == 1


def test_exporter_to_json():
    r = Repository()
    r.add_account(FinancialAccount(account_id="AC.01", standard_code="AC.01",
                                   standard_name="Caja", class_="activo"))
    e = Exporter(r)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name
    try:
        output = e.to_json(tmp_path)
        assert "AC.01" in output
        with open(tmp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["meta"]["total_accounts"] == 1
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

def test_version():
    assert VERSION == "1.0.0"


# ---------------------------------------------------------------------------
# Integration: round-trip load/save
# ---------------------------------------------------------------------------

def test_round_trip():
    r = Repository()
    accounts_data = [
        {"account_id": "AC.01", "standard_code": "AC.01", "standard_name": "Caja",
         "class": "activo", "status": "active"},
        {"account_id": "PC.01", "standard_code": "PC.01", "standard_name": "Proveedores",
         "class": "pasivo", "status": "active"},
    ]
    synonyms_data = [
        {"term": "Caja", "account_id": "AC.01"},
    ]
    full_data = {
        "accounts": accounts_data,
        "synonyms": synonyms_data,
    }
    loader = Loader(r)
    loader.load_from_dict(full_data)
    assert r.count_accounts() == 2
    assert r.synonyms.count() == 1

    e = Exporter(r)
    exported = e.to_dict()
    assert exported["meta"]["total_accounts"] == 2
    assert exported["meta"]["total_synonyms"] == 1

    r2 = Repository()
    loader2 = Loader(r2)
    loader2.load_from_dict(exported)
    assert r2.count_accounts() == 2
    assert r2.synonyms.count() == 1


# ---------------------------------------------------------------------------
# Run guard
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    this = sys.modules[__name__]
    passed = 0
    failed = 0
    for name in sorted(dir(this)):
        if name.startswith("test_"):
            try:
                getattr(this, name)()
                print(f"  \u2713 {name}")
                passed += 1
            except Exception as e:
                print(f"  \u2717 {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
