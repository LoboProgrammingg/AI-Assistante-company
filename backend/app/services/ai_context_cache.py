"""
Cache Redis específico para contexto da IA - Compatibilidade.

Este arquivo mantém compatibilidade com imports existentes.
A implementação real está em app/core/cache/ai_context.py
"""

from app.core.cache.ai_context import AIContextCache, get_ai_cache

__all__ = ["AIContextCache", "get_ai_cache"]
