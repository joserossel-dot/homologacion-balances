# Interfaces públicas del sistema

Todas las interfaces se definen como Protocolos (Python 3.8+ typing.Protocol)
para permitir implementaciones múltiples sin herencia forzada.

---

## DocumentContext

Contexto único que atraviesa todo el pipeline. Ver `document_context.md` para
la especificación completa de campos.

```python
@dataclass
class DocumentContext:
    document_id: str
    source_file: str
    document_type: str | None
    family: str | None
    raw_lines: list[str]
    pages: int
    layout: dict
    structure: StructuralTree | None
    template: StructureTemplate | None
    accounts: list[AccountBalance]
    knowledge: list[KnowledgeMatch]
    validation: ValidationResult | None
    confidence: ConfidenceResult | None
    coverage: CoverageResult | None
    review: ReviewCandidate | None
    status: ProcessingStatus
    errors: list[ProcessingError]
    warnings: list[str]
    metadata: dict
```

**Quién llena cada campo:** Ver `document_context.md`.

---

## IDR — Intelligent Document Router

```python
class IDRouter(Protocol):
    def route(self, file_path: str) -> DocumentContext:
        """Examina el archivo y produce un DocumentContext inicial con
        document_type, family y routing_path determinados."""
```

**Input:** Ruta a un archivo en INBOX.
**Output:** DocumentContext con `document_type`, `family` poblados.

---

## SIE — Structure Intelligence Engine

```python
class StructureEngine(Protocol):
    def analyze(self, ctx: DocumentContext) -> StructuralTree:
        """Construye el árbol estructural del documento."""

    def detect_family(self, tree: StructuralTree) -> str:
        """Clasifica la familia del documento basado en su estructura."""

    def detect_layout(self, raw_lines: list[str]) -> dict:
        """Detecta el layout de columnas del documento."""
```

```python
@dataclass
class StructuralNode:
    level: int
    code: str
    name: str
    section: str
    children: list[StructuralNode]

@dataclass
class StructuralTree:
    root: StructuralNode
    nodes: list[StructuralNode]
    depth: int
    sections: list[SectionInfo]
    signature: StructuralSignature
```

```python
@dataclass
class StructuralSignature:
    depth_profile: list[int]
    section_count: int
    node_count: int
    code_format: str
```

```python
@dataclass
class SectionInfo:
    name: str
    start_line: int
    end_line: int
    node_count: int
```

---

## Template Repository

```python
class TemplateRepository(Protocol):
    def get_template(self, template_id: str) -> StructureTemplate | None:
        """Recupera un template por ID."""

    def find_matches(self, tree: StructuralTree, threshold: float = 0.7) -> list[TemplateMatch]:
        """Busca templates que matcheen el árbol dado."""

    def save_template(self, template: StructureTemplate) -> str:
        """Persiste un nuevo template y retorna su ID."""

    def classify_family(self, tree: StructuralTree) -> str:
        """Clasifica la familia del árbol usando templates conocidos."""
```

```python
@dataclass
class StructureTemplate:
    template_id: str
    family: str
    signature: StructuralSignature
    nodes: list[StructuralNode]
    section_order: list[str]
    frequency: int
```

```python
@dataclass
class TemplateMatch:
    template: StructureTemplate
    similarity: float
    matched_nodes: int
    total_nodes: int
```

---

## Parser

```python
class Parser(Protocol):
    def parse(self, ctx: DocumentContext) -> list[AccountBalance]:
        """Extrae cuentas y montos del documento usando el contexto
        estructural (layout, template, secciones)."""

    def can_handle(self, file_path: str) -> bool:
        """Indica si este parser puede procesar el archivo."""
```

```python
@dataclass
class AccountBalance:
    account_id: str
    code: str
    name: str
    amount: Decimal
    level: int
    section: str
    nature: AccountNature
    is_total: bool
    is_subtotal: bool
    parent_code: str | None
    raw_line: str
    source_page: int
```

```python
class AccountNature(Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"
```

---

## Knowledge Base CMCC

```python
class KnowledgeBase(Protocol):
    def homologate(self, account: AccountBalance) -> list[KnowledgeMatch]:
        """Busca el código canónico y nombre para una cuenta dada."""

    def homologate_batch(self, accounts: list[AccountBalance]) -> list[KnowledgeMatch]:
        """Homologa un lote de cuentas."""
```

```python
@dataclass
class KnowledgeMatch:
    source_account: AccountBalance
    canonical_code: str
    canonical_name: str
    account_type: AccountType
    confidence: float         # 0.0 - 1.0
    match_source: str         # "exact", "fuzzy", "synonym", "rule", "semantic"
    variant: str | None       # Variante CMCC si aplica
    family_group: str | None  # Grupo familiar
```

```python
class AccountType(Enum):
    ACTIVO = "ACTIVO"
    PASIVO = "PASIVO"
    PATRIMONIO = "PATRIMONIO"
    RESULTADO_DEUDOR = "RESULTADO_DEUDOR"
    RESULTADO_ACREEDOR = "RESULTADO_ACREEDOR"
    ORDEN_DEUDORA = "ORDEN_DEUDORA"
    ORDEN_ACREEDORA = "ORDEN_ACREEDORA"
    OTRO = "OTRO"
```

---

## BIV — Balance Integrity Validator

```python
class BalanceValidator(Protocol):
    def validate(self, ctx: DocumentContext) -> ValidationResult:
        """Ejecuta todas las validaciones de integridad contable."""
```

