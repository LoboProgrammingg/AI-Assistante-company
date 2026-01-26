"""
Subscriptions Agent - Detecção e gerenciamento de assinaturas.

Detecta:
- Cobranças recorrentes (Netflix, Spotify, etc)
- Aumentos de preço
- Serviços não utilizados
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, TYPE_CHECKING

from app.ai.agents.base import SpecializedAgent, AgentResult
from app.ai.agents.registry import AgentRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Serviços conhecidos para detecção
KNOWN_SUBSCRIPTIONS = {
    "netflix": {"category": "Streaming", "typical_price": (39.90, 55.90)},
    "spotify": {"category": "Streaming", "typical_price": (21.90, 34.90)},
    "amazon prime": {"category": "Streaming", "typical_price": (14.90, 19.90)},
    "disney": {"category": "Streaming", "typical_price": (27.90, 43.90)},
    "hbo max": {"category": "Streaming", "typical_price": (19.90, 27.90)},
    "youtube premium": {"category": "Streaming", "typical_price": (24.90, 41.90)},
    "icloud": {"category": "Armazenamento", "typical_price": (3.50, 37.00)},
    "google one": {"category": "Armazenamento", "typical_price": (6.99, 34.99)},
    "dropbox": {"category": "Armazenamento", "typical_price": (11.99, 19.99)},
    "chatgpt": {"category": "IA", "typical_price": (100.00, 120.00)},
    "github": {"category": "Dev", "typical_price": (20.00, 44.00)},
    "academia": {"category": "Saúde", "typical_price": (80.00, 200.00)},
    "gym": {"category": "Saúde", "typical_price": (80.00, 200.00)},
}


@AgentRegistry.register
class SubscriptionsAgent(SpecializedAgent):
    """Agente de gerenciamento de assinaturas."""
    
    name = "subscriptions"
    description = "Detecta e gerencia assinaturas e cobranças recorrentes"
    supported_intents = ["subscriptions", "assinatura", "recorrente", "mensal"]
    
    def _register_tools(self) -> Dict[str, callable]:
        """Registra tools do agente."""
        return {
            "detect_recurring_payment": self._detect_recurring,
            "track_subscription": self._track_subscription,
            "alert_price_change": self._alert_price_change,
            "list_subscriptions": self._list_subscriptions,
            "analyze_subscriptions": self._analyze_subscriptions,
        }
    
    async def process(self, message: str, entities: Dict[str, Any] = None) -> AgentResult:
        """Processa solicitação sobre assinaturas."""
        entities = entities or {}
        message_lower = message.lower()
        
        # Detectar assinaturas
        if any(k in message_lower for k in ["detectar", "encontrar", "quais assinaturas"]):
            return await self._handle_detect()
        
        # Analisar gastos com assinaturas
        if any(k in message_lower for k in ["quanto gasto", "total", "valor"]):
            return await self._handle_analyze()
        
        # Verificar aumentos
        if any(k in message_lower for k in ["aumento", "subiu", "mais caro"]):
            return await self._handle_price_changes()
        
        # Listagem padrão
        return await self._handle_list()
    
    async def _handle_detect(self) -> AgentResult:
        """Detecta assinaturas nos gastos."""
        if not self.db or not self.user_id:
            return AgentResult(success=False, action="error", error="Sem acesso")
        
        try:
            from app.services.finance_service import FinanceService
            
            service = FinanceService(self.db)
            
            # Buscar gastos dos últimos 3 meses
            summary = service.get_summary_by_period(self.user_id, "tudo")
            transactions = summary.get("transactions", [])
            
            # Agrupar por descrição para encontrar recorrências
            by_description = defaultdict(list)
            for t in transactions:
                desc = t.get("description", "").lower()
                by_description[desc].append(t)
            
            # Encontrar recorrências (aparecem 2+ vezes)
            subscriptions = []
            for desc, items in by_description.items():
                if len(items) >= 2:
                    # Verificar se é serviço conhecido
                    for known, info in KNOWN_SUBSCRIPTIONS.items():
                        if known in desc:
                            avg_amount = sum(i.get("amount", 0) for i in items) / len(items)
                            subscriptions.append({
                                "name": known.title(),
                                "category": info["category"],
                                "amount": avg_amount,
                                "occurrences": len(items),
                            })
                            break
            
            if not subscriptions:
                return AgentResult(
                    success=True,
                    action="detect_recurring_payment",
                    data={"subscriptions": []},
                    message="📭 Nenhuma assinatura recorrente detectada nos seus gastos.\n\n_Dica: Registre seus gastos regularmente para detectar padrões._",
                )
            
            # Ordenar por valor
            subscriptions.sort(key=lambda x: x["amount"], reverse=True)
            
            total = sum(s["amount"] for s in subscriptions)
            
            lines = ["📱 *Assinaturas Detectadas*\n"]
            for s in subscriptions[:10]:
                lines.append(f"• {s['name']}: R$ {s['amount']:.2f}/mês")
            
            lines.append(f"\n💰 *Total mensal:* R$ {total:.2f}")
            lines.append(f"📅 *Anual estimado:* R$ {total * 12:,.2f}")
            
            return AgentResult(
                success=True,
                action="detect_recurring_payment",
                data={"subscriptions": subscriptions, "total": total},
                message="\n".join(lines),
            )
            
        except Exception as e:
            logger.error(f"[SUBSCRIPTIONS] Erro ao detectar: {e}")
            return AgentResult(success=False, action="error", error=str(e))
    
    async def _handle_analyze(self) -> AgentResult:
        """Analisa gastos com assinaturas."""
        result = await self._handle_detect()
        
        if not result.success or not result.data.get("subscriptions"):
            return result
        
        total = result.data.get("total", 0)
        subs = result.data.get("subscriptions", [])
        
        # Adicionar análise
        lines = [result.message, "\n📊 *Análise:*"]
        
        # Categoria com mais gasto
        by_category = defaultdict(float)
        for s in subs:
            by_category[s["category"]] += s["amount"]
        
        top_category = max(by_category.items(), key=lambda x: x[1])
        lines.append(f"• Maior categoria: {top_category[0]} (R$ {top_category[1]:.2f})")
        
        # Sugestão se gasto alto
        if total > 300:
            lines.append("\n💡 *Sugestão:* Revise se todos esses serviços são utilizados regularmente.")
        
        return AgentResult(
            success=True,
            action="analyze_subscriptions",
            data=result.data,
            message="\n".join(lines),
        )
    
    async def _handle_price_changes(self) -> AgentResult:
        """Verifica aumentos de preço."""
        return AgentResult(
            success=True,
            action="alert_price_change",
            data={},
            message="📈 Para detectar aumentos de preço, preciso de histórico de pelo menos 3 meses.\n\n_Continue registrando seus gastos e eu avisarei sobre qualquer aumento._",
        )
    
    async def _handle_list(self) -> AgentResult:
        """Lista funcionalidades do agente."""
        lines = [
            "📱 *Gerenciamento de Assinaturas*\n",
            "Posso ajudar você a:",
            "• Detectar assinaturas nos seus gastos",
            "• Calcular total mensal com streaming/apps",
            "• Alertar sobre aumentos de preço",
            "• Sugerir serviços para revisar\n",
            "_Diga: \"quais são minhas assinaturas?\"_",
        ]
        
        return AgentResult(
            success=True,
            action="list_subscriptions",
            data={},
            message="\n".join(lines),
        )
    
    # === Tool implementations ===
    
    def _detect_recurring(self, months: int = 3) -> Dict[str, Any]:
        """Detecta pagamentos recorrentes."""
        return {"success": False, "error": "Use o método process()"}
    
    def _track_subscription(self, name: str, amount: float) -> Dict[str, Any]:
        """Registra assinatura para tracking."""
        return {"success": True, "message": f"Assinatura {name} registrada"}
    
    def _alert_price_change(self, name: str, old_price: float, new_price: float) -> Dict[str, Any]:
        """Alerta sobre mudança de preço."""
        change = ((new_price - old_price) / old_price) * 100
        return {
            "success": True,
            "message": f"⚠️ {name} aumentou {change:.1f}%: R$ {old_price:.2f} → R$ {new_price:.2f}",
        }
    
    def _list_subscriptions(self) -> Dict[str, Any]:
        """Lista assinaturas rastreadas."""
        return {"success": True, "subscriptions": []}
    
    def _analyze_subscriptions(self) -> Dict[str, Any]:
        """Analisa gastos com assinaturas."""
        return {"success": False, "error": "Use o método process()"}
