"""
Soul Engine — Ollama Adapter
Wraps local Ollama calls with Soul Engine architecture
Any call to Llama goes through the 10-step state machine + 7 validation gates
"""

import json
import subprocess
import sys
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Add Soul Engine to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from soul_engine.core.db import SoulEngineDB, Task, TaskStatus
from soul_engine.core.validation import ValidationEngine, ClaimProvenanceTracker
from soul_engine.core.quality import QualityScorer


@dataclass
class OllamaSoulResult:
    """Result from a Soul-Engine-wrapped Ollama call."""
    success: bool
    output: str
    quality_score: float
    gates_passed: int
    gates_failed: int
    claim_provenance: List[Dict]
    reasoning_trace: List[str]


class OllamaSoulAdapter:
    """
    Adapter that intercepts Ollama calls and applies Soul Engine architecture.
    
    Usage:
        adapter = OllamaSoulAdapter(model="llama3.2:3b")
        result = adapter.generate("Create a poster for SpaceBlanket")
    
    What it does:
        1. Parses the request into requirements
        2. Gathers evidence from memory/error ledger
        3. Plans the response with checkpoints
        4. Calls Ollama with structured prompts (not raw user input)
        5. Validates output against gates
        6. Returns scored, verified result
    """
    
    def __init__(self, model: str = "llama3.2:3b", db_path: str = "soul_engine.db"):
        self.model = model
        self.db = SoulEngineDB(db_path)
        self.validator = ValidationEngine(self.db)
        self.scorer = QualityScorer(self.db)
        self.provenance = ClaimProvenanceTracker()
    
    def generate(self, user_request: str, system_prompt: Optional[str] = None,
                 temperature: float = 0.3, **kwargs) -> OllamaSoulResult:
        """
        Main entry point. Runs the full Soul Engine pipeline on Llama.
        """
        reasoning_trace = []
        
        # === STEP 1: Create task ===
        task = self.db.create_task(
            user_goal=user_request,
            stakes=self._estimate_stakes(user_request),
            ambiguity=self._estimate_ambiguity(user_request)
        )
        reasoning_trace.append(f"[1] Task created: {task.id}, depth_score={task.depth_score:.2f}")
        
        # === STEP 2: Extract requirements ===
        requirements = self._extract_requirements(user_request)
        for req in requirements:
            self.db.add_requirement(task.id, req)
        reasoning_trace.append(f"[2] Requirements extracted: {len(requirements)}")
        
        # === STEP 3: Gather evidence ===
        evidence = self._gather_evidence(task)
        reasoning_trace.append(f"[3] Evidence gathered: {len(evidence)} items")
        
        # === STEP 4: Build structured prompt for Llama ===
        structured_prompt = self._build_structured_prompt(
            user_request=user_request,
            requirements=requirements,
            evidence=evidence,
            system_prompt=system_prompt
        )
        reasoning_trace.append("[4] Structured prompt built (layered)")
        
        # === STEP 5: Call Ollama with structured prompt ===
        raw_output = self._call_ollama(structured_prompt, temperature, **kwargs)
        reasoning_trace.append("[5] Ollama called with structured prompt")
        
        # === STEP 6: Parse claims and track provenance ===
        claims = self._extract_claims(task.id, raw_output, evidence)
        reasoning_trace.append(f"[6] Claims extracted: {len(claims)}")
        
        # === STEP 7: Validate output ===
        gate_results = self.validator.run_all_gates(task.id)
        failed = self.validator.get_failed_gates(gate_results)
        passed = [g for g in gate_results if g.passed]
        reasoning_trace.append(f"[7] Gates: {len(passed)} passed, {len(failed)} failed")
        
        # === STEP 8: Score quality ===
        dimensions = self.scorer.score_task(task.id)
        reasoning_trace.append(f"[8] Quality: {dimensions.grade.value} (score={dimensions.weighted_score:.3f})")
        
        # === STEP 9: Build provenance report ===
        provenance_report = self._build_provenance_report(claims)
        
        # === STEP 10: Deliver or flag for retry ===
        if failed and dimensions.weighted_score < 2.0:
            # Critical failure — retry with stricter prompt
            reasoning_trace.append("[10] CRITICAL: Retrying with stricter constraints")
            retry_prompt = self._build_retry_prompt(structured_prompt, failed)
            raw_output = self._call_ollama(retry_prompt, temperature=0.1, **kwargs)
            
            # Re-extract and re-validate
            claims = self._extract_claims(task.id, raw_output, evidence)
            gate_results = self.validator.run_all_gates(task.id)
            failed = self.validator.get_failed_gates(gate_results)
            passed = [g for g in gate_results if g.passed]
            dimensions = self.scorer.score_task(task.id)
        
        self.db.update_task_status(task.id, TaskStatus.DELIVERED)
        
        return OllamaSoulResult(
            success=len(failed) == 0 or dimensions.grade.value not in ["REJECT", "INCOMPLETE"],
            output=raw_output,
            quality_score=dimensions.weighted_score,
            gates_passed=len(passed),
            gates_failed=len(failed),
            claim_provenance=provenance_report,
            reasoning_trace=reasoning_trace
        )
    
    def _estimate_stakes(self, user_request: str) -> int:
        text = user_request.lower()
        if any(w in text for w in ['production', 'deploy', 'client', 'payment', 'revenue']):
            return 4
        elif any(w in text for w in ['important', 'critical', 'major']):
            return 3
        elif any(w in text for w in ['fix', 'bug', 'error']):
            return 2
        return 1
    
    def _estimate_ambiguity(self, user_request: str) -> int:
        text = user_request.lower()
        if any(w in text for w in ['maybe', 'whatever', 'something']):
            return 3
        elif any(w in text for w in ['or', 'could', 'might']):
            return 2
        return 1
    
    def _extract_requirements(self, user_request: str) -> List[str]:
        """Extract atomic requirements."""
        parts = user_request.replace(".", "|").replace(";", "|").split("|")
        requirements = [p.strip() for p in parts if len(p.strip()) > 10]
        return requirements[:5] if requirements else [user_request]
    
    def _gather_evidence(self, task: Task) -> List[Any]:
        """Gather evidence from memory and error ledger."""
        evidence = []
        
        # Check memory
        memories = self.db.get_memory(scope=f"task:{task.id}")
        for mem in memories:
            self.db.add_evidence(task.id, f"memory://{mem.id}", mem.statement, source_type="memory")
            evidence.append(mem)
        
        # Check error ledger for similar past failures
        errors = self.db.get_errors()
        for err in errors[:3]:
            self.db.add_evidence(task.id, f"error://{err.id}", 
                               f"Past error: {err.signature} — {err.general_lesson}", source_type="memory")
            evidence.append(err)
        
        return evidence
    
    def _build_structured_prompt(self, user_request: str, requirements: List[str],
                                 evidence: List[Any], system_prompt: Optional[str]) -> str:
        """Build a layered, structured prompt for Llama."""
        
        parts = []
        
        # Layer 1: System identity
        if system_prompt:
            parts.append(f"SYSTEM IDENTITY:\n{system_prompt}\n")
        else:
            parts.append("""SYSTEM IDENTITY:
You are a precise, evidence-based assistant. Every claim must be supported.
You follow a strict workflow: parse requirements → gather evidence → plan → execute → validate.
""")
        
        # Layer 2: Requirement ledger
        parts.append("REQUIREMENT LEDGER:")
        for i, req in enumerate(requirements, 1):
            parts.append(f"  {i}. {req} [REQUIRED]")
        parts.append("")
        
        # Layer 3: Evidence context
        if evidence:
            parts.append("EVIDENCE CONTEXT:")
            for ev in evidence[:5]:
                parts.append(f"  • {str(ev)[:100]}")
            parts.append("")
        
        # Layer 4: Task constraints
        parts.append("""CONSTRAINTS:
- Only answer what is asked
- Mark uncertain claims as [ASSUMED] or [UNVERIFIED]
- If evidence is insufficient, say so explicitly
- Do not hallucinate details
""")
        
        # Layer 5: User request
        parts.append(f"USER REQUEST:\n{user_request}\n")
        
        # Layer 6: Output format
        parts.append("""OUTPUT FORMAT:
1. STATE what you will do / have done
2. PROVIDE the actual output
3. TAG claims: [OBSERVED] for verified facts, [DERIVED] for logical conclusions, [ASSUMED] for gaps
4. FLAG any limitations or uncertainties
""")
        
        return "\n".join(parts)
    
    def _call_ollama(self, prompt: str, temperature: float, **kwargs) -> str:
        """Call Ollama with the structured prompt."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                **kwargs
            }
        }
        
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:11434/api/generate"],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                return f"[ERROR: Ollama call failed: {result.stderr}]"
            
            response = json.loads(result.stdout)
            return response.get("response", "[ERROR: No response field]")
            
        except Exception as e:
            return f"[ERROR: {str(e)}]"
    
    def _extract_claims(self, task_id: str, output: str, evidence: List[Any]) -> List[Any]:
        """Extract claims from output and track provenance."""
        claims = []
        
        # Simple claim extraction based on tags
        lines = output.split("\n")
        for line in lines:
            if "[OBSERVED]" in line:
                claims.append(self.db.add_claim(
                    task_id=task_id,
                    text=line.replace("[OBSERVED]", "").strip(),
                    claim_type="observed",
                    confidence=0.90,
                    stakes=1
                ))
            elif "[DERIVED]" in line:
                claims.append(self.db.add_claim(
                    task_id=task_id,
                    text=line.replace("[DERIVED]", "").strip(),
                    claim_type="derived",
                    confidence=0.70,
                    stakes=1
                ))
            elif "[ASSUMED]" in line or "[UNVERIFIED]" in line:
                claims.append(self.db.add_claim(
                    task_id=task_id,
                    text=line.replace("[ASSUMED]", "").replace("[UNVERIFIED]", "").strip(),
                    claim_type="assumed",
                    confidence=0.40,
                    stakes=2
                ))
        
        # If no explicit tags, create one claim for the whole output
        if not claims:
            claims.append(self.db.add_claim(
                task_id=task_id,
                text=output[:200],
                claim_type="assumed",
                confidence=0.50,
                stakes=2
            ))
        
        return claims
    
    def _build_provenance_report(self, claims: List[Any]) -> List[Dict]:
        """Build a report of claim provenance."""
        return [
            {
                "text": c.text[:100],
                "type": c.claim_type,
                "confidence": c.confidence,
                "stakes": c.stakes,
                "verification": c.verification_status
            }
            for c in claims
        ]
    
    def _build_retry_prompt(self, original_prompt: str, failed_gates: List[Any]) -> str:
        """Build a stricter retry prompt when validation fails."""
        gate_info = "\n".join([f"- {g.gate_name}: {g.evidence[:80]}" for g in failed_gates])
        
        return f"""{original_prompt}

