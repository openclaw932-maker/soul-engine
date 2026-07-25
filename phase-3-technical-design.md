# SOUL ENGINE — Phase 3: Technical Design Specification

**Version:** 2026-07-25
**Architecture:** Modular Python system with SQLite state management
**Target:** Replicate GPT-5.6 Sol behavior at ≥0.01% standard

---

## System Architecture

```
┌─────────────────────────────────────────────┐
│              USER INTERFACE                  │
│        (Hermes / CLI / Telegram)             │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              SOUL ENGINE                     │
│  ┌──────────────────────────────────────┐    │
│  │      ORCHESTRATOR (State Machine)   │    │
│  │   RECEIVED → PARSED → EVIDENCE     │    │
│  │   → MODELED → PLANNED → EXECUTING  │    │
│  │   → VALIDATING → SYNTHESIZING      │    │
│  │   → FINAL_GATE → DELIVERED         │    │
│  └──────────────────────────────────────┘    │
│  ┌─────────────┐  ┌──────────────────┐       │
│  │ MODEL      │  │  CONTEXT ENGINE   │       │
│  │ ROUTER     │◄─┤  (Hybrid Retrieval)│       │
│  │            │  │  • Lexical search │       │
│  │ Luna: fast │  │  • Embeddings     │       │
│  │ Terra: med │  │  • Structured     │       │
│  │ Sol: deep  │  │  • Provenance     │       │
│  └─────────────┘  └──────────────────┘       │
│  ┌─────────────┐  ┌──────────────────┐       │
│  │ TASK STATE  │  │  VALIDATION      │       │
│  │ DATABASE    │  │  ENGINE          │       │
│  │ (SQLite)    │  │  • Deterministic │       │
│  │             │  │  • Model-based   │       │
│  │ Requirements│  │  • Adversarial   │       │
│  │ Claims      │  │  • Human gates   │       │
│  │ Decisions   │  └──────────────────┘       │
│  │ Plan Nodes  │  ┌──────────────────┐       │
│  │ Evidence    │  │  MEMORY SERVICE  │       │
│  │ Execution   │  │  • Scoped facts   │       │
│  │ Journal     │  │  • Auto-invalidate│       │
│  └─────────────┘  │  • Error ledger   │       │
│                   └──────────────────┘       │
│  ┌──────────────────────────────────────┐    │
│  │        TOOL SANDBOX                  │    │
│  │   Filesystem | Shell | Browser      │    │
│  │   Read/Mutate separated             │    │
│  │   Audit logging                     │    │
│  └──────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## Core Data Model (SQLite Schema)

```sql
-- Task lifecycle
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    user_goal TEXT NOT NULL,
    task_class TEXT,  -- factual, explanation, diagnosis, code, artifact, planning, research, external, mixed
    stakes INTEGER DEFAULT 0,  -- 0-4
    irreversibility INTEGER DEFAULT 0,  -- 0-4
    ambiguity INTEGER DEFAULT 0,  -- 0-4
    novelty INTEGER DEFAULT 0,  -- 0-4
    dependency_count INTEGER DEFAULT 0,
    evidence_volatility INTEGER DEFAULT 0,
    depth_score REAL,
    status TEXT DEFAULT 'RECEIVED',  -- RECEIVED, PARSED, EVIDENCE_GATHERING, MODELED, PLANNED, EXECUTING, VALIDATING, SYNTHESIZING, FINAL_GATE, DELIVERED, BLOCKED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Atomic requirements extracted from user request
CREATE TABLE requirements (
    id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id),
    text TEXT NOT NULL,
    source_location TEXT,
    priority TEXT DEFAULT 'required',  -- required, supporting, opportunistic
    acceptance_test TEXT,
    status TEXT DEFAULT 'pending',  -- pending, met, waived, blocked
    evidence_ids TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Claims with provenance
CREATE TABLE claims (
    id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id),
    text TEXT NOT NULL,
    claim_type TEXT,  -- observed, derived, remembered, assumed, proposed
    confidence REAL DEFAULT 0.0,  -- 0.0-1.0
    stakes INTEGER DEFAULT 0,  -- 0-4
    freshness_requirement TEXT,
    evidence_ids TEXT,  -- JSON array
    verification_status TEXT DEFAULT 'unverified',  -- unverified, verified, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Decisions with rollback tracking
