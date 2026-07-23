import pytest
from knowledge.discovery.cluster_engine import ClusterEngine, Cluster


class TestCluster:
    def test_create(self):
        c = Cluster("C0001", "Test Cluster")
        assert c.id == "C0001"
        assert c.name == "Test Cluster"
        assert c.n_members == 0

    def test_add_member(self):
        c = Cluster("C0001", "Test")
        c.add_member("Cuenta 1", freq=10, empresa="Emp1")
        assert c.n_members == 1
        assert c.frecuencia == 10
        assert c.n_empresas == 1

    def test_add_duplicate_member(self):
        c = Cluster("C0001", "Test")
        c.add_member("C1")
        c.add_member("C1")
        assert c.n_members == 1

    def test_to_dict(self):
        c = Cluster("C0001", "Test")
        c.add_member("C1", freq=5)
        d = c.to_dict()
        assert d['id'] == "C0001"
        assert d['n_variantes'] == 1
        assert d['frecuencia'] == 5


class TestClusterEngine:
    def test_empty(self):
        e = ClusterEngine()
        clusters = e.build_clusters([], min_cluster_size=2)
        assert clusters == []

    def test_single_name(self):
        e = ClusterEngine()
        clusters = e.build_clusters([("Caja", 1, "")], min_cluster_size=2)
        assert clusters == []
        assert len(e.singletons) == 1

    def test_identical_names(self):
        e = ClusterEngine(threshold=0.7)
        clusters = e.build_clusters([
            ("Caja General", 5, "Emp1"),
            ("Caja General", 3, "Emp2"),
        ], min_cluster_size=2)
        assert len(clusters) >= 1

    def test_similar_names(self):
        e = ClusterEngine(threshold=0.7)
        clusters = e.build_clusters([
            ("Gastos de Administracion", 10, "Emp1"),
            ("Gastos Administrativos", 5, "Emp1"),
            ("Gastos Adm", 3, "Emp2"),
        ], min_cluster_size=2)
        assert len(clusters) >= 1
        cluster = [c for c in clusters if c.n_members >= 2]
        assert len(cluster) >= 1

    def test_no_similarity(self):
        e = ClusterEngine(threshold=0.7)
        clusters = e.build_clusters([
            ("Caja", 1, ""),
            ("Depreciacion", 1, ""),
        ], min_cluster_size=2)
        assert clusters == []
        assert len(e.singletons) >= 2

    def test_ambiguous(self):
        e = ClusterEngine(threshold=0.5)
        e.build_clusters([
            ("Banco Chile", 5, "E1"),
            ("Banco Estado", 5, "E1"),
            ("Depreciacion", 3, "E2"),
            ("Depreciacion Acumulada", 2, "E2"),
        ], min_cluster_size=2)
        amb = e.find_ambiguous(min_overlap=0.2)
        assert isinstance(amb, list)


if __name__ == "__main__":
    pytest.main([__file__])