=== VALIDATION RETRY ===
Previous output failed these validation gates:
{gate_info}

STRICTER RULES:
- Provide only evidence-backed statements
- If uncertain, explicitly say "I don't have enough evidence"
- Double-check every factual claim against the evidence context
- Be conservative — better to say less and be accurate
"""


# CLI entry point for direct usage
def main():
    if len(sys.argv) < 2:
        print("Usage: python ollama_soul_adapter.py 'your prompt here'")
        print("Usage: python ollama_soul_adapter.py --model llama3.2:3b 'your prompt'")
        sys.exit(1)
    
    model = "llama3.2:3b"
    prompt_idx = 1
    
    if sys.argv[1] == "--model" and len(sys.argv) > 2:
        model = sys.argv[2]
        prompt_idx = 3
    
    user_prompt = " ".join(sys.argv[prompt_idx:])
    
    adapter = OllamaSoulAdapter(model=model)
    result = adapter.generate(user_prompt)
    
    print(f"=== SOUL ENGINE RESULT ===")
    print(f"Success: {result.success}")
    print(f"Quality: {result.quality_score:.3f} ({result.gates_passed}/{result.gates_passed + result.gates_failed} gates)")
    print(f"\n=== REASONING TRACE ===")
    for step in result.reasoning_trace:
        print(f"  {step}")
    print(f"\n=== OUTPUT ===")
    print(result.output)
    print(f"\n=== CLAIM PROVENANCE ===")
    for claim in result.claim_provenance:
        print(f"  [{claim['type'].upper()}] conf={claim['confidence']:.2f} stakes={claim['stakes']} — {claim['text'][:60]}")


if __name__ == "__main__":
    main()