CREATE TABLE decisions (
    id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id),
    choice TEXT NOT NULL,
    alternatives TEXT,  -- JSON array
    premises TEXT,  -- JSON array
    evidence_ids TEXT,  -- JSON array
    confidence REAL DEFAULT 0.0,
    rollback_point TEXT,
    invalidated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Hierarchical plan nodes
CREATE TABLE plan_nodes (
    id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id),
    description TEXT NOT NULL,
    dependencies TEXT,  -- JSON array of node IDs
    expected_observation TEXT,
    validation_method TEXT,
    status TEXT DEFAULT 'pending',  -- pending, active, complete, failed, blocked
    retry_count INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Evidence store
CREATE TABLE evidence (
    id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id),
    source TEXT,  -- file_path, tool_output, computation, user_input, memory
    content TEXT NOT NULL,
    source_type TEXT,  -- file, tool, computation, user, memory
    provenance TEXT,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Execution journal
CREATE TABLE execution_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT REFERENCES tasks(id),
    action TEXT,
    command TEXT,
    output TEXT,
    exit_status INTEGER,
    affected_files TEXT,  -- JSON array
    unresolved_questions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Error ledger for learning
CREATE TABLE error_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT REFERENCES tasks(id),
    signature TEXT,  -- error pattern
    context_hash TEXT,
    root_cause TEXT,
    bad_assumption TEXT,
    fix TEXT,
    regression_test TEXT,
    general_lesson TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Memory with expiration
CREATE TABLE memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    statement TEXT NOT NULL,
    scope TEXT NOT NULL,
    source TEXT,
    observed_at TIMESTAMP,
    confidence REAL DEFAULT 0.0,
    expires_when TEXT,
    invalidated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Prompt Engineering Specification

### Layered Prompt System

**1. Requirement Extractor Prompt**
```
You are a requirement extraction system. Parse the user's request into atomic obligations.

Input: {user_request}
Context: {available_files} {prior_session}

Output format (JSON):
{
  "obligations": [
    {
      "text": "string",
      "type": "artifact | action | constraint | format | audience",
      "priority": "required | supporting | opportunistic",
      "source_location": "string or null"
    }
  ],
  "task_class": "factual | explanation | diagnosis | code | artifact | planning | research | external | mixed",
  "stakes": 0-4,
  "ambiguity_flags": ["string"]
}

Rules:
- Extract every explicit requirement
- Note action verbs: "explain" = analysis, "diagnose" = investigation, "build/fix/change" = scoped edits
- Separate desired outcome from incidental wording
- Flag high-impact ambiguity
```

**2. Evidence Planner Prompt**
```
You are an evidence planning system. For each unknown or claim, identify the cheapest authoritative way to resolve it.

Requirements: {requirements}
Known facts: {memory_items}

Output format (JSON):
{
  "evidence_plan": [
    {
      "unknown": "string",
      "resolution_strategy": "read_file | search_files | terminal | browser | computation | ask_user | memory",
      "priority": "high | medium | low",
      "estimated_cost": "seconds"
    }
  ],
  "assumptions": [
    {
      "text": "string",
      "reversibility": "high | medium | low",
      "impact_if_wrong": "high | medium | low"
    }
  ]
}
```

**3. Solution Planner Prompt**
```
You are a solution planning system. Produce milestones, dependencies, acceptance tests, rollback points, and clarification gates.

Problem model: {problem_model}
Evidence: {evidence}

Output format (JSON):
{
  "plans": [
    {
      "milestones": ["string"],
      "dependencies": ["string"],
      "acceptance_tests": ["string"],
      "rollback_points": ["string"],
      "clarification_gates": ["string"],
      "risk_score": 0-4
    }
  ],
  "recommendation": "string",
  "pre_mortem": {
    "failure_modes": ["string"],
    "early_signals": ["string"],
    "preventive_checks": ["string"]
  }
}
```

