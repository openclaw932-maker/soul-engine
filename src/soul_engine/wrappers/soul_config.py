"""
Soul Engine — Permanent Wrapper Configuration
This file is loaded automatically by OllamaSoulAdapter.
Edit this to configure how Soul Engine wraps Llama calls.
"""

from typing import Dict, Any

# Default model for Soul-Engine-wrapped Ollama calls
DEFAULT_MODEL: str = "llama3.2:3b"

# Default database path
DEFAULT_DB_PATH: str = "soul_engine.db"

# Temperature settings by task class
TEMPERATURE_MAP: Dict[str, float] = {
    "factual": 0.1,      # Low creativity for facts
    "explanation": 0.2,   # Moderate for explanations
    "diagnosis": 0.2,     # Moderate for debugging
    "code": 0.1,          # Low for code (deterministic)
    "artifact": 0.3,      # Higher for creative output
    "planning": 0.2,      # Moderate for strategy
    "research": 0.3,      # Higher for exploration
    "external": 0.1,      # Low for external actions
    "mixed": 0.2          # Default
}

# Gate thresholds (0-4 scale)
GATE_THRESHOLDS: Dict[str, float] = {
    "requirement_coverage": 3.0,
    "claim_verification": 3.0,
    "correctness": 3.0,
    "completeness": 3.0,
    "consistency": 2.5,
    "risk": 3.0,
    "communication_quality": 2.5
}

# Quality score thresholds for automatic retry
AUTO_RETRY_THRESHOLD: float = 2.0  # Below this, retry with stricter prompt
MAX_RETRIES: int = 2

# Logging
LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE: str = "soul_engine.log"

# Ollama connection
OLLAMA_BASE_URL: str = "http://localhost:11434"
OLLAMA_TIMEOUT: int = 60  # seconds

# Claim provenance tracking
ENABLE_PROVENANCE: bool = True
PROVENANCE_CONFIDENCE_THRESHOLD: float = 0.70

# Calibration tracking
ENABLE_CALIBRATION: bool = True
CALIBRATION_BIN_SIZE: float = 0.2  # Brier score bins

# Scope discipline
ENABLE_SCOPE_DISCIPLINE: bool = True
LOG_OPPORTUNISTIC_IMPROVEMENTS: bool = True
