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
from app.ai.graph_v3.prompts.financial_agent_prompts import (
    ANOMALY_DETECTION_PROMPT,
    CASHFLOW_PROJECTION_PROMPT,
    CATEGORY_KEYWORDS,
    CATEGORY_LEARNING_PROMPT,
    EXPENSE_CATEGORIES,
    FINANCIAL_AGENT_SYSTEM_PROMPT,
    FINANCIAL_ANALYSIS_PROMPT,
    FINANCIAL_INTENT_PROMPT,
    FINANCIAL_SIMULATION_PROMPT,
    INCOME_CATEGORIES,
    INVESTMENT_ANALYSIS_PROMPT,
    TRANSACTION_EXTRACTION_PROMPT,
)
from app.ai.graph_v3.prompts.meeting_transcription_prompts import (
    SUMMARIZATION_PROMPT,
    TRANSCRIPTION_PROMPT,
)
from app.ai.graph_v3.prompts.responder_prompts import (
    GENERAL_PROMPT,
    RESPONSE_PROMPT,
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
    # Financial Agent
    "FINANCIAL_AGENT_SYSTEM_PROMPT",
    "FINANCIAL_ANALYSIS_PROMPT",
    "CATEGORY_LEARNING_PROMPT",
    "ANOMALY_DETECTION_PROMPT",
    "CASHFLOW_PROJECTION_PROMPT",
    "FINANCIAL_SIMULATION_PROMPT",
    "INVESTMENT_ANALYSIS_PROMPT",
    "TRANSACTION_EXTRACTION_PROMPT",
    "FINANCIAL_INTENT_PROMPT",
    "EXPENSE_CATEGORIES",
    "INCOME_CATEGORIES",
    "CATEGORY_KEYWORDS",
]
