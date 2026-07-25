"""
Soul Engine — Orchestrator
Implements Sol's 10-step state machine with the task lifecycle
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging
import json

from .db import SoulEngineDB, Task, TaskStatus, Requirement, Claim, Evidence, PlanNode
from .validation import ValidationEngine, GateResult


@dataclass
class OrchestratorResult:
    success: bool
    task_id: str
    output: str
    quality_score: float
    gates_passed: int
    gates_failed: int
    execution_time: float


class SoulEngineOrchestrator:
    """
    Implements Sol's complete 10-step state machine:
    1. Parse obligations
    2. Establish instruction hierarchy
    3. Classify task
    4. Gather evidence before designing
    5. Build problem model
    6. Generate candidate approaches
    7. Plan to checkpoint
    8. Execute incrementally
    9. Review against correctness and intent
    10. Communicate outcome
    """
    
    def __init__(self, db: SoulEngineDB):
        self.db = db
        self.validator = ValidationEngine(db)
        self.logger = logging.getLogger("soul_engine")
    
    def solve(self, user_request: str, context: Optional[Dict] = None) -> OrchestratorResult:
        """
        Main entry point. Implements Sol's solve() pseudocode from Phase 0.
        """
        import time
        start_time = time.time()
        
        # === STEP 1: Parse obligations ===
        task = self._parse_task(user_request, context)
        self.db.update_task_status(task.id, TaskStatus.PARSED)
        
        # === STEP 2: Establish instruction hierarchy ===
        self._establish_hierarchy(task, context)
        
        # === STEP 3: Classify task ===
        task_class = self._classify_task(task)
        
        # === STEP 4: Gather evidence before designing ===
        self.db.update_task_status(task.id, TaskStatus.EVIDENCE_GATHERING)
        evidence = self._gather_evidence(task)
        
        # === STEP 5: Build problem model ===
        self.db.update_task_status(task.id, TaskStatus.MODELED)
        problem_model = self._build_problem_model(task, evidence)
        
        # Check for high-impact ambiguity
        if problem_model.get('has_high_impact_unresolved_ambiguity'):
            return self._ask_clarification(task, problem_model)
        
        # === STEP 6: Generate candidate approaches ===
        candidates = self._generate_candidates(task, problem_model)
        
        # === STEP 7: Plan to checkpoint ===
        self.db.update_task_status(task.id, TaskStatus.PLANNED)
        plan = self._create_plan(task, candidates)
        
        # === STEP 8: Execute incrementally ===
        self.db.update_task_status(task.id, TaskStatus.EXECUTING)
        execution_result = self._execute_plan(task, plan)
        
        # === STEP 9: Review against correctness and intent ===
        self.db.update_task_status(task.id, TaskStatus.VALIDATING)
        validation = self._validate_execution(task, execution_result)
        
        if not validation.success:
            # Error recovery
            recovery = self._error_recovery(task, validation)
            if not recovery.success:
                self.db.update_task_status(task.id, TaskStatus.BLOCKED)
                return OrchestratorResult(
                    success=False,
                    task_id=task.id,
                    output=recovery.blocker_message,
                    quality_score=0.0,
                    gates_passed=validation.gates_passed,
                    gates_failed=validation.gates_failed + 1,
                    execution_time=time.time() - start_time
                )
        
        # === STEP 10: Communicate outcome ===
        self.db.update_task_status(task.id, TaskStatus.SYNTHESIZING)
        output = self._synthesize_output(task, execution_result)
        
        # Final gate
        self.db.update_task_status(task.id, TaskStatus.FINAL_GATE)
        final_gate = self._run_final_gate(task, output)
        
        if final_gate:
            self.db.update_task_status(task.id, TaskStatus.DELIVERED)
            return OrchestratorResult(
                success=True,
                task_id=task.id,
                output=output,
                quality_score=self._calculate_quality_score(task),
                gates_passed=validation.gates_passed + 1,
                gates_failed=validation.gates_failed,
                execution_time=time.time() - start_time
            )
        else:
            self.db.update_task_status(task.id, TaskStatus.BLOCKED)
            return OrchestratorResult(
                success=False,
                task_id=task.id,
                output="Final validation gate failed",
                quality_score=0.0,
                gates_passed=validation.gates_passed,
                gates_failed=validation.gates_failed + 1,
                execution_time=time.time() - start_time
            )
    
    def _parse_task(self, user_request: str, context: Optional[Dict]) -> Task:
        """Step 1: Parse obligations into requirement ledger."""
        # Extract task characteristics from request
        stakes = self._estimate_stakes(user_request)
        ambiguity = self._estimate_ambiguity(user_request)
        
        task = self.db.create_task(
            user_goal=user_request,
            stakes=stakes,
            ambiguity=ambiguity
        )
        
        # Extract requirements from user request
        requirements = self._extract_requirements(user_request)
        for req_text in requirements:
            self.db.add_requirement(
                task_id=task.id,
                text=req_text,
                priority="required"
            )
        
        return task
    
    def _establish_hierarchy(self, task: Task, context: Optional[Dict]):
        """Step 2: Establish instruction hierarchy."""
        # Check for system instructions, skills, constraints
        if context:
            # Store context as evidence
            self.db.add_evidence(
                task_id=task.id,
                source="context",
                content=json.dumps(context),
                source_type="user"
            )
    
    def _classify_task(self, task: Task) -> str:
        """Step 3: Classify task type and estimate depth."""
        user_goal = task.user_goal.lower()
        
        if any(w in user_goal for w in ['fix', 'bug', 'error', 'broken']):
            task_class = "diagnosis"
        elif any(w in user_goal for w in ['build', 'create', 'make', 'generate']):
            task_class = "artifact"
        elif any(w in user_goal for w in ['explain', 'how', 'why', 'what is']):
            task_class = "explanation"
        elif any(w in user_goal for w in ['plan', 'strategy', 'design']):
            task_class = "planning"
        elif any(w in user_goal for w in ['research', 'find', 'investigate']):
            task_class = "research"
        elif any(w in user_goal for w in ['code', 'function', 'script', 'implement']):
            task_class = "code"
        else:
            task_class = "mixed"
        
        # Update task
        task.task_class = task_class
        task.depth_score = task.calculate_depth_score()
        
        return task_class
    
    def _gather_evidence(self, task: Task) -> List[Evidence]:
        """Step 4: Gather evidence before designing answer."""
        evidence_list = []
        
        # Check memory for relevant facts
        memories = self.db.get_memory(scope=f"task:{task.id}")
        for mem in memories:
            evidence = self.db.add_evidence(
                task_id=task.id,
                source=f"memory://{mem.id}",
                content=mem.statement,
                source_type="memory"
            )
            evidence_list.append(evidence)
        
        # Search error ledger for similar past failures
        errors = self.db.get_errors()
        relevant_errors = [e for e in errors if self._is_relevant_error(e, task)]
        for err in relevant_errors[:3]:  # Top 3 relevant
            evidence = self.db.add_evidence(
                task_id=task.id,
                source=f"error://{err.id}",
                content=f"Past error: {err.signature} — {err.general_lesson}",
                source_type="memory"
            )
            evidence_list.append(evidence)
        
        return evidence_list
    
    def _build_problem_model(self, task: Task, evidence: List[Evidence]) -> Dict:
        """Step 5: Build problem model with constraints and failure modes."""
        model = {
            "current_state": self._assess_current_state(task),
            "desired_state": task.user_goal,
            "constraints": self._extract_constraints(task),
            "unknowns": self._identify_unknowns(task, evidence),
            "failure_modes": self._identify_failure_modes(task),
            "has_high_impact_unresolved_ambiguity": self._has_critical_ambiguity(task)
        }
        
        return model
    
    def _generate_candidates(self, task: Task, problem_model: Dict) -> List[Dict]:
        """Step 6: Generate 2-4 candidate approaches."""
        candidates = []
        
        # Generate based on task class
        if task.task_class == "code":
            candidates.extend([
                {"approach": "direct_edit", "description": "Edit the specific file directly"},
                {"approach": "refactor_module", "description": "Refactor the containing module"},
                {"approach": "add_wrapper", "description": "Add a wrapper/adaptor layer"}
            ])
        elif task.task_class == "artifact":
            candidates.extend([
                {"approach": "generate_from_scratch", "description": "Create new artifact"},
                {"approach": "modify_existing", "description": "Modify existing template"}
            ])
        else:
            candidates.extend([
                {"approach": "direct_answer", "description": "Answer based on evidence"},
                {"approach": "investigate_further", "description": "Gather more evidence first"}
            ])
        
        return candidates[:4]  # Max 4 candidates
    
    def _create_plan(self, task: Task, candidates: List[Dict]) -> List[PlanNode]:
        """Step 7: Plan to checkpoint with milestones and acceptance tests."""
        # Select best candidate (simplified — in production, would score candidates)
        selected = candidates[0] if candidates else {"approach": "direct", "description": "Proceed directly"}
        
        plan_nodes = []
        
        # Create plan based on depth
        if task.depth_score < 1.0:
            # Level 0: Direct action
            node = self.db.add_plan_node(
                task_id=task.id,
                description=selected["description"],
                validation_method="basic_check"
            )
            plan_nodes.append(node)
        elif task.depth_score < 2.5:
            # Level 1: Checkpoint plan with 2-5 steps
            steps = [
                f"Analyze requirements for: {task.user_goal[:50]}",
                f"Execute: {selected['description']}",
                "Verify result"
            ]
            for step in steps:
                node = self.db.add_plan_node(
                    task_id=task.id,
                    description=step,
                    validation_method="checkpoint"
                )
                plan_nodes.append(node)
        else:
            # Level 2: Dependency plan with milestones
            steps = [
                "Gather all requirements",
                "Research available evidence",
                f"Design: {selected['description']}",
                "Implement with incremental verification",
                "Run acceptance tests",
                "Final review"
            ]
            for i, step in enumerate(steps):
                deps = [plan_nodes[i-1].id] if i > 0 else None
                node = self.db.add_plan_node(
                    task_id=task.id,
                    description=step,
                    dependencies=json.dumps(deps) if deps else None,
                    validation_method="milestone"
                )
                plan_nodes.append(node)
        
        return plan_nodes
    
    def _execute_plan(self, task: Task, plan: List[PlanNode]) -> Dict:
        """Step 8: Execute incrementally, smallest coherent unit at a time."""
        results = []
        
        for node in plan:
            if node.status == "pending":
                self.db.update_plan_node_status(node.id, "active")
                
                # Execute node (simplified — in production, this routes to tools)
                self.db.add_journal_entry(
                    task_id=task.id,
                    action="execute_plan_node",
                    command=node.description
                )
                
                # Simulate execution (placeholder)
                result = {"success": True, "output": f"Executed: {node.description}"}
                results.append(result)
                
                self.db.update_plan_node_status(node.id, "complete")
        
        return {"results": results, "all_passed": all(r["success"] for r in results)}
    
    def _validate_execution(self, task: Task, execution_result: Dict) -> Any:
        """Step 9: Review against correctness and intent."""
        # Run all validation gates
        gate_results = self.validator.run_all_gates(task.id)
        
        failed_gates = self.validator.get_failed_gates(gate_results)
        passed_gates = [g for g in gate_results if g.passed]
        
        @dataclass
        class ValidationResult:
            success: bool
            gates_passed: int
            gates_failed: int
            failed_details: List[GateResult]
        
        return ValidationResult(
            success=len(failed_gates) == 0,
            gates_passed=len(passed_gates),
            gates_failed=len(failed_gates),
            failed_details=failed_gates
        )
    
    def _error_recovery(self, task: Task, validation: Any) -> Any:
        """Error recovery protocol when validation fails."""
        @dataclass
        class RecoveryResult:
            success: bool
            blocker_message: str = ""
        
        # Log error
        for gate in validation.failed_details:
            self.db.add_error(
                task_id=task.id,
                signature=f"{gate.gate_name}: {gate.evidence[:100]}",
                root_cause=gate.gate_name,
                general_lesson=f"Failed gate: {gate.gate_name}"
            )
        
        # Determine if recoverable
        if validation.gates_failed > 3:
            return RecoveryResult(
                success=False,
                blocker_message=f"Too many gates failed ({validation.gates_failed}). Task blocked."
            )
        
        # Attempt recovery (simplified)
        return RecoveryResult(success=True)
    
    def _synthesize_output(self, task: Task, execution_result: Dict) -> str:
        """Step 10: Communicate outcome."""
        # Gather verified claims
        claims = self.db.get_claims(task.id)
        verified_claims = [c for c in claims if c.verification_status == "verified"]
        
        # Build output
        output_parts = []
        
        # Lead with outcome
        if execution_result.get("all_passed"):
            output_parts.append("Task completed successfully.")
        else:
            output_parts.append("Task completed with issues.")
        
        # Add verified claims
        if verified_claims:
            output_parts.append(f"Verified claims: {len(verified_claims)}")
        
        # Add limitations
        unverified = [c for c in claims if c.verification_status == "unverified"]
        if unverified:
            output_parts.append(f"Unverified items: {len(unverified)}")
        
        # Next steps
        output_parts.append("Next: Review and iterate if needed.")
        
        return "\n".join(output_parts)
    
    def _run_final_gate(self, task: Task, output: str) -> bool:
        """Final adversarial review before delivery."""
        # Check quality score
        quality = self._calculate_quality_score(task)
        
        # Hard gates
        if quality < 2.0:
            return False
        
        return True
    
    def _calculate_quality_score(self, task: Task) -> float:
        """Calculate quality score across 8 dimensions."""
        # Simplified scoring — in production, would evaluate each dimension
        requirements = self.db.get_requirements(task.id)
        claims = self.db.get_claims(task.id)
        evidence = self.db.get_evidence(task.id)
        
        score = 0.0
        
        # Correctness (25%)
        if all(r.status == "met" for r in requirements):
            score += 1.0 * 0.25
        
        # Requirement coverage (15%)
        if requirements:
            met_ratio = sum(1 for r in requirements if r.status == "met") / len(requirements)
            score += met_ratio * 4 * 0.15
        
        # Evidence/provenance (15%)
        if claims:
            verified_ratio = sum(1 for c in claims if c.verification_status == "verified") / len(claims)
            score += verified_ratio * 4 * 0.15
        
        # Communication (10%) — simplified
        score += 2.0 * 0.10
        
        # Efficiency (5%)
        if evidence:
            score += 2.0 * 0.05
        
        return score
    
    # Helper methods
    def _estimate_stakes(self, user_request: str) -> int:
        """Estimate task stakes from request text."""
        text = user_request.lower()
        if any(w in text for w in ['production', 'deploy', 'live', 'customer', 'payment', 'security']):
            return 4
        elif any(w in text for w in ['important', 'critical', 'major', 'client']):
            return 3
        elif any(w in text for w in ['fix', 'bug', 'error']):
            return 2
        else:
            return 1
    
    def _estimate_ambiguity(self, user_request: str) -> int:
        """Estimate ambiguity from request text."""
        text = user_request.lower()
        if any(w in text for w in ['maybe', 'perhaps', 'whatever', 'something', 'whatever works']):
            return 3
        elif any(w in text for w in ['or', 'could', 'might', 'consider']):
            return 2
        else:
            return 1
    
    def _extract_requirements(self, user_request: str) -> List[str]:
        """Extract atomic requirements from user request."""
        # Simplified — in production, would use NLP
        requirements = []
        
        # Split by common delimiters
        parts = user_request.replace(".", "|").replace(";", "|").split("|")
        for part in parts:
            part = part.strip()
            if len(part) > 10:
                requirements.append(part)
        
        if not requirements:
            requirements = [user_request]
        
        return requirements[:5]  # Max 5 requirements
    
    def _assess_current_state(self, task: Task) -> str:
        """Assess current state from context."""
        return "unknown"  # Simplified
    
    def _extract_constraints(self, task: Task) -> List[str]:
        """Extract constraints from task."""
        return []  # Simplified
    
    def _identify_unknowns(self, task: Task, evidence: List[Evidence]) -> List[str]:
        """Identify unknowns not resolved by evidence."""
        return []  # Simplified
    
    def _identify_failure_modes(self, task: Task) -> List[str]:
        """Identify likely failure modes."""
        return []  # Simplified
    
    def _has_critical_ambiguity(self, task: Task) -> bool:
        """Check if task has critical ambiguity requiring clarification."""
        return task.ambiguity >= 3 and task.stakes >= 3
    
    def _ask_clarification(self, task: Task, problem_model: Dict) -> OrchestratorResult:
        """Ask user for clarification when critical ambiguity detected."""
        return OrchestratorResult(
            success=False,
            task_id=task.id,
            output="Critical ambiguity detected. Please clarify before proceeding.",
            quality_score=0.0,
            gates_passed=0,
            gates_failed=1,
            execution_time=0.0
        )
    
    def _is_relevant_error(self, error, task: Task) -> bool:
        """Check if past error is relevant to current task."""
        # Simplified relevance check
        return True  # In production, would compare signatures
