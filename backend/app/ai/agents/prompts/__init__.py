# Prompts organizados por agente
from app.ai.agents.prompts.classifier_prompts import ClassifierPrompts
from app.ai.agents.prompts.finance_prompts import FinancePrompts
from app.ai.agents.prompts.meeting_prompts import MeetingPrompts
from app.ai.agents.prompts.reminder_prompts import ReminderPrompts
from app.ai.agents.prompts.response_prompts import ResponsePrompts

__all__ = [
    "ReminderPrompts",
    "FinancePrompts",
    "MeetingPrompts",
    "ClassifierPrompts",
    "ResponsePrompts",
]
