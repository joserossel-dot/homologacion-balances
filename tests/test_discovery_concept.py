import pytest
import json
import pandas as pd
from pathlib import Path
from knowledge.discovery.concept_discovery import ConceptDiscovery
from knowledge.discovery.reports import generate_reports


@pytest.fixture
def sample_accounts(tmp_path):
    df = pd.DataFrame({
        'cuenta': ['Caja General', 'Caja Chica', 'Banco Estado', 'Banco Chile',
                   'Depreciacion', 'Depreciacion Acumulada', 'Sueldo Ejecutivos',
                   'Sueldo Administrativos', 'Otros Gastos', 'Varios'],
        'frecuencia': [100, 50, 80, 60, 30, 20, 40, 35, 10, 5],
        'empresas_distintas': ['E1,E2', 'E1', 'E2,E3', 'E1,E3',
                               'E2', 'E3', 'E1,E2', 'E1',
                               'E2', 'E3'],
    })
    path = tmp_path / 'top_accounts.xlsx'
    df.to_excel(path, index=False)
    return path


class TestConceptDiscovery:
    def test_load(self, sample_accounts):
        cd = ConceptDiscovery()
        cd.load_accounts(sample_accounts)
        assert len(cd.accounts) >= 10
        assert len(cd.all_names_set) >= 10

    def test_load_with_extra_diccionario(self, sample_accounts, tmp_path):
        d = [{'cuenta_original': 'Caja General Extra', 'estandar': ''}]
        dp = tmp_path / 'diccionario.json'
        with open(dp, 'w', encoding='utf-8') as f:
            json.dump(d, f)
        cd = ConceptDiscovery()
        cd.load_accounts(sample_accounts, diccionario_path=dp)
        names = [a['name'] for a in cd.accounts]
        assert 'Caja General Extra' in names

    def test_run(self, sample_accounts):
        cd = ConceptDiscovery(threshold=0.5)
        cd.load_accounts(sample_accounts)
        result = cd.run(min_cluster_size=2)
        assert 'clusters' in result
        assert 'singletons' in result
        assert 'token_stats' in result
        assert 'ambiguous' in result
        assert result['total_accounts'] >= 10

    def test_export_graph(self, sample_accounts):
        cd = ConceptDiscovery(threshold=0.5)
        cd.load_accounts(sample_accounts)
        cd.run(min_cluster_size=2)
        graph = cd.export_cluster_graph()
        assert 'nodes' in graph
        assert 'links' in graph


class TestReports:
    def test_generate(self, sample_accounts, tmp_path):
        cd = ConceptDiscovery(threshold=0.5)
        cd.load_accounts(sample_accounts)
        result = cd.run(min_cluster_size=2)
        result['graph'] = cd.export_cluster_graph()
        result['freq_map'] = cd.freq_map

        out_dir = tmp_path / 'reports'
        paths = generate_reports(result, out_dir)
        assert len(paths) == 6
        for p in paths.values():
            assert Path(p).exists(), f"{p} not found"

    def test_report_empty_clusters(self, tmp_path):
        result = {
            'clusters': [],
            'singletons': ['Caja'],
            'token_stats': {'unique_tokens': 0, 'total_tokens': 0,
                            'avg_tokens_per_name': 0, 'avg_name_length': 0,
                            'top_tokens': []},
            'ambiguous': [],
            'total_accounts': 1,
            'clustered_accounts': 0,
            'singleton_count': 1,
            'graph': {'nodes': [], 'links': []},
            'freq_map': {},
        }
        out_dir = tmp_path / 'reports'
        paths = generate_reports(result, out_dir)
        assert len(paths) == 6


if __name__ == "__main__":
    pytest.main([__file__])
