"""
Soul Engine Core — Task State Management
Implements Sol's 10-step state machine with SQLite persistence
"""

import sqlite3
import json
import uuid
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
from enum import Enum

class TaskStatus(Enum):
    RECEIVED = "RECEIVED"
    PARSED = "PARSED"
    EVIDENCE_GATHERING = "EVIDENCE_GATHERING"
    MODELED = "MODELED"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    SYNTHESIZING = "SYNTHESIZING"
    FINAL_GATE = "FINAL_GATE"
    DELIVERED = "DELIVERED"
    BLOCKED = "BLOCKED"

class ClaimType(Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    REMEMBERED = "remembered"
    ASSUMED = "assumed"
    PROPOSED = "proposed"

@dataclass
class Task:
    id: str
    user_goal: str
    task_class: str = "mixed"
    stakes: int = 0
    irreversibility: int = 0
    ambiguity: int = 0
    novelty: int = 0
    dependency_count: int = 0
    evidence_volatility: int = 0
    depth_score: float = 0.0
    status: TaskStatus = TaskStatus.RECEIVED
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def calculate_depth_score(self) -> float:
        """Sol's depth scoring formula."""
        return (
            0.25 * self.stakes +
            0.20 * self.irreversibility +
            0.15 * self.ambiguity +
            0.15 * self.novelty +
            0.15 * self.dependency_count +
            0.10 * self.evidence_volatility
        )
    
    def determine_planning_level(self) -> int:
        """Level 0 = direct, Level 1 = checkpoint, Level 2 = dependency."""
        if self.depth_score < 1.0:
            return 0
        elif self.depth_score < 2.5:
            return 1
        else:
            return 2

@dataclass
class Requirement:
    id: str
    task_id: str
    text: str
    source_location: Optional[str] = None
    priority: str = "required"
    acceptance_test: Optional[str] = None
    status: str = "pending"
    evidence_ids: Optional[str] = None
    created_at: Optional[str] = None

@dataclass
class Claim:
    id: str
    task_id: str
    text: str
    claim_type: str = "assumed"
    confidence: float = 0.0
    stakes: int = 0
    freshness_requirement: Optional[str] = None
    evidence_ids: Optional[str] = None
    verification_status: str = "unverified"
    created_at: Optional[str] = None

@dataclass
class Decision:
    id: str
    task_id: str
    choice: str
    alternatives: Optional[str] = None
    premises: Optional[str] = None
    evidence_ids: Optional[str] = None
    confidence: float = 0.0
    rollback_point: Optional[str] = None
    invalidated_at: Optional[str] = None
    created_at: Optional[str] = None

@dataclass
class PlanNode:
    id: str
    task_id: str
    description: str
    dependencies: Optional[str] = None
    expected_observation: Optional[str] = None
    validation_method: Optional[str] = None
    status: str = "pending"
    retry_count: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None

@dataclass
class Evidence:
    id: str
    task_id: str
    source: str
    content: str
    source_type: str = "file"
    provenance: Optional[str] = None
    observed_at: Optional[str] = None

@dataclass
class ExecutionJournalEntry:
    id: int
    task_id: str
    action: str
    command: Optional[str] = None
    output: Optional[str] = None
    exit_status: Optional[int] = None
    affected_files: Optional[str] = None
    unresolved_questions: Optional[str] = None
    created_at: Optional[str] = None

@dataclass
class ErrorRecord:
    id: int
    task_id: str
    signature: str
    context_hash: Optional[str] = None
    root_cause: Optional[str] = None
    bad_assumption: Optional[str] = None
    fix: Optional[str] = None
    regression_test: Optional[str] = None
    general_lesson: Optional[str] = None
    created_at: Optional[str] = None

@dataclass
class MemoryItem:
    id: int
    statement: str
    scope: str
    source: Optional[str] = None
    observed_at: Optional[str] = None
    confidence: float = 0.0
    expires_when: Optional[str] = None
    invalidated_at: Optional[str] = None
    created_at: Optional[str] = None


class SoulEngineDB:
    """SQLite database for Soul Engine task state management."""
    
    def __init__(self, db_path: str = "soul_engine.db"):
        self.db_path = db_path
        self.init_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_schema(self):
        """Initialize database schema."""
        schema = '''
        -- Task lifecycle
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            user_goal TEXT NOT NULL,
            task_class TEXT DEFAULT 'mixed',
            stakes INTEGER DEFAULT 0,
            irreversibility INTEGER DEFAULT 0,
            ambiguity INTEGER DEFAULT 0,
            novelty INTEGER DEFAULT 0,
            dependency_count INTEGER DEFAULT 0,
            evidence_volatility INTEGER DEFAULT 0,
            depth_score REAL DEFAULT 0.0,
            status TEXT DEFAULT 'RECEIVED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS requirements (
            id TEXT PRIMARY KEY,
            task_id TEXT REFERENCES tasks(id),
            text TEXT NOT NULL,
            source_location TEXT,
            priority TEXT DEFAULT 'required',
            acceptance_test TEXT,
            status TEXT DEFAULT 'pending',
            evidence_ids TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS claims (
            id TEXT PRIMARY KEY,
            task_id TEXT REFERENCES tasks(id),
            text TEXT NOT NULL,
            claim_type TEXT DEFAULT 'assumed',
            confidence REAL DEFAULT 0.0,
            stakes INTEGER DEFAULT 0,
            freshness_requirement TEXT,
            evidence_ids TEXT,
            verification_status TEXT DEFAULT 'unverified',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            task_id TEXT REFERENCES tasks(id),
            choice TEXT NOT NULL,
            alternatives TEXT,
            premises TEXT,
            evidence_ids TEXT,
            confidence REAL DEFAULT 0.0,
            rollback_point TEXT,
            invalidated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS plan_nodes (
            id TEXT PRIMARY KEY,
            task_id TEXT REFERENCES tasks(id),
            description TEXT NOT NULL,
            dependencies TEXT,
            expected_observation TEXT,
            validation_method TEXT,
            status TEXT DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY,
            task_id TEXT REFERENCES tasks(id),
            source TEXT,
            content TEXT NOT NULL,
            source_type TEXT DEFAULT 'file',
            provenance TEXT,
            observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS execution_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT REFERENCES tasks(id),
            action TEXT,
            command TEXT,
            output TEXT,
            exit_status INTEGER,
            affected_files TEXT,
            unresolved_questions TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS error_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT REFERENCES tasks(id),
            signature TEXT,
            context_hash TEXT,
            root_cause TEXT,
            bad_assumption TEXT,
            fix TEXT,
            regression_test TEXT,
            general_lesson TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS memory (
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
        '''
        with self._get_connection() as conn:
            conn.executescript(schema)
            conn.commit()
    
    # Task operations
    def create_task(self, user_goal: str, **kwargs) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            user_goal=user_goal,
            **kwargs
        )
        task.depth_score = task.calculate_depth_score()
        task.created_at = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO tasks (id, user_goal, task_class, stakes, irreversibility, 
                                  ambiguity, novelty, dependency_count, evidence_volatility, 
                                  depth_score, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task.id, task.user_goal, task.task_class, task.stakes, task.irreversibility,
                task.ambiguity, task.novelty, task.dependency_count, task.evidence_volatility,
                task.depth_score, task.status.value, task.created_at
            ))
            conn.commit()
        return task
    
    def update_task_status(self, task_id: str, status: TaskStatus):
        with self._get_connection() as conn:
            conn.execute(
                'UPDATE tasks SET status = ? WHERE id = ?',
                (status.value, task_id)
            )
            if status == TaskStatus.DELIVERED:
                conn.execute(
                    'UPDATE tasks SET completed_at = ? WHERE id = ?',
                    (datetime.now().isoformat(), task_id)
                )
            conn.commit()
    
    def get_task(self, task_id: str) -> Optional[Task]:
        with self._get_connection() as conn:
            row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
            if row:
                return Task(**dict(row))
            return None
    
    # Requirement operations
    def add_requirement(self, task_id: str, text: str, **kwargs) -> Requirement:
        req_id = str(uuid.uuid4())
        req = Requirement(id=req_id, task_id=task_id, text=text, **kwargs)
        req.created_at = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO requirements (id, task_id, text, source_location, priority, 
                                         acceptance_test, status, evidence_ids, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (req.id, req.task_id, req.text, req.source_location, req.priority,
                  req.acceptance_test, req.status, req.evidence_ids, req.created_at))
            conn.commit()
        return req
    
    def get_requirements(self, task_id: str) -> List[Requirement]:
        with self._get_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM requirements WHERE task_id = ?', (task_id,)
            ).fetchall()
            return [Requirement(**dict(row)) for row in rows]
    
    # Claim operations
    def add_claim(self, task_id: str, text: str, claim_type: str, confidence: float = 0.0, 
                  stakes: int = 0, **kwargs) -> Claim:
        claim_id = str(uuid.uuid4())
        claim = Claim(
            id=claim_id, task_id=task_id, text=text, claim_type=claim_type,
            confidence=confidence, stakes=stakes, **kwargs
        )
        claim.created_at = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO claims (id, task_id, text, claim_type, confidence, stakes,
                                   freshness_requirement, evidence_ids, verification_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (claim.id, claim.task_id, claim.text, claim.claim_type, claim.confidence,
                  claim.stakes, claim.freshness_requirement, claim.evidence_ids,
                  claim.verification_status, claim.created_at))
            conn.commit()
        return claim
    
    def get_claims(self, task_id: str) -> List[Claim]:
        with self._get_connection() as conn:
            rows = conn.execute('SELECT * FROM claims WHERE task_id = ?', (task_id,)).fetchall()
            return [Claim(**dict(row)) for row in rows]
    
    # Decision operations
    def add_decision(self, task_id: str, choice: str, **kwargs) -> Decision:
        decision_id = str(uuid.uuid4())
        decision = Decision(id=decision_id, task_id=task_id, choice=choice, **kwargs)
        decision.created_at = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO decisions (id, task_id, choice, alternatives, premises, 
                                      evidence_ids, confidence, rollback_point, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (decision.id, decision.task_id, decision.choice, decision.alternatives,
                  decision.premises, decision.evidence_ids, decision.confidence,
                  decision.rollback_point, decision.created_at))
            conn.commit()
        return decision
    
    # Plan node operations
    def add_plan_node(self, task_id: str, description: str, **kwargs) -> PlanNode:
        node_id = str(uuid.uuid4())
        node = PlanNode(id=node_id, task_id=task_id, description=description, **kwargs)
        node.created_at = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO plan_nodes (id, task_id, description, dependencies, expected_observation,
                                       validation_method, status, retry_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (node.id, node.task_id, node.description, node.dependencies,
                  node.expected_observation, node.validation_method, node.status,
                  node.retry_count, node.created_at))
            conn.commit()
        return node
    
    def get_plan_nodes(self, task_id: str) -> List[PlanNode]:
        with self._get_connection() as conn:
            rows = conn.execute('SELECT * FROM plan_nodes WHERE task_id = ?', (task_id,)).fetchall()
            return [PlanNode(**dict(row)) for row in rows]
    
    def update_plan_node_status(self, node_id: str, status: str):
        with self._get_connection() as conn:
            if status == 'active':
                conn.execute('UPDATE plan_nodes SET status = ?, started_at = ? WHERE id = ?',
                             (status, datetime.now().isoformat(), node_id))
            elif status == 'complete':
                conn.execute('UPDATE plan_nodes SET status = ?, completed_at = ? WHERE id = ?',
                             (status, datetime.now().isoformat(), node_id))
            else:
                conn.execute('UPDATE plan_nodes SET status = ? WHERE id = ?', (status, node_id))
            conn.commit()
    
    # Evidence operations
    def add_evidence(self, task_id: str, source: str, content: str, **kwargs) -> Evidence:
        evidence_id = str(uuid.uuid4())
        evidence = Evidence(id=evidence_id, task_id=task_id, source=source, 
                          content=content, **kwargs)
        evidence.observed_at = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO evidence (id, task_id, source, content, source_type, provenance, observed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (evidence.id, evidence.task_id, evidence.source, evidence.content,
                  evidence.source_type, evidence.provenance, evidence.observed_at))
            conn.commit()
        return evidence
    
    def get_evidence(self, task_id: str) -> List[Evidence]:
        with self._get_connection() as conn:
            rows = conn.execute('SELECT * FROM evidence WHERE task_id = ?', (task_id,)).fetchall()
            return [Evidence(**dict(row)) for row in rows]
    
    # Execution journal
    def add_journal_entry(self, task_id: str, action: str, **kwargs) -> ExecutionJournalEntry:
        entry = ExecutionJournalEntry(
            id=0,  # Will be assigned by SQLite
            task_id=task_id,
            action=action,
            **kwargs
        )
        entry.created_at = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO execution_journal (task_id, action, command, output, exit_status,
                                              affected_files, unresolved_questions, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (entry.task_id, entry.action, entry.command, entry.output,
                  entry.exit_status, entry.affected_files, entry.unresolved_questions,
                  entry.created_at))
            conn.commit()
            if cursor.lastrowid:
                entry = ExecutionJournalEntry(
                    id=cursor.lastrowid,
                    task_id=entry.task_id,
                    action=entry.action,
                    command=entry.command,
                    output=entry.output,
                    exit_status=entry.exit_status,
                    affected_files=entry.affected_files,
                    unresolved_questions=entry.unresolved_questions,
                    created_at=entry.created_at
                )
        return entry
    
    # Error ledger
    def add_error(self, task_id: str, signature: str, **kwargs) -> ErrorRecord:
        error = ErrorRecord(
            id=0,
            task_id=task_id,
            signature=signature,
            **kwargs
        )
        error.created_at = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO error_ledger (task_id, signature, context_hash, root_cause,
                                         bad_assumption, fix, regression_test, general_lesson, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (error.task_id, error.signature, error.context_hash, error.root_cause,
                  error.bad_assumption, error.fix, error.regression_test,
                  error.general_lesson, error.created_at))
            conn.commit()
            error.id = cursor.lastrowid
        return error
    
    def get_errors(self, task_id: Optional[str] = None) -> List[ErrorRecord]:
        with self._get_connection() as conn:
            if task_id:
                rows = conn.execute('SELECT * FROM error_ledger WHERE task_id = ?', (task_id,)).fetchall()
            else:
                rows = conn.execute('SELECT * FROM error_ledger').fetchall()
            return [ErrorRecord(**dict(row)) for row in rows]
    
    # Memory operations
    def add_memory(self, statement: str, scope: str, **kwargs) -> MemoryItem:
        memory = MemoryItem(
            id=0,
            statement=statement,
            scope=scope,
            **kwargs
        )
        memory.created_at = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO memory (statement, scope, source, observed_at, confidence, 
                                   expires_when, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (memory.statement, memory.scope, memory.source, memory.observed_at,
                  memory.confidence, memory.expires_when, memory.created_at))
            conn.commit()
            memory.id = cursor.lastrowid
        return memory
    
    def get_memory(self, scope: Optional[str] = None) -> List[MemoryItem]:
        with self._get_connection() as conn:
            if scope:
                rows = conn.execute('SELECT * FROM memory WHERE scope = ?', (scope,)).fetchall()
            else:
                rows = conn.execute('SELECT * FROM memory').fetchall()
            return [MemoryItem(**dict(row)) for row in rows]
    
    def invalidate_memory(self, memory_id: int, reason: str):
        with self._get_connection() as conn:
            conn.execute(
                'UPDATE memory SET invalidated_at = ? WHERE id = ?',
                (datetime.now().isoformat(), memory_id)
            )
            conn.commit()
