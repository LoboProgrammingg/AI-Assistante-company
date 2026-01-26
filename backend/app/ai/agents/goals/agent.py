"""
Goals Agent - Gerenciamento de metas.

Tipos de metas:
- Financeiras: economizar X, reduzir gastos em Y
- Pessoais: exercício, leitura, hábitos
- Profissionais: cursos, projetos, networking
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, TYPE_CHECKING

from app.ai.agents.base import SpecializedAgent, AgentResult
from app.ai.agents.registry import AgentRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@AgentRegistry.register
class GoalsAgent(SpecializedAgent):
    """Agente de gerenciamento de metas."""
    
    name = "goals"
    description = "Gerencia metas financeiras e pessoais"
    supported_intents = ["goals", "meta", "objetivo", "economizar", "poupar"]
    
    def _register_tools(self) -> Dict[str, callable]:
        """Registra tools do agente de metas."""
        return {
            "create_goal": self._create_goal,
            "update_goal": self._update_goal,
            "read_goal_progress": self._read_goal_progress,
            "suggest_adjustment": self._suggest_adjustment,
            "list_goals": self._list_goals,
        }
    
    async def process(self, message: str, entities: Dict[str, Any] = None) -> AgentResult:
        """Processa solicitação de metas."""
        entities = entities or {}
        message_lower = message.lower()
        
        # Criar nova meta
        if any(k in message_lower for k in ["criar meta", "nova meta", "quero economizar", "quero poupar"]):
            return await self._handle_create_goal(message, entities)
        
        # Ver progresso
        if any(k in message_lower for k in ["progresso", "como estou", "minhas metas"]):
            return await self._handle_progress(entities)
        
        # Ajustar meta
        if any(k in message_lower for k in ["ajustar", "mudar meta", "alterar meta"]):
            return await self._handle_adjust(message, entities)
        
        # Listar metas
        return await self._handle_list()
    
    async def _handle_create_goal(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Cria nova meta."""
        import re
        
        # Extrair valor se mencionado
        amount_match = re.search(r"r?\$?\s*([\d.,]+)", message.lower())
        amount = 0.0
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(".", "").replace(",", "."))
            except ValueError:
                pass
        
        # Extrair prazo
        deadline = None
        if "mês" in message.lower() or "mes" in message.lower():
            deadline = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        elif "ano" in message.lower():
            deadline = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        elif "semana" in message.lower():
            deadline = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Detectar tipo de meta
        goal_type = "financial"
        if any(k in message.lower() for k in ["exercício", "academia", "correr", "saúde"]):
            goal_type = "health"
        elif any(k in message.lower() for k in ["ler", "livro", "estudar", "curso"]):
            goal_type = "personal"
        elif any(k in message.lower() for k in ["trabalho", "projeto", "carreira"]):
            goal_type = "professional"
        
        goal_data = {
            "type": goal_type,
            "target_amount": amount,
            "deadline": deadline,
            "description": message[:200],
        }
        
        if amount > 0:
            msg = f"🎯 *Meta financeira detectada!*\n\n"
            msg += f"💰 Objetivo: R$ {amount:,.2f}\n"
            if deadline:
                msg += f"📅 Prazo: {deadline}\n"
            msg += f"\n*Confirma a criação desta meta?*"
            
            return AgentResult(
                success=True,
                action="create_goal",
                data=goal_data,
                message=msg,
                requires_confirmation=True,
                confidence=0.8,
            )
        
        return AgentResult(
            success=True,
            action="create_goal",
            data=goal_data,
            message="🎯 Qual é o valor da sua meta? (ex: economizar R$ 1.000)",
            requires_confirmation=True,
        )
    
    async def _handle_progress(self, entities: Dict[str, Any]) -> AgentResult:
        """Mostra progresso das metas."""
        if not self.db or not self.user_id:
            return AgentResult(success=False, action="error", error="Sem acesso")
        
        try:
            from app.services.finance_service import FinanceService
            
            service = FinanceService(self.db)
            summary = service.get_summary_by_period(self.user_id, "mes")
            
            s = summary.get("summary", {})
            income = s.get("total_income", 0)
            expense = s.get("total_expense", 0)
            saved = income - expense
            
            lines = ["📊 *Progresso Financeiro do Mês*\n"]
            
            if saved > 0:
                lines.append(f"💚 Economizado: R$ {saved:,.2f}")
                if income > 0:
                    rate = (saved / income) * 100
                    lines.append(f"📈 Taxa de poupança: {rate:.1f}%")
            else:
                lines.append(f"🔴 Déficit: R$ {abs(saved):,.2f}")
                lines.append("💡 _Tente reduzir gastos para atingir suas metas_")
            
            return AgentResult(
                success=True,
                action="read_goal_progress",
                data={"saved": saved, "income": income, "expense": expense},
                message="\n".join(lines),
            )
            
        except Exception as e:
            logger.error(f"[GOALS] Erro ao ler progresso: {e}")
            return AgentResult(success=False, action="error", error=str(e))
    
    async def _handle_adjust(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Sugere ajuste de meta."""
        return AgentResult(
            success=True,
            action="suggest_adjustment",
            data={},
            message="📝 Qual meta você gostaria de ajustar?\n\n_Dica: Posso sugerir ajustes baseados no seu comportamento real._",
            requires_confirmation=True,
        )
    
    async def _handle_list(self) -> AgentResult:
        """Lista metas ativas."""
        # Por enquanto, mostrar orientação
        lines = [
            "🎯 *Gerenciamento de Metas*\n",
            "Posso ajudar você a:",
            "• Criar metas de economia",
            "• Acompanhar seu progresso",
            "• Sugerir ajustes realistas\n",
            "_Diga algo como: \"quero economizar R$ 500 por mês\"_",
        ]
        
        return AgentResult(
            success=True,
            action="list_goals",
            data={},
            message="\n".join(lines),
        )
    
    # === Tool implementations ===
    
    def _create_goal(self, goal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria uma nova meta."""
        # TODO: Implementar persistência de metas
        return {
            "success": True,
            "message": f"✅ Meta criada: R$ {goal_data.get('target_amount', 0):,.2f}",
        }
    
    def _update_goal(self, goal_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza meta existente."""
        return {"success": False, "error": "Implementação pendente"}
    
    def _read_goal_progress(self, goal_id: str = None) -> Dict[str, Any]:
        """Lê progresso de uma meta."""
        return {"success": False, "error": "Implementação pendente"}
    
    def _suggest_adjustment(self, goal_id: str) -> Dict[str, Any]:
        """Sugere ajuste para uma meta."""
        return {"success": False, "error": "Implementação pendente"}
    
    def _list_goals(self) -> Dict[str, Any]:
        """Lista todas as metas."""
        return {"success": True, "goals": []}
