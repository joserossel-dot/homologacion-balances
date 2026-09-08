"""Adaptadores locales iniciales para los contratos de persistencia."""

from .files import FileDocumentRepository, FileReportRepository
from .json_knowledge import JsonKnowledgeRepository
from .legacy_neon import LegacyNeonKnowledgeAdapter
from .process_service import LocalProcessPersistenceService
from .reconciliation import LocalRuntimeReconciler
from .sqlite_operational import SqliteOperationalRepository

__all__ = [
    "FileDocumentRepository",
    "FileReportRepository",
    "JsonKnowledgeRepository",
    "LegacyNeonKnowledgeAdapter",
    "LocalProcessPersistenceService",
    "LocalRuntimeReconciler",
    "SqliteOperationalRepository",
]
