"""
Módulo AI - IRIS Graph v3
"""
from app.ai.graph_v3.core import IRISGraphV3
from app.ai.graph_v3.migration import process_message as process_message_v3, GRAPH_VERSION
from app.ai.memory import MemoryManager

__all__ = [
    "IRISGraphV3",
    "process_message_v3",
    "GRAPH_VERSION",
    "MemoryManager",
]
