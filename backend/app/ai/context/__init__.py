"""
Context Module - Sistema de contexto rico para a IA.

Responsável por carregar e formatar dados do usuário para
fornecer contexto completo ao LLM.
"""

from app.ai.context.user_data_loader import UserDataLoader
from app.ai.context.context_builder import ContextBuilder

__all__ = ["UserDataLoader", "ContextBuilder"]
