"""
Soul Engine — Quality Scoring System
Implements Sol's 8-dimension quality rubric
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class QualityGrade(Enum):
    REJECT = "REJECT"
    INCOMPLETE = "INCOMPLETE"
    GOOD_ENOUGH = "GOOD_ENOUGH"
    EXCELLENT = "EXCELLENT"
    WORLD_CLASS = "WORLD_CLASS"


@dataclass
class QualityDimensions:
    """8 dimensions of quality, scored 0-4 each."""
    correctness: float = 0.0           # 25% weight
    requirement_coverage: float = 0.0  # 15% weight
    evidence_provenance: float = 0.0   # 15% weight
    robustness: float = 0.0            # 10% weight
    safety_scope: float = 0.0          # 10% weight
    simplicity_maintainability: float = 0.0  # 10% weight
    communication: float = 0.0         # 10% weight
    efficiency: float = 0.0            # 5% weight
    
    WEIGHTS = {
        'correctness': 0.25,
        'requirement_coverage': 0.15,
        'evidence_provenance': 0.15,
        'robustness': 0.10,
        'safety_scope': 0.10,
        'simplicity_maintainability': 0.10,
        'communication': 0.10,
        'efficiency': 0.05
    }
    
    @property
    def weighted_score(self) -> float:
        return sum(
            getattr(self, dim) * weight
            for dim, weight in self.WEIGHTS.items()
        )
    
    @property
    def grade(self) -> QualityGrade:
        score = self.weighted_score
        if score < 2.0:
            return QualityGrade.REJECT
        elif score < 2.8:
            return QualityGrade.INCOMPLETE
        elif score < 3.4:
            return QualityGrade.GOOD_ENOUGH
        elif score < 3.8:
            return QualityGrade.EXCELLENT
        else:
            return QualityGrade.WORLD_CLASS
    
    def hard_gates_passed(self) -> bool:
        """Hard gates that override the average."""
        return (
            self.correctness >= 3.0 and
            self.safety_scope >= 3.0 and
            self.requirement_coverage >= 3.0
        )
    
    def to_dict(self) -> Dict:
        return {
            'dimensions': {
                'correctness': self.correctness,
                'requirement_coverage': self.requirement_coverage,
                'evidence_provenance': self.evidence_provenance,
                'robustness': self.robustness,
                'safety_scope': self.safety_scope,
                'simplicity_maintainability': self.simplicity_maintainability,
                'communication': self.communication,
                'efficiency': self.efficiency
            },
            'weighted_score': round(self.weighted_score, 3),
            'grade': self.grade.value,
            'hard_gates_passed': self.hard_gates_passed()
        }


class QualityScorer:
    """Score task output against Sol's quality rubric."""
    
    def __init__(self, db):
        self.db = db
    
    def score_task(self, task_id: str) -> QualityDimensions:
        """Score a completed task across all 8 dimensions."""
        task = self.db.get_task(task_id)
        requirements = self.db.get_requirements(task_id)
        claims = self.db.get_claims(task_id)
        evidence = self.db.get_evidence(task_id)
        journal = self.db.get_journal(task_id)
        
        dimensions = QualityDimensions()
        
        # 1. Correctness (25%)
        dimensions.correctness = self._score_correctness(task, claims, journal)
        
        # 2. Requirement coverage (15%)
        dimensions.requirement_coverage = self._score_requirement_coverage(requirements)
        
        # 3. Evidence/provenance (15%)
        dimensions.evidence_provenance = self._score_evidence_provenance(claims, evidence)
        
        # 4. Robustness (10%)
        dimensions.robustness = self._score_robustness(task, claims)
        
        # 5. Safety/scope (10%)
        dimensions.safety_scope = self._score_safety_scope(task, journal)
        
        # 6. Simplicity/maintainability (10%)
        dimensions.simplicity_maintainability = self._score_simplicity(task)
        
        # 7. Communication (10%)
        dimensions.communication = self._score_communication(task)
        
        # 8. Efficiency (5%)
        dimensions.efficiency = self._score_efficiency(task, journal)
        
        return dimensions
    
    def _score_correctness(self, task, claims, journal) -> float:
        """Score correctness: verified claims, successful executions."""
        if not claims:
            return 2.0  # Neutral
        
        verified = sum(1 for c in claims if c.verification_status == "verified")
        ratio = verified / len(claims)
        
        # Check journal for failures
        failures = sum(1 for j in journal if j.exit_status != 0 and j.exit_status is not None)
        
        if ratio >= 0.9 and failures == 0:
            return 4.0
        elif ratio >= 0.7:
            return 3.0
        elif ratio >= 0.5:
            return 2.0
        else:
            return 1.0
    
    def _score_requirement_coverage(self, requirements) -> float:
        """Score requirement coverage: all requirements met?"""
        if not requirements:
            return 2.0  # Neutral
        
        met = sum(1 for r in requirements if r.status == "met")
        ratio = met / len(requirements)
        
        if ratio >= 0.95:
            return 4.0
        elif ratio >= 0.8:
            return 3.0
        elif ratio >= 0.6:
            return 2.0
        else:
            return 1.0
    
    def _score_evidence_provenance(self, claims, evidence) -> float:
        """Score evidence/provenance: load-bearing claims directly verified."""
        if not claims:
            return 2.0
        
        high_stakes_claims = [c for c in claims if c.stakes >= 2]
        if not high_stakes_claims:
            return 3.0  # No high-stakes claims to verify
        
        verified_high_stakes = sum(
            1 for c in high_stakes_claims 
            if c.verification_status == "verified" and c.claim_type == "observed"
        )
        ratio = verified_high_stakes / len(high_stakes_claims)
        
        if ratio >= 0.9:
            return 4.0
        elif ratio >= 0.7:
            return 3.0
        elif ratio >= 0.5:
            return 2.0
        else:
            return 1.0
    
    def _score_robustness(self, task, claims) -> float:
        """Score robustness: edge cases addressed."""
        # Simplified — would check for error handling, edge cases
        return 2.5  # Neutral
    
    def _score_safety_scope(self, task, journal) -> float:
        """Score safety/scope: exact scope, reversible, audited."""
        # Check for destructive actions
        destructive = False
        for entry in journal:
            if entry.command and any(kw in entry.command.lower() for kw in ['rm -rf', 'drop', 'truncate']):
                destructive = True
                break
        
        if destructive and task.stakes >= 3:
            return 1.0  # Dangerous
        elif destructive:
            return 2.0
        else:
            return 3.5  # Generally safe
    
    def _score_simplicity(self, task) -> float:
        """Score simplicity/maintainability."""
        # Simplified — would analyze complexity of solution
        return 2.5  # Neutral
    
    def _score_communication(self, task) -> float:
        """Score communication: concise, calibrated, reproducible."""
        # Simplified — would analyze output text
        return 3.0  # Good
    
    def _score_efficiency(self, task, journal) -> float:
        """Score efficiency: evidence gain per action."""
        if not journal:
            return 2.0
        
        # Check if there were redundant actions
        actions = [j.action for j in journal]
        unique_actions = len(set(actions))
        total_actions = len(actions)
        
        if total_actions == 0:
            return 2.0
        
        ratio = unique_actions / total_actions
        if ratio >= 0.9:
            return 4.0
        elif ratio >= 0.7:
            return 3.0
        else:
            return 2.0