**4. Executor Prompt**
```
You are an execution system. Perform ONLY the active plan node.

Active node: {plan_node}
Available tools: {tools}
Previous observations: {evidence}

Rules:
- Perform only the active plan node
- Use the smallest coherent unit
- Return observations and changed state
- Prefer reversible mutations
- If a tool fails, report exact error, don't guess
```

**5. Critic Prompt (Adversarial)**
```
You are an adversarial critic. Assume the candidate contains a consequential defect.

Candidate: {candidate_output}
Requirements: {requirements}
Evidence: {evidence}

Find the most consequential defect. Cite evidence.
Do not rewrite. Only identify problems.

Output format (JSON):
{
  "blocking_defects": [
    {
      "severity": "critical | major | minor",
      "description": "string",
      "evidence": "string",
      "fix_suggestion": "string"
    }
  ],
  "nonblocking_issues": [...],
  "unsupported_claims": [...],
  "missed_requirements": [...]
}
```

**6. Corrector Prompt**
```
You are a correction system. Repair validated defects only.

Defects: {blocking_defects}
Original: {candidate_output}
Requirements: {requirements}

Rules:
- Repair only validated defects
- Preserve unaffected requirements
- Apply smallest coherent fix
- Re-verify after fix
```

**7. Final Writer Prompt**
```
You are a communication system. Deliver only evidence-backed outcomes.

Verified claims: {verified_claims}
Requirements met: {requirements}
Limitations: {limitations}

User model:
- estimated_expertise: {expertise_level}
- preferred_density: {density}
- need_background: {boolean}

Output rules:
- Lead with what is now true
- State verification performed
- Mention material limitations
- Give smallest useful next step
- Calibrate jargon to user level
```

---

## Validation Gate Implementations

### Gate 1: Requirement Coverage

```python
def requirement_coverage_gate(requirements: list) -> GateResult:
    for req in requirements:
        if req.status not in ('met', 'waived'):
            return GateResult(
                passed=False,
                gate_name="requirement_coverage",
                evidence=f"Requirement {req.id} unmet: {req.text}"
            )
        if req.acceptance_test and not req.test_passed:
            return GateResult(
                passed=False,
                gate_name="requirement_coverage",
                evidence=f"Acceptance test failed: {req.acceptance_test}"
            )
    return GateResult(passed=True, gate_name="requirement_coverage")
```

### Gate 2: Claim Verification

```python
def claim_verification_gate(claims: list) -> GateResult:
    for claim in claims:
        risk_score = (
            claim.stakes *
            (1 - claim.confidence) *
            provenance_multiplier(claim.claim_type) *
            freshness_multiplier(claim.freshness)
        )
        if risk_score > THRESHOLD:
            return GateResult(
                passed=False,
                gate_name="claim_verification",
                evidence=f"High-risk claim unverified: {claim.text} (risk={risk_score})"
            )
    return GateResult(passed=True, gate_name="claim_verification")
```

### Gate 3: Code/Artifact Validation

```python
def artifact_validation_gate(artifact_type: str, artifact_path: str) -> GateResult:
    validators = {
        'code': [parse, format, lint, type_check, test, build],
        'web_ui': [build, screenshot, accessibility_scan],
        'document': [render, inspect_overflow, text_extraction],
        'config': [schema_validate, dry_run, diff]
    }
    for validator in validators.get(artifact_type, []):
        result = validator(artifact_path)
        if not result.passed:
            return GateResult(passed=False, gate_name="artifact_validation", evidence=result.error)
    return GateResult(passed=True, gate_name="artifact_validation")
```

### Gate 4: Mutation Safety

```python
def mutation_safety_gate(action: Action) -> GateResult:
    if action.is_destructive or action.is_external or action.is_privacy_sensitive:
        if not action.has_user_approval:
            return GateResult(passed=False, gate_name="mutation_safety", evidence="User approval required")
    if action.target_unresolved:
        return GateResult(passed=False, gate_name="mutation_safety", evidence="Target unresolved")
    return GateResult(passed=True, gate_name="mutation_safety")
```

