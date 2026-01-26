"""
Base - Classe base para executores.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExecutionResult:
    """Resultado da execução de uma ação."""
    success: bool
    action_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    response_template: Optional[str] = None
