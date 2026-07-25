"""
Soul Engine
Local replication of GPT-5.6 Sol cognitive architecture
"""

from .core.db import SoulEngineDB, Task, TaskStatus, Requirement, Claim, Decision, PlanNode, Evidence, ExecutionJournalEntry, ErrorRecord, MemoryItem
from .core.validation import ValidationEngine, GateResult, ClaimProvenanceTracker
from .core.orchestrator import SoulEngineOrchestrator, OrchestratorResult
from .core.quality import QualityScorer, EvaluationHarness, QualityDimensions, QualityGrade

__version__ = "0.1.0"
__all__ = [
    "SoulEngineDB",
    "Task",
    "TaskStatus",
    "Requirement",
    "Claim",
    "Decision",
    "PlanNode",
    "Evidence",
    "ExecutionJournalEntry",
    "ErrorRecord",
    "MemoryItem",
    "ValidationEngine",
    "GateResult",
    "ClaimProvenanceTracker",
    "SoulEngineOrchestrator",
    "OrchestratorResult",
    "QualityScorer",
    "EvaluationHarness",
    "QualityDimensions",
    "QualityGrade",
]
