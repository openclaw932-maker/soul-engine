# Soul Engine Phase 0 Review

## Verdict

The current repository is a useful **schema-and-scaffolding prototype**, not yet
an operational implementation of the blueprint. It names most of the right
concepts, but its central loop does not gather real evidence, execute real
actions, repair failures, or prove completion. The most dangerous failure mode
is therefore epistemic: placeholder success can be mistaken for verified work.

The generated module at
`src/soul_engine/prompts/layered_prompts.py` supplies the missing prompt layers,
a risk-adjusted model router, an enforceable read/mutate tool interface, and a
strict pre-mortem generator. These are control-plane primitives; the existing
orchestrator still needs to call them.

## Top five gaps

### 1. The cognitive pipeline is labels and heuristics, not layered model work

**Missing or wrong**

- There are no role-specific prompts or structured response schemas in the
  existing engine.
- Requirement extraction splits punctuation and truncates the ledger to five
  items (`orchestrator.py`, `_extract_requirements`).
- Classification is keyword matching; candidate selection always takes the
  first canned option.
- The model router described in the blueprint does not exist, so cheap
  extraction, strong planning, independent criticism, and task-risk escalation
  cannot be assigned to different models or temperatures.

**Why it matters for quality**

One undifferentiated or heuristic pass causes omissions to propagate: a missed
requirement never reaches planning, a weak plan constrains execution, and the
same reasoning process tends to approve its own error. The absence of typed
outputs also lets prose be mistaken for task state.

**Minimal fix**

Use the seven templates and `ModelRouter` generated in
`layered_prompts.py`. Render each layer independently, validate its JSON against
a typed schema, and retry malformed output once with the schema error. Persist
the resulting requirements, evidence requests, plan nodes, critiques, and
repairs before allowing the next transition.

### 2. Execution is simulated and there is no permission-enforcing tool sandbox

**Missing or wrong**

`_execute_plan` writes a journal row, returns
`{"success": True, "output": "Executed: ..."}`, and marks every node complete
without invoking a filesystem, shell, browser, test, or connector
(`orchestrator.py:314-335`). Risk checks later search command text for a few
keywords; that is retrospective pattern matching, not a pre-action permission
boundary.

**Why it matters for quality**

The engine can report progress without changing or observing reality. It cannot
distinguish reads from mutations, enforce writable roots, require approval for
external actions, or prove which files changed. Consequently both its success
signal and its safety score are untrustworthy.

**Minimal fix**

Route every plan-node action through `ToolSandbox.read()` or
`ToolSandbox.mutate()`. Register exact capabilities with `ToolSpec`, configure
readable/writable roots and allowlists in `SandboxPolicy`, require an approved
action ID for consequential mutations, and persist each `ToolCallRecord`.
Shell and connector adapters must add their own domain-specific argument
validation; prompts must never grant permission.

### 3. Claim provenance exists as nullable text, not a live evidence graph

**Missing or wrong**

Claims have `evidence_ids` and `freshness_requirement`, but both are unvalidated
text columns. Evidence has a timestamp, while claims have no enforced
claim-to-evidence relation, source hash/version, expiry calculation, or
invalidation cascade. The risk gate merely checks a manually assigned
`verification_status`. Memory invalidation stores a timestamp but ignores its
`reason` parameter and does not invalidate dependent claims, decisions, or plan
nodes (`db.py:563-569`).

**Why it matters for quality**

A claim can be marked verified with nonexistent, stale, irrelevant, or changed
evidence. Version-sensitive facts can silently survive source changes, and
plans can continue after a premise becomes false. This defeats the blueprint's
main anti-hallucination mechanism.

**Minimal fix**

Add normalized `claim_evidence` and `decision_premise` relations; store source
URI, observed time, content hash/version, authority, and expiry/invalidation
condition. Verification must resolve every referenced evidence ID and enforce
freshness. When a source hash/version or expiry changes, mark dependent claims
and decisions stale, invalidate downstream plan nodes, and re-plan from the
earliest affected milestone.

