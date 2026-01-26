"""
Goals Agent - Gerenciamento de metas inteligente.

Funcionalidades:
- Análise de progresso em relação a metas de economia
- Comparação entre meta desejada e situação financeira atual
- Projeções e recomendações personalizadas
- Persistência de metas no banco de dados

Usa LLM para entendimento semântico, não pattern matching.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.ai.agents.base import SpecializedAgent, AgentResult
from app.ai.agents.registry import AgentRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@AgentRegistry.register
class GoalsAgent(SpecializedAgent):
    """Agente inteligente de gerenciamento de metas."""
    
    name = "goals"
    description = "Analisa metas financeiras e pessoais com inteligência"
    supported_intents = ["goals", "meta", "objetivo", "economizar", "poupar"]
    
    def _register_tools(self) -> Dict[str, callable]:
        """Registra tools do agente de metas."""
        return {
            "analyze_goal_progress": self._analyze_goal_progress,
            "create_goal": self._create_goal,
            "list_goals": self._list_goals,
        }
    
    async def process(self, message: str, entities: Dict[str, Any] = None) -> AgentResult:
        """Processa solicitação de metas com análise inteligente."""
        entities = entities or {}
        
        logger.info(f"[GOALS] Processando: {message[:100]}")
        logger.info(f"[GOALS] Entities: {entities}")
        
        # Extrair valor da meta se mencionado
        meta_valor = entities.get("meta_valor") or self._extract_amount(message)
        periodo = entities.get("meta_periodo", "mes")
        
        logger.info(f"[GOALS] Meta valor extraído: {meta_valor}, Período: {periodo}")
        
        # Se tem valor de meta, fazer análise de progresso
        if meta_valor and meta_valor > 0:
            return await self._analyze_goal_progress(message, meta_valor, periodo)
        
        # Detectar ação baseada nas entities do CognitiveNode
        action = entities.get("action", "")
        
        if action == "create_goal":
            return await self._handle_create_goal(message, entities)
        elif action == "goal_progress":
            return await self._analyze_goal_progress(message, 0, periodo)
        
        # Fallback: análise geral do estado financeiro
        return await self._analyze_financial_state(message)
    
    def _extract_amount(self, message: str) -> float:
        """Extrai valor monetário da mensagem."""
        patterns = [
            r"r\$\s*([\d.,]+)",
            r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:reais|real)",
            r"(\d+(?:,\d{2})?)\s*(?:reais|real)",
            r"economizar\s+(\d+(?:\.\d{3})*(?:,\d{2})?)",
            r"poupar\s+(\d+(?:\.\d{3})*(?:,\d{2})?)",
            r"juntar\s+(\d+(?:\.\d{3})*(?:,\d{2})?)",
            r"meta\s+(?:de\s+)?(\d+(?:\.\d{3})*(?:,\d{2})?)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                try:
                    value_str = match.group(1)
                    value_str = value_str.replace(".", "").replace(",", ".")
                    return float(value_str)
                except ValueError:
                    continue
        
        return 0.0
    
    async def _analyze_goal_progress(self, message: str, meta_valor: float, periodo: str = "mes") -> AgentResult:
        """Analisa progresso em relação a uma meta de economia."""
        logger.info(f"[GOALS] Analisando progresso: meta={meta_valor}, periodo={periodo}")
        
        if not self.db or not self.user_id:
            logger.error(f"[GOALS] Sem acesso ao banco! db={self.db}, user_id={self.user_id}")
            return AgentResult(success=False, action="error", error="Sem acesso ao banco de dados")
        
        try:
            from app.services.finance_service import FinanceService
            
            service = FinanceService(self.db)
            logger.info(f"[GOALS] Buscando dados financeiros para user_id={self.user_id}")
            
            # Buscar dados do mês atual
            current = service.get_summary_by_period(self.user_id, "mes")
            current_summary = current.get("summary", {})
            
            # Buscar dados do mês anterior para comparação
            previous = service.get_summary_by_period(self.user_id, "mes_anterior")
            prev_summary = previous.get("summary", {})
            
            # Calcular valores
            income = current_summary.get("total_income", 0)
            expenses = current_summary.get("total_expenses", current_summary.get("total_expense", 0))
            current_savings = income - expenses
            
            prev_income = prev_summary.get("total_income", 0)
            prev_expenses = prev_summary.get("total_expenses", prev_summary.get("total_expense", 0))
            prev_savings = prev_income - prev_expenses
            
            # Buscar top gastos para análise
            top_expenses = service.get_top_transactions(
                user_id=self.user_id,
                limit=5,
                tipo="expense",
                periodo="mes",
                ordenacao="maior"
            )
            
            # Construir análise
            data = {
                "meta_valor": meta_valor,
                "income": income,
                "expenses": expenses,
                "current_savings": current_savings,
                "prev_savings": prev_savings,
                "top_expenses": top_expenses.get("transactions", []),
                "by_category": current.get("by_category", []),
                "transactions_count": current_summary.get("count", 0),
            }
            
            # Gerar resposta baseada nos dados
            lines = []
            
            if meta_valor > 0:
                lines.append(f"🎯 *Análise da Meta: R$ {meta_valor:,.2f}*\n")
                lines.append(f"💵 Receitas do mês: R$ {income:,.2f}")
                lines.append(f"💸 Gastos do mês: R$ {expenses:,.2f}")
                
                if current_savings >= 0:
                    lines.append(f"🟢 Economia atual: R$ {current_savings:,.2f}")
                else:
                    lines.append(f"🔴 Déficit atual: R$ {abs(current_savings):,.2f}")
                
                lines.append("")
                
                if current_savings >= meta_valor:
                    diff = current_savings - meta_valor
                    lines.append(f"✅ *Parabéns!* Você já atingiu sua meta!")
                    lines.append(f"📈 Economizou R$ {diff:,.2f} A MAIS que o objetivo.")
                elif current_savings > 0:
                    diff = meta_valor - current_savings
                    percentage = (current_savings / meta_valor) * 100
                    lines.append(f"📊 *Progresso:* {percentage:.1f}% da meta")
                    lines.append(f"⏳ Falta: R$ {diff:,.2f} para atingir o objetivo")
                    
                    if income > 0:
                        daily_needed = diff / max(1, 30 - datetime.now().day)
                        lines.append(f"💡 Economize R$ {daily_needed:,.2f}/dia para atingir a meta")
                else:
                    lines.append(f"⚠️ *Atenção:* Você está gastando mais do que ganha")
                    lines.append(f"💡 Revise seus gastos para alcançar sua meta")
            else:
                lines.append("📊 *Situação Financeira Atual*\n")
                lines.append(f"💵 Receitas: R$ {income:,.2f}")
                lines.append(f"� Gastos: R$ {expenses:,.2f}")
                
                if current_savings >= 0:
                    lines.append(f"� Economia: R$ {current_savings:,.2f}")
                    if income > 0:
                        rate = (current_savings / income) * 100
                        lines.append(f"📈 Taxa de poupança: {rate:.1f}%")
                else:
                    lines.append(f"🔴 Déficit: R$ {abs(current_savings):,.2f}")
            
            # Adicionar top gastos
            top = data.get("top_expenses", [])[:3]
            if top:
                lines.append("\n� *Maiores gastos do mês:*")
                for i, t in enumerate(top, 1):
                    lines.append(f"  {i}. R$ {t['amount']:,.2f} - {t['description']}")
            
            return AgentResult(
                success=True,
                action="goal_progress",
                data=data,
                message="\n".join(lines),
            )
            
        except Exception as e:
            logger.error(f"[GOALS] Erro na análise: {e}")
            return AgentResult(success=False, action="error", error=str(e))
    
    async def _analyze_financial_state(self, message: str) -> AgentResult:
        """Analisa estado financeiro geral."""
        return await self._analyze_goal_progress(message, 0, "mes")
    
    async def _handle_create_goal(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Cria nova meta."""
        amount = self._extract_amount(message)
        
        deadline = None
        if "mês" in message.lower() or "mes" in message.lower():
            deadline = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        elif "ano" in message.lower():
            deadline = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        
        goal_data = {
            "type": "financial",
            "target_amount": amount,
            "deadline": deadline,
            "description": message[:200],
        }
        
        if amount > 0:
            msg = f"🎯 *Meta financeira criada!*\n\n"
            msg += f"💰 Objetivo: R$ {amount:,.2f}\n"
            if deadline:
                msg += f"📅 Prazo: {deadline}\n"
            
            # Salvar meta no banco
            self._save_goal(goal_data)
            
            return AgentResult(
                success=True,
                action="create_goal",
                data=goal_data,
                message=msg,
            )
        
        return AgentResult(
            success=True,
            action="create_goal",
            data=goal_data,
            message="🎯 Qual é o valor da sua meta? (ex: economizar R$ 5.000)",
        )
    
    def _save_goal(self, goal_data: Dict[str, Any]) -> bool:
        """Salva meta no banco de dados."""
        if not self.db or not self.user_id:
            return False
        
        try:
            from app.models import UserMemory
            
            memory = UserMemory(
                user_id=self.user_id,
                memory_type="goal",
                content=f"Meta de economia: R$ {goal_data.get('target_amount', 0):,.2f}",
                metadata=goal_data,
                is_active=True,
            )
            self.db.add(memory)
            self.db.commit()
            
            logger.info(f"[GOALS] Meta salva para user {self.user_id}")
            return True
        except Exception as e:
            logger.error(f"[GOALS] Erro ao salvar meta: {e}")
            return False
    
    def _create_goal(self, goal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Tool: Cria uma nova meta."""
        success = self._save_goal(goal_data)
        return {
            "success": success,
            "message": f"✅ Meta criada: R$ {goal_data.get('target_amount', 0):,.2f}" if success else "Erro ao criar meta",
        }
    
    def _list_goals(self) -> Dict[str, Any]:
        """Tool: Lista metas ativas."""
        if not self.db or not self.user_id:
            return {"success": False, "goals": []}
        
        try:
            from app.models import UserMemory
            
            goals = (
                self.db.query(UserMemory)
                .filter(
                    UserMemory.user_id == self.user_id,
                    UserMemory.memory_type == "goal",
                    UserMemory.is_active == True,
                )
                .all()
            )
            
            return {
                "success": True,
                "goals": [
                    {
                        "id": g.id,
                        "content": g.content,
                        "metadata": g.metadata,
                    }
                    for g in goals
                ],
            }
        except Exception as e:
            logger.error(f"[GOALS] Erro ao listar metas: {e}")
            return {"success": False, "goals": []}
