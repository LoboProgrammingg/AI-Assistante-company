"""
Context Module - Sistema de contexto rico para a IA.

Responsável por carregar e formatar dados do usuário para
fornecer contexto completo ao LLM.

Context module for IRIS AI.

Componentes:
- UserDataLoader: Carrega dados brutos do PostgreSQL
- ContextBuilder: Formata dados para prompts
- ContextCompressor: Reduz tokens enviando apenas dados relevantes
"""

from app.ai.context.context_builder import ContextBuilder
from app.ai.context.user_data_loader import UserDataLoader
from app.ai.context.compressor import ContextCompressor, compress_context

__all__ = [
    "ContextBuilder",
    "UserDataLoader",
    "ContextCompressor",
    "compress_context"
]
