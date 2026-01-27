"""
IRIS Graph v3 - Arquitetura otimizada para baixa latência.

Estrutura:
├── state/          # Tipos e estado do grafo
├── nodes/          # CognitiveNode, ResponderNode
├── executors/      # Executores por domínio
├── templates/      # Templates de resposta
├── graph.py        # Grafo principal
└── migration.py    # Migração v2→v3
"""

from app.ai.graph_v3.core import IRISGraphV3, get_iris_graph_v3
from app.ai.graph_v3.executors import ExecutorNode
from app.ai.graph_v3.nodes import CognitiveNode, ResponderNode
from app.ai.graph_v3.state import (
    ExecutionResult,
    ExtractedAction,
    IRISStateV3,
    create_initial_state_v3,
)

__all__ = [
    # State
    "IRISStateV3",
    "ExtractedAction",
    "ExecutionResult",
    "create_initial_state_v3",
    # Nodes
    "CognitiveNode",
    "ResponderNode",
    "ExecutorNode",
    # Graph
    "IRISGraphV3",
    "get_iris_graph_v3",
]