```python
@dataclass
class ValidationResult:
    hierarchy: HierarchyResult
    subtotals: SubtotalResult
    equation: EquationResult
    missing_accounts: MissingAccountResult
    integrity_score: IntegrityScore
    errors: list[ValidationError]
```

```python
@dataclass
class HierarchyResult:
    tree: HierarchyTree
    root_nodes: int
    max_depth: int
    orphan_accounts: list[str]
    valid: bool
```

```python
@dataclass
class HierarchyTree:
    account: AccountBalance
    children: list[HierarchyTree]
    depth: int
    is_valid: bool
```

```python
@dataclass
class SubtotalResult:
    subtotals: list[SubtotalCheck]
    total_checked: int
    valid_count: int
    invalid_count: int
    threshold: Decimal
```

```python
@dataclass
class SubtotalCheck:
    label: str
    expected: Decimal
    actual: Decimal
    diff: Decimal
    tolerance: Decimal
    valid: bool
```

```python
@dataclass
class EquationResult:
    assets: Decimal
    liabilities: Decimal
    equity: Decimal
    net_income: Decimal
    equation: str          # "A = P + E"
    left_side: Decimal
    right_side: Decimal
    diff: Decimal
    valid: bool
```

```python
@dataclass
class MissingAccountResult:
    expected_codes: list[str]
    found_codes: list[str]
    missing: list[str]
    coverage_pct: float
```

```python
@dataclass
class IntegrityScore:
    extraction: float      # 0-100
    classification: float  # 0-100
    hierarchy: float       # 0-100
    overall: float         # 0-100
```

```python
@dataclass
class ValidationError:
    code: str
    severity: str          # "error", "warning", "info"
    message: str
    account_code: str | None
```

---

## Confidence Engine

```python
class ConfidenceEngine(Protocol):
    def evaluate(self, ctx: DocumentContext) -> ConfidenceResult:
        """Evalúa la confianza de cada cuenta y del documento completo."""
```

```python
@dataclass
class ConfidenceResult:
    per_account: dict[str, AccountConfidence]
    global_score: float
    distribution: ConfidenceDistribution
    signals: list[ConfidenceSignal]

@dataclass
class AccountConfidence:
    account_code: str
    score: float            # 0.0 - 1.0
    signals: list[ConfidenceSignal]
    needs_review: bool

@dataclass
class ConfidenceSignal:
    source: str             # "fuzzy", "consensus", "validation", "kb_coverage"
    value: float
    weight: float
    description: str

@dataclass
class ConfidenceDistribution:
    high: int               # > 0.8
    medium: int             # 0.5 - 0.8
    low: int                # < 0.5
    unknown: int
```

---

## Coverage Engine

```python
class CoverageEngine(Protocol):
    def measure(self, ctx: DocumentContext) -> CoverageResult:
        """Mide la cobertura del documento contra la Knowledge Base."""
```

```python
@dataclass
class CoverageResult:
    kb_coverage_pct: float
    missing_codes: list[str]
    unresolved_accounts: list[AccountBalance]
    section_coverage: dict[str, SectionCoverage]
    recommendations: list[CoverageRecommendation]

@dataclass
class SectionCoverage:
    section: str
    total_accounts: int
    covered: int
    missing: int
    coverage_pct: float

@dataclass
class CoverageRecommendation:
    type: str               # "add_to_kb", "review", "auto_approve"
    account_code: str
    reason: str
    priority: str           # "high", "medium", "low"
```

---

## Human Review Workspace

```python
class ReviewWorkspace(Protocol):
    def get_candidates(self, ctx: DocumentContext) -> list[ReviewCandidate]:
        """Retorna las cuentas que requieren revisión humana."""

    def record_decision(self, candidate_id: str, decision: HumanDecision) -> None:
        """Registra una decisión humana."""

    def export_approved(self, ctx: DocumentContext) -> DocumentContext:
        """Exporta las decisiones aprobadas de vuelta al contexto."""
```

```python
@dataclass
class ReviewCandidate:
    candidate_id: str
    account: AccountBalance
    knowledge_match: KnowledgeMatch | None
    confidence: AccountConfidence | None
    coverage: SectionCoverage | None
    suggestions: list[ReviewSuggestion]
    status: ReviewStatus

class ReviewStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EDITED = "EDITED"
    SKIPPED = "SKIPPED"

@dataclass
class HumanDecision:
    candidate_id: str
    decision: ReviewStatus
    canonical_code: str | None
    canonical_name: str | None
    reviewer: str
    notes: str
    timestamp: datetime

@dataclass
class ReviewSuggestion:
    canonical_code: str
    canonical_name: str
    score: float
    source: str
```

---

## Dataset Manager

```python
class DatasetManager(Protocol):
    def scan(self, base_path: str) -> DatasetManifest:
        """Escanea directorios y construye un manifiesto."""

    def move_to(self, file_path: str, target: DatasetStage) -> None:
        """Mueve un archivo a la etapa indicada."""

    def get_stage(self, stage: DatasetStage) -> list[DatasetEntry]:
        """Retorta todos los archivos en una etapa."""
```

```python
@dataclass
class DatasetEntry:
    file_path: str
    filename: str
    stage: DatasetStage
    size: int
    hash: str
    added_at: datetime
    processed_at: datetime | None

class DatasetStage(Enum):
    INBOX = "INBOX"
    PROCESSING = "PROCESSING"
    TRAINING = "TRAINING"
    HOLDOUT = "HOLDOUT"
    ARCHIVE = "ARCHIVE"
    ERROR = "ERROR"
```
