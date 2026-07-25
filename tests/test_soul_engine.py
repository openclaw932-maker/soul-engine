"""
Soul Engine Test Suite — Phase 5
Tests the core functionality against Sol's standard
"""

import sys
sys.path.insert(0, '../src')

from soul_engine.core.db import SoulEngineDB, TaskStatus
from soul_engine.core.validation import ValidationEngine
from soul_engine.core.quality import QualityScorer, QualityDimensions
from soul_engine.core.orchestrator import SoulEngineOrchestrator

def test_database_creation():
    """Test that database initializes correctly."""
    db = SoulEngineDB(":memory:")  # In-memory for testing
    
    # Create a task
    task = db.create_task(
        user_goal="Build a landing page for SpaceBlanket",
        stakes=2,
        ambiguity=1
    )
    
    assert task.id is not None
    assert task.user_goal == "Build a landing page for SpaceBlanket"
    assert task.depth_score > 0
    print(f"✅ Task created: {task.id}, depth_score={task.depth_score:.2f}")
    
    # Add requirements
    req1 = db.add_requirement(task.id, "Create HTML structure")
    req2 = db.add_requirement(task.id, "Add CSS styling")
    
    requirements = db.get_requirements(task.id)
    assert len(requirements) == 2
    print(f"✅ Requirements added: {len(requirements)}")
    
    # Add claims
    claim1 = db.add_claim(task.id, "HTML5 is the standard", "remembered", 0.95, 1)
    claim2 = db.add_claim(task.id, "Tailwind CSS is available", "assumed", 0.60, 2)
    
    claims = db.get_claims(task.id)
    assert len(claims) == 2
    print(f"✅ Claims added: {len(claims)}")
    
    # Add evidence
    ev1 = db.add_evidence(task.id, "file://package.json", '{"dependencies": {"tailwindcss": "^3.0"}}')
    
    evidence = db.get_evidence(task.id)
    assert len(evidence) == 1
    print(f"✅ Evidence added: {len(evidence)}")
    
    return db, task

def test_validation_gates(db, task_id):
    """Test that validation gates work correctly."""
    validator = ValidationEngine(db)
    
    # Run gates before completion (should fail some)
    results = validator.run_all_gates(task_id)
    
    failed = [r for r in results if not r.passed]
    passed = [r for r in results if r.passed]
    
    print(f"✅ Gates run: {len(passed)} passed, {len(failed)} failed")
    
    for r in failed:
        print(f"   ⚠️  Failed: {r.gate_name} — {r.evidence[:60]}")
    
    assert len(results) == 7  # All 7 gates ran
    return results

def test_quality_scoring(db, task_id):
    """Test quality scoring system."""
    scorer = QualityScorer(db)
    
    dimensions = scorer.score_task(task_id)
    
    print(f"✅ Quality scored:")
    print(f"   correctness: {dimensions.correctness}")
    print(f"   requirement_coverage: {dimensions.requirement_coverage}")
    print(f"   evidence_provenance: {dimensions.evidence_provenance}")
    print(f"   weighted_score: {dimensions.weighted_score:.3f}")
    print(f"   grade: {dimensions.grade.value}")
    
    assert 0 <= dimensions.weighted_score <= 4
    return dimensions

def test_orchestrator():
    """Test the full orchestrator workflow."""
    db = SoulEngineDB(":memory:")
    orchestrator = SoulEngineOrchestrator(db)
    
    result = orchestrator.solve("Create a simple Python script that prints hello world")
    
    print(f"✅ Orchestrator result:")
    print(f"   success: {result.success}")
    print(f"   quality_score: {result.quality_score:.3f}")
    print(f"   gates_passed: {result.gates_passed}")
    print(f"   gates_failed: {result.gates_failed}")
    print(f"   execution_time: {result.execution_time:.3f}s")
    
    assert result.task_id is not None
    return result

def test_depth_scoring():
    """Test depth scoring formula from Sol."""
    from soul_engine.core.db import Task
    
    task = Task(id="test", user_goal="test", stakes=3, irreversibility=2, ambiguity=2, novelty=1, dependency_count=2, evidence_volatility=1)
    score = task.calculate_depth_score()
    
    expected = 0.25*3 + 0.20*2 + 0.15*2 + 0.15*1 + 0.15*2 + 0.10*1
    assert abs(score - expected) < 0.01
    print(f"✅ Depth score: {score:.3f} (expected: {expected:.3f})")

def test_claim_risk():
    """Test claim risk scoring."""
    from soul_engine.core.db import Claim
    from soul_engine.core.validation import ValidationEngine
    
    db = SoulEngineDB(":memory:")
    validator = ValidationEngine(db)
    
    # High-risk claim
    claim = Claim(id="c1", task_id="t1", text="test", claim_type="assumed", confidence=0.3, stakes=3)
    risk = validator.claim_risk_score(claim)
    
    print(f"✅ Claim risk score: {risk:.3f}")
    assert risk > 0

if __name__ == "__main__":
    print("=" * 60)
    print("SOUL ENGINE TEST SUITE — Phase 5")
    print("=" * 60)
    print()
    
    print("Test 1: Database Creation")
    print("-" * 40)
    db, task = test_database_creation()
    print()
    
    print("Test 2: Validation Gates")
    print("-" * 40)
    test_validation_gates(db, task.id)
    print()
    
    print("Test 3: Quality Scoring")
    print("-" * 40)
    test_quality_scoring(db, task.id)
    print()
    
    print("Test 4: Orchestrator")
    print("-" * 40)
    test_orchestrator()
    print()
    
    print("Test 5: Depth Scoring")
    print("-" * 40)
    test_depth_scoring()
    print()
    
    print("Test 6: Claim Risk")
    print("-" * 40)
    test_claim_risk()
    print()
    
    print("=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