### 4. Planning has no pre-mortem, real acceptance tests, or recovery loop

**Missing or wrong**

Problem-model helpers return `"unknown"` or empty lists; planning chooses the
first canned candidate; most nodes lack expected observations and real
validators. `_error_recovery` records the gate name, blocks only when more than
three gates fail, and otherwise returns success without diagnosis or repair
(`orchestrator.py:359-383`). It does not implement the ten recovery stages,
retry identity checks, blast-radius analysis, competing diagnoses, or
regression tests.

**Why it matters for quality**

The plan is not falsifiable before action, and failed validation does not change
the hypothesis or artifact. The engine can continue after a failed gate,
repeat the same mistake, or repair symptoms while preserving the earliest bad
premise.

**Minimal fix**

Run `PreMortemGenerator` after candidate selection and insert each preventive
check before the named risky node. Require every node to have an expected
observation and executable validator. On failure, transition through
`DIAGNOSING → REPLANNING`, implement the blueprint's ten recovery records, ban
identical semantic retries, apply the smallest repair, rerun the original
failure, then run regressions.

### 5. Validation and calibration do not measure real correctness

**Missing or wrong**

- Several quality dimensions return constants (`quality.py:192-221`), while
  the alternate orchestrator score implements only fragments of the rubric.
- Gate 3 treats “no journaled nonzero exit” as correctness even when nothing
  ran. Gate 7 requires `DELIVERED`, but it is called while the task is
  `VALIDATING`, before delivery (`validation.py`, `gate_7_communication_quality`;
  `orchestrator.py:86-114`).
- No Brier-score event store, benchmark versions, predicted probabilities,
  outcomes, reliability bins, or regression comparisons exist.
- The execution journal schema has an unresolved-question field, but simulated
  execution never records outputs, exit status, affected files, or questions.
- The shipped pytest suite currently fails: `SoulEngineDB(":memory:")` creates a
  fresh SQLite database for every connection, so later calls see no tables; two
  tests also request nonexistent `db` and `task_id` fixtures.

**Why it matters for quality**

Constant and self-referential scores create false confidence. Without empirical
outcomes, confidence values are decoration rather than calibrated
probabilities, and releases cannot be compared. Broken tests remove even the
baseline regression signal.

**Minimal fix**

First make tests hermetic: retain one connection for `:memory:` or use a shared
memory URI, and define real fixtures. Move communication review after draft
synthesis and remove the impossible delivered-state dependency. Persist
`predicted_probability`, binary/graded outcome, task-suite version, model,
prompt version, and route; calculate mean Brier score
`mean((p - outcome) ** 2)` plus reliability bins. Replace constant dimensions
with artifact-derived checks and block completion when required journal fields
or hard-gate evidence are absent.

## Generated components

`src/soul_engine/prompts/layered_prompts.py` contains:

1. Seven runnable `string.Template`-compatible Python prompt strings with
   evidence boundaries and JSON-only output contracts.
2. `ModelRouter`, which selects Luna, Terra, or Sol from role, complexity,
   stakes, ambiguity, novelty, tool risk, context size, current-evidence
   requirements, critic independence, and cost preference.
   Model deployment names and context limits are configurable.
3. `ToolSandbox`, whose separate `read()` and `mutate()` entry points enforce
   registered operation mode, exact capability allowlists, allowed roots,
   external-action approvals, and audit digests.
4. `PreMortemGenerator`, which routes a plan-analysis call and rejects output
   unless it contains the configured number of complete, typed failure modes
   with signals and preventive checks.

## Recommended integration order

1. Repair the database/test lifecycle so verification is trustworthy.
2. Replace simulated execution with sandboxed adapters and pre-action gates.
3. Connect requirement extraction, evidence planning, and solution planning.
4. Add provenance relations and freshness invalidation before enabling durable
   memory.
5. Connect critic/corrector/final-writer stages, then add benchmark and Brier
   calibration tracking.

This order establishes contact with reality before increasing autonomy.
