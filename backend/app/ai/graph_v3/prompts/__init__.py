"""
Prompts do Graph V3 - Organizados por função.

Cada arquivo contém prompts específicos para um nó ou funcionalidade.
"""

from app.ai.graph_v3.prompts.cognitive_prompts import (
    COGNITIVE_PROMPT,
    DANGEROUS_ACTIONS,
    DEFAULT_ACTIONS,
    VALID_ACTIONS,
)
from app.ai.graph_v3.prompts.responder_prompts import (
    GENERAL_PROMPT,
    RESPONSE_PROMPT,
)
from app.ai.graph_v3.prompts.meeting_transcription_prompts import (
    TRANSCRIPTION_PROMPT,
    SUMMARIZATION_PROMPT,
)

__all__ = [
    # Cognitive
    "COGNITIVE_PROMPT",
    "VALID_ACTIONS",
    "DEFAULT_ACTIONS",
    "DANGEROUS_ACTIONS",
    # Responder
    "RESPONSE_PROMPT",
    "GENERAL_PROMPT",
    # Meeting Transcription
    "TRANSCRIPTION_PROMPT",
    "SUMMARIZATION_PROMPT",
]
