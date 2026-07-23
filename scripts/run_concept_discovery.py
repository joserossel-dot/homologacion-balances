"""Run the full Concept Discovery pipeline."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge.discovery.concept_discovery import ConceptDiscovery
from knowledge.discovery.reports import generate_reports

BASE_DIR = Path('/Users/josealfonsorossel/AI-Projects/homologacion-balances')
TOP_ACCOUNTS = BASE_DIR / 'reports/classification_gap/top_accounts.xlsx'
DICCIONARIO = BASE_DIR / 'diccionario.json'
CMCC_PATH = BASE_DIR / 'knowledge/cmcc.json'
OUTPUT_DIR = BASE_DIR / 'reports/concept_discovery'
GRAPH_OUTPUT = BASE_DIR / 'knowledge/concept_graph.json'

print("=" * 60)
print("CONCEPT DISCOVERY ENGINE")
print("=" * 60)

discovery = ConceptDiscovery(threshold=0.70)
discovery.load_accounts(TOP_ACCOUNTS, diccionario_path=DICCIONARIO)

result = discovery.run(min_cluster_size=2)

graph = discovery.export_cluster_graph()
result['graph'] = graph
result['freq_map'] = discovery.freq_map

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
paths = generate_reports(result, OUTPUT_DIR)

GRAPH_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
# Also save as knowledge/concept_graph.json
import json
with open(GRAPH_OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(graph, f, indent=2, ensure_ascii=False)
print(f"Graph saved to {GRAPH_OUTPUT}")

print("\n" + "=" * 60)
print("REPORTS GENERATED:")
for name, path in paths.items():
    print(f"  {name}: {path}")
print("=" * 60)
