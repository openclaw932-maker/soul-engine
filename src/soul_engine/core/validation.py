"""
Soul Engine — Validation Gates
Deterministic, software-enforced gates (not prompt-dependent)
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum
import json


class GateResult:
    def __init__(self, passed: bool, gate_name: str, evidence: str = "", score: float = 0.0):
        self.passed = passed
        self.gate_name = gate_name
        self.evidence = evidence
        self.score = score
    
    def __bool__(self):
        return self.passed
    
    def __repr__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"Gate({self.gate_name}): {status} — {self.evidence[:100]}"


class ClaimProvenance(Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    REMEMBERED = "remembered"
    ASSUMED = "assumed"
    PROPOSED = "proposed"


class ValidationEngine:
    """Implements Sol's 7 validation gates as deterministic software."""
    
    def __init__(self, db):
        self.db = db
        self.THRESHOLD = 3.0  # Configurable risk threshold
    
    def run_all_gates(self, task_id: str) -> List[GateResult]:
        """Run all 7 gates for a task. Return list of results."""
        results = []
        
        results.append(self.gate_1_instruction_compliance(task_id))
        results.append(self.gate_2_evidence_integrity(task_id))
        results.append(self.gate_3_correctness(task_id))
        results.append(self.gate_4_completeness(task_id))
        results.append(self.gate_5_consistency(task_id))
        results.append(self.gate_6_risk(task_id))
        results.append(self.gate_7_communication_quality(task_id))
        
        return results
    
    def gate_1_instruction_compliance(self, task_id: str) -> GateResult:
        """Gate 1: Did the response answer the actual request?"""
        task = self.db.get_task(task_id)
        requirements = self.db.get_requirements(task_id)
        
        if not requirements:
            return GateResult(
                passed=False,
                gate_name="instruction_compliance",
                evidence="No requirements extracted from user request"
            )
        
        # Check if task has progressed beyond RECEIVED
        if task.status.value == "RECEIVED":
            return GateResult(
                passed=False,
                gate_name="instruction_compliance",
                evidence="Task has not been parsed into requirements"
            )
        
        return GateResult(passed=True, gate_name="instruction_compliance")
    
    def gate_2_evidence_integrity(self, task_id: str) -> GateResult:
        """Gate 2: Which claims came from files, tools, sources, computation, memory?"""
        claims = self.db.get_claims(task_id)
        evidence = self.db.get_evidence(task_id)
        
        if not claims:
            return GateResult(passed=True, gate_name="evidence_integrity")
        
        unverified_high_stakes = []
        for claim in claims:
            if claim.stakes >= 2 and claim.verification_status != "verified":
                unverified_high_stakes.append(claim.text)
        
        if unverified_high_stakes:
            return GateResult(
                passed=False,
                gate_name="evidence_integrity",
                evidence=f"High-stakes claims unverified: {unverified_high_stakes[:3]}"
            )
        
        return GateResult(passed=True, gate_name="evidence_integrity")
    
    def gate_3_correctness(self, task_id: str) -> GateResult:
        """Gate 3: Are calculations recomputed? Does code parse/compile/test/execute?"""
        # This gate is task-specific. For code tasks, check compilation/tests.
        # For factual tasks, check claim verification.
        # For now, delegate to task class.
        
        task = self.db.get_task(task_id)
        journal = self.db.get_journal(task_id)
        
        # Check for failed executions in journal
        failed_executions = [j for j in journal if j.exit_status != 0 and j.exit_status is not None]
        
        if failed_executions:
            return GateResult(
                passed=False,
                gate_name="correctness",
                evidence=f"Failed executions: {len(failed_executions)}"
            )
        
        return GateResult(passed=True, gate_name="correctness")
    
    def gate_4_completeness(self, task_id: str) -> GateResult:
        """Gate 4: Every requirement-ledger item addressed?"""
        requirements = self.db.get_requirements(task_id)
        
        if not requirements:
            return GateResult(passed=True, gate_name="completeness")
        
        unmet = [r for r in requirements if r.status not in ("met", "waived")]
        
        if unmet:
            return GateResult(
                passed=False,
                gate_name="completeness",
                evidence=f"Requirements unmet: {len(unmet)}"
            )
        
        return GateResult(passed=True, gate_name="completeness")
    
    def gate_5_consistency(self, task_id: str) -> GateResult:
        """Gate 5: Claims don't contradict each other?"""
        claims = self.db.get_claims(task_id)
        
        if len(claims) < 2:
            return GateResult(passed=True, gate_name="consistency")
        
        # Check for contradictory claims (simplified)
        # In production, this would use NLP contradiction detection
        contradictions = self._detect_contradictions(claims)
        
        if contradictions:
            return GateResult(
                passed=False,
                gate_name="consistency",
                evidence=f"Contradictions found: {contradictions[:3]}"
            )
        
        return GateResult(passed=True, gate_name="consistency")
    
    def gate_6_risk(self, task_id: str) -> GateResult:
        """Gate 6: Any destructive, privacy-sensitive, financial, legal, externally visible action?"""
        task = self.db.get_task(task_id)
        journal = self.db.get_journal(task_id)
        
        # Check for destructive actions
        destructive_keywords = ["rm -rf", "delete", "drop", "truncate", "destroy"]
        risky_actions = []
        
        for entry in journal:
            if entry.command:
                for keyword in destructive_keywords:
                    if keyword in entry.command.lower():
                        risky_actions.append(f"{entry.action}: {entry.command[:50]}")
        
        if risky_actions and task.stakes >= 3:
            return GateResult(
                passed=False,
                gate_name="risk",
                evidence=f"High-stakes destructive actions: {risky_actions[:3]}"
            )
        
        return GateResult(passed=True, gate_name="risk")
    
    def gate_7_communication_quality(self, task_id: str) -> GateResult:
        """Gate 7: Lead with outcome? Calibrated to user? Not overstating verification?"""
        task = self.db.get_task(task_id)
        
        # Check if task has been delivered
        if task.status.value != "DELIVERED":
            return GateResult(
                passed=False,
                gate_name="communication_quality",
                evidence="Task not yet delivered"
            )
        
        # In production, this would analyze actual output text
        # For now, check that execution journal exists
        journal = self.db.get_journal(task_id)
        if not journal:
            return GateResult(
                passed=False,
                gate_name="communication_quality",
                evidence="No execution journal — cannot verify outcome was communicated"
            )
        
        return GateResult(passed=True, gate_name="communication_quality")
    
    def _detect_contradictions(self, claims: list) -> List[str]:
        """Detect simple contradictions between claims."""
        contradictions = []
        
        # Check for opposite boolean claims
        for i, c1 in enumerate(claims):
            for c2 in claims[i+1:]:
                text1 = c1.text.lower()
                text2 = c2.text.lower()
                
                # Simple contradiction patterns
                if ("is true" in text1 and "is false" in text2) or \
                   ("is false" in text1 and "is true" in text2):
                    contradictions.append(f"'{c1.text[:50]}' vs '{c2.text[:50]}'")
                
                if ("can" in text1 and "cannot" in text2) or \
                   ("cannot" in text1 and "can" in text2):
                    contradictions.append(f"'{c1.text[:50]}' vs '{c2.text[:50]}'")
        
        return contradictions
    
    def claim_risk_score(self, claim) -> float:
        """Calculate risk score for a claim."""
        multipliers = {
            "observed": 0.5,
            "derived": 0.7,
            "remembered": 1.5,
            "assumed": 2.0,
            "proposed": 1.8
        }
        
        provenance_mult = multipliers.get(claim.claim_type, 1.0)
        freshness_mult = 1.0  # Default, could be calculated from observed_at
        
        return claim.stakes * (1 - claim.confidence) * provenance_mult * freshness_mult
    
    def get_failed_gates(self, results: List[GateResult]) -> List[GateResult]:
        """Return only failed gates."""
        return [r for r in results if not r.passed]


class ClaimProvenanceTracker:
    """Track and classify claim provenance."""
    
    @staticmethod
    def classify_claim(text: str, source: str, confidence: float = 0.5) -> str:
        """Classify a claim based on its source."""
        if source.startswith("file://") or source.startswith("tool://"):
            return "observed"
        elif source.startswith("computation://"):
            return "derived"
        elif source.startswith("memory://"):
            return "remembered"
        elif source.startswith("user://"):
            return "observed"
        elif confidence < 0.5:
            return "assumed"
        else:
            return "proposed"
    
    @staticmethod
    def get_confidence_guidance(claim_type: str, confidence: float) -> str:
        """Return guidance based on claim type and confidence."""
        if claim_type == "observed" and confidence > 0.90:
            return "Answer directly"
        elif claim_type == "remembered" and confidence > 0.90:
            return "Answer with qualification"
        elif confidence > 0.70:
            return "Answer with qualification or cheap check"
        elif confidence > 0.40:
            return "Investigate before asserting"
        else:
            return "Do not present as fact; ask, browse, test, or omit"