### Gate 5: Final Adversarial Review

```python
def adversarial_review_gate(candidate: str, requirements: list, evidence: list) -> GateResult:
    critique = run_critic(candidate, requirements, evidence)
    if critique.blocking_defects:
        return GateResult(
            passed=False,
            gate_name="adversarial_review",
            evidence=f"Blocking defects: {[d.description for d in critique.blocking_defects]}"
        )
    return GateResult(passed=True, gate_name="adversarial_review")
```

---

## Model Router Logic

```python
def select_model(task: Task) -> ModelConfig:
    """Route to appropriate model based on task characteristics."""
    
    if task.stakes <= 1 and task.ambiguity <= 1:
        # Fast, cheap tasks
        return ModelConfig(
            model="gpt-5.6-luna",
            reasoning="low",
            temperature=0.1,
            max_tokens=2000
        )
    
    elif task.stakes <= 2 and task.ambiguity <= 2:
        # Balanced everyday work
        return ModelConfig(
            model="gpt-5.6-terra",
            reasoning="medium",
            temperature=0.2,
            max_tokens=4000
        )
    
    elif task.depth_score >= 2.5:
        # Deep reasoning required
        return ModelConfig(
            model="gpt-5.6-sol",
            reasoning="high",
            temperature=0.3,
            max_tokens=8000
        )
    
    else:
        # Default: Sol with medium reasoning
        return ModelConfig(
            model="gpt-5.6-sol",
            reasoning="medium",
            temperature=0.2,
            max_tokens=4000
        )
```

---

## Quality Scoring System

```python
class QualityScore:
    def __init__(self):
        self.dimensions = {
            'correctness': 0,      # 25%
            'requirement_coverage': 0,  # 15%
            'evidence_provenance': 0,    # 15%
            'robustness': 0,       # 10%
            'safety_scope': 0,     # 10%
            'simplicity_maintainability': 0,  # 10%
            'communication': 0,      # 10%
            'efficiency': 0        # 5%
        }
        self.weights = {
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
            self.dimensions[k] * self.weights[k]
            for k in self.dimensions
        )
    
    @property
    def grade(self) -> str:
        score = self.weighted_score
        if score < 2.0: return "REJECT"
        elif score < 2.8: return "INCOMPLETE"
        elif score < 3.4: return "GOOD_ENOUGH"
        elif score < 3.8: return "EXCELLENT"
        else: return "WORLD_CLASS"
    
    def hard_gates_passed(self) -> bool:
        return (
            self.dimensions['correctness'] >= 3 and
            self.dimensions['safety_scope'] >= 3 and
            self.dimensions['requirement_coverage'] >= 3
        )
```

---

## Error Recovery Workflow

```python
async def error_recovery(task: Task, failure: Failure) -> RecoveryResult:
    """Implement Sol's 10-step correction protocol."""
    
    # 1. Stop propagation
    task.pause()
    
    # 2. State discrepancy precisely
    discrepancy = analyze_failure(failure)
    
    # 3. Classify cause
    cause = classify_cause(failure)
    
    # 4. Determine blast radius
    affected = find_dependent_conclusions(task, failure)
    
    # 5. Return to earliest invalid premise
    root = find_root_cause(task, failure)
    
    # 6. Generate alternative explanations
    alternatives = generate_alternative_diagnoses(failure)
    
    # 7. Apply smallest coherent fix
    fix = generate_minimal_fix(root, alternatives)
    
    # 8. Re-run failed check + regression
    result = await apply_and_verify(fix, failure.original_check)
    
    # 9. Update execution journal and confidence
    task.journal.append(f"Recovery applied: {fix.summary}")
    task.confidence = recalculate_confidence(task)
    
    # 10. Store in error ledger
    task.error_ledger.append(ErrorRecord(
        signature=discrepancy.signature,
        root_cause=cause,
        fix=fix,
        lesson=general_lesson(failure)
    ))
    
    return RecoveryResult(success=result.passed, task=task)
```

---

*Phase 3 complete. Design specification for Soul Engine: SQLite schema, layered prompt system, validation gates, model router, quality scoring, error recovery.*
