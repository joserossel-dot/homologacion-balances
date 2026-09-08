"""Contratos de persistencia y clientes remotos del dominio."""

from .audit import AuditEvent, LocalAuditRepository
from .documents import DocumentRecord, LocalDocumentRepository
from .executions import ExecutionRecord, LocalExecutionRepository
from .knowledge import LocalKnowledgeRepository, ValidationDecision
from .identity import (
    AuthenticatedActor,
    AuthenticationRequest,
    AuthenticationRequired,
    AuthorizationDenied,
    DenyAllIdentityProvider,
    IdentityProvider,
    IdentityRole,
    audit_event_for_actor,
    require_role,
)
from .remote import (
    LicenseClient,
    LicenseGrant,
    MasterBundleManifest,
    MasterDataClient,
    TelemetryClient,
    TelemetryEvent,
)
from .reports import LocalReportRepository, ReportRecord
from .processes import (
    LocalProcessPersistence,
    PersistedProcess,
    ProcessPersistenceError,
    ProcessScope,
)
from .promotions import (
    PromotionOutcomeRecord,
    PromotionOutcomeStatus,
    PromotionPolicyRecord,
    PromotionPolicyRepository,
)
from .users import LocalUserRepository, UserRecord

__all__ = [
    "AuditEvent",
    "AuthenticatedActor",
    "AuthenticationRequest",
    "AuthenticationRequired",
    "AuthorizationDenied",
    "DenyAllIdentityProvider",
    "DocumentRecord",
    "ExecutionRecord",
    "LicenseClient",
    "LicenseGrant",
    "IdentityProvider",
    "IdentityRole",
    "LocalAuditRepository",
    "LocalDocumentRepository",
    "LocalExecutionRepository",
    "LocalKnowledgeRepository",
    "LocalProcessPersistence",
    "LocalReportRepository",
    "LocalUserRepository",
    "MasterBundleManifest",
    "MasterDataClient",
    "PromotionPolicyRecord",
    "PromotionOutcomeRecord",
    "PromotionOutcomeStatus",
    "PromotionPolicyRepository",
    "PersistedProcess",
    "ProcessPersistenceError",
    "ProcessScope",
    "ReportRecord",
    "TelemetryClient",
    "TelemetryEvent",
    "UserRecord",
    "ValidationDecision",
    "audit_event_for_actor",
    "require_role",
]