class EvaluationHarness:
    """Run evaluation suite and track performance over time."""
    
    def __init__(self, db):
        self.db = db
        self.scorer = QualityScorer(db)
    
    def evaluate_task(self, task_id: str) -> Dict:
        """Evaluate a single task."""
        dimensions = self.scorer.score_task(task_id)
        
        return {
            'task_id': task_id,
            'dimensions': dimensions.to_dict(),
            'passed': dimensions.hard_gates_passed() and dimensions.grade != QualityGrade.REJECT
        }
    
    def benchmark_report(self, task_ids: List[str]) -> Dict:
        """Generate benchmark report across multiple tasks."""
        results = [self.evaluate_task(tid) for tid in task_ids]
        
        scores = [r['dimensions']['weighted_score'] for r in results]
        grades = [r['dimensions']['grade'] for r in results]
        
        return {
            'total_tasks': len(results),
            'average_score': sum(scores) / len(scores) if scores else 0,
            'min_score': min(scores) if scores else 0,
            'max_score': max(scores) if scores else 0,
            'grade_distribution': {
                'REJECT': grades.count('REJECT'),
                'INCOMPLETE': grades.count('INCOMPLETE'),
                'GOOD_ENOUGH': grades.count('GOOD_ENOUGH'),
                'EXCELLENT': grades.count('EXCELLENT'),
                'WORLD_CLASS': grades.count('WORLD_CLASS')
            },
            'pass_rate': sum(1 for r in results if r['passed']) / len(results) if results else 0
        }
