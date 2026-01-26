"""
Bills Agent - Agente especializado em faturas e documentos financeiros.

Responsabilidades:
- Processar imagens de faturas via OCR
- Extrair dados estruturados
- Criar lembretes de pagamento
- Registrar gastos automaticamente

Restrições:
- ❌ Nunca executar pagamento
- ❌ Nunca assumir valores não explicitados
- ✅ Confirmar dados críticos antes de salvar
"""

import logging
from typing import Any, Dict, List, TYPE_CHECKING

from app.ai.agents.base import SpecializedAgent, AgentResult, ConfidenceScore
from app.ai.agents.registry import AgentRegistry
from app.ai.agents.bills.tools import extract_invoice_data, create_financial_reminder

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@AgentRegistry.register
class BillsAgent(SpecializedAgent):
    """Agente especializado em faturas e documentos financeiros."""
    
    name = "bills"
    description = "Processa faturas, boletos e documentos financeiros"
    supported_intents = ["bills", "invoice", "fatura", "boleto", "conta"]
    
    # Campos obrigatórios para diferentes ações
    REQUIRED_FIELDS = {
        "create_reminder": ["vendor", "amount", "due_date"],
        "register_expense": ["amount", "vendor"],
        "extract_data": [],
    }
    
    # Ações que requerem confirmação obrigatória
    DANGEROUS_ACTIONS = {"register_expense", "create_reminder"}
    
    def _register_tools(self) -> Dict[str, callable]:
        """Registra tools específicas do BillsAgent."""
        return {
            "extract_invoice_data": self._extract_invoice_data,
            "create_financial_reminder": self._create_financial_reminder,
            "register_expense": self._register_expense,
            "read_image": self._read_image,
        }
    
    async def process(self, message: str, entities: Dict[str, Any] = None) -> AgentResult:
        """
        Processa mensagem relacionada a faturas.
        
        Fluxo:
        1. Verifica se há imagem/documento
        2. Extrai dados via OCR/parsing
        3. Calcula confidence
        4. Sugere ou executa ação
        """
        entities = entities or {}
        
        # Verificar se tem texto de OCR
        ocr_text = entities.get("ocr_text", "")
        image_url = entities.get("image_url", "")
        
        if ocr_text:
            return await self._process_ocr_text(ocr_text, entities)
        
        if image_url:
            return await self._process_image(image_url, entities)
        
        # Sem imagem - pode ser pergunta sobre faturas
        return await self._handle_query(message, entities)
    
    async def _process_ocr_text(self, ocr_text: str, entities: Dict[str, Any]) -> AgentResult:
        """Processa texto já extraído via OCR."""
        self.log("info", f"Processando OCR: {len(ocr_text)} chars")
        
        # Extrair dados da fatura
        invoice_data = extract_invoice_data(ocr_text, source="ocr")
        
        # Calcular confidence
        confidence = self.calculate_confidence("create_reminder", invoice_data)
        
        # Se confidence alta e dados completos, sugerir ação
        if invoice_data.get("amount", 0) > 0 and invoice_data.get("due_date"):
            action = "create_reminder"
            message = self._build_confirmation_message(invoice_data)
            
            return AgentResult(
                success=True,
                action=action,
                data=invoice_data,
                confidence=confidence.score,
                requires_confirmation=not confidence.can_auto_execute,
                message=message,
            )
        
        # Dados incompletos - retornar o que foi extraído
        return AgentResult(
            success=True,
            action="extract_data",
            data=invoice_data,
            confidence=confidence.score,
            requires_confirmation=False,
            message=self._build_extraction_summary(invoice_data),
        )
    
    async def _process_image(self, image_url: str, entities: Dict[str, Any]) -> AgentResult:
        """Processa imagem de fatura."""
        self.log("info", f"Processando imagem: {image_url[:50]}...")
        
        # O OCR já deve ter sido feito antes de chegar aqui
        # Se não tiver, indicar que precisa de OCR
        return AgentResult(
            success=False,
            action="needs_ocr",
            data={"image_url": image_url},
            confidence=0.0,
            message="Preciso processar a imagem primeiro. Por favor, envie novamente.",
        )
    
    async def _handle_query(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Trata perguntas sobre faturas."""
        self.log("info", f"Query: {message[:50]}...")
        
        # Verificar se é consulta de faturas pendentes
        keywords = ["pendente", "vencer", "pagar", "próxima", "atrasada"]
        message_lower = message.lower()
        
        if any(k in message_lower for k in keywords):
            return await self._list_pending_bills()
        
        return AgentResult(
            success=True,
            action="general_response",
            data={},
            confidence=0.5,
            message="Posso ajudar com faturas! Envie uma imagem de boleto ou fatura que eu extraio os dados automaticamente.",
        )
    
    async def _list_pending_bills(self) -> AgentResult:
        """Lista faturas/lembretes pendentes."""
        if not self.db or not self.user_id:
            return AgentResult(
                success=False,
                action="error",
                data={},
                message="Não consegui acessar seus dados.",
            )
        
        try:
            from app.services.reminder_service import ReminderService
            
            service = ReminderService(self.db)
            reminders, total = service.list_by_user(
                self.user_id, 
                status="active", 
                limit=10,
            )
            
            # Filtrar lembretes financeiros
            financial = [r for r in reminders if "pagar" in r.title.lower() or "💰" in r.title]
            
            if not financial:
                return AgentResult(
                    success=True,
                    action="list_bills",
                    data={"bills": []},
                    message="📭 Você não tem faturas pendentes registradas.",
                )
            
            lines = ["💳 *Faturas pendentes:*\n"]
            for r in financial[:5]:
                time_str = r.scheduled_time.strftime("%d/%m") if r.scheduled_time else ""
                lines.append(f"• {r.title} - {time_str}")
            
            return AgentResult(
                success=True,
                action="list_bills",
                data={"bills": [{"title": r.title} for r in financial]},
                message="\n".join(lines),
            )
            
        except Exception as e:
            self.log("error", f"Erro ao listar faturas: {e}")
            return AgentResult(
                success=False,
                action="error",
                error=str(e),
            )
    
    def calculate_confidence(self, action: str, data: Dict[str, Any]) -> ConfidenceScore:
        """Calcula confidence para ações de faturas."""
        required = self.REQUIRED_FIELDS.get(action, [])
        
        if not required:
            return ConfidenceScore.from_score(0.7, "Ação sem requisitos")
        
        present = sum(1 for f in required if data.get(f))
        base_score = present / len(required)
        
        # Bonus por dados adicionais
        if data.get("barcode"):
            base_score = min(1.0, base_score + 0.1)
        if data.get("invoice_number"):
            base_score = min(1.0, base_score + 0.05)
        
        # Penalidade se valor muito alto ou suspeito
        amount = data.get("amount", 0)
        if amount > 10000:
            base_score = max(0.3, base_score - 0.2)
        
        reason = f"{present}/{len(required)} campos | R$ {amount:.2f}"
        return ConfidenceScore.from_score(base_score, reason)
    
    def _get_required_fields(self, action: str) -> List[str]:
        return self.REQUIRED_FIELDS.get(action, [])
    
    def _build_confirmation_message(self, data: Dict[str, Any]) -> str:
        """Monta mensagem de confirmação."""
        vendor = data.get("vendor", "Fatura")
        amount = data.get("amount", 0)
        due_date = data.get("due_date", "")
        category = data.get("category", "")
        installment = data.get("installment", "")
        
        lines = ["📄 *Dados extraídos da fatura:*\n"]
        
        if vendor:
            lines.append(f"🏢 *Empresa:* {vendor}")
        lines.append(f"💰 *Valor:* R$ {amount:,.2f}")
        if due_date:
            lines.append(f"📅 *Vencimento:* {due_date}")
        if category:
            lines.append(f"📂 *Categoria:* {category}")
        if installment:
            lines.append(f"🔢 *Parcela:* {installment}")
        
        lines.append("\n*Deseja que eu crie um lembrete para pagamento?*")
        
        return "\n".join(lines)
    
    def _build_extraction_summary(self, data: Dict[str, Any]) -> str:
        """Monta resumo da extração."""
        confidence = data.get("confidence", 0)
        
        if confidence < 0.3:
            return "❌ Não consegui identificar dados de fatura nesta imagem. Tente uma imagem mais nítida."
        
        lines = ["📄 *Dados encontrados:*\n"]
        
        if data.get("vendor"):
            lines.append(f"🏢 Empresa: {data['vendor']}")
        if data.get("amount"):
            lines.append(f"💰 Valor: R$ {data['amount']:,.2f}")
        if data.get("due_date"):
            lines.append(f"📅 Vencimento: {data['due_date']}")
        
        if len(lines) == 1:
            return "⚠️ Consegui ver a imagem, mas não encontrei dados claros de fatura."
        
        return "\n".join(lines)
    
    # === Tool implementations ===
    
    def _extract_invoice_data(self, text: str, source: str = "ocr") -> Dict[str, Any]:
        """Wrapper para tool de extração."""
        return extract_invoice_data(text, source)
    
    def _create_financial_reminder(self, invoice_data: Dict[str, Any], auto_create: bool = False) -> Dict[str, Any]:
        """Wrapper para tool de criar lembrete."""
        if not self.db or not self.user_id:
            return {"success": False, "error": "Sem acesso ao banco"}
        return create_financial_reminder(self.db, self.user_id, invoice_data, auto_create)
    
    def _register_expense(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra gasto a partir da fatura."""
        if not self.db or not self.user_id:
            return {"success": False, "error": "Sem acesso ao banco"}
        
        try:
            from app.services.finance_service import FinanceService
            
            service = FinanceService(self.db)
            
            finance_data = {
                "amount": invoice_data.get("amount", 0),
                "description": invoice_data.get("vendor", "Fatura"),
                "category": invoice_data.get("category", "Contas"),
                "type": "expense",
                "date": invoice_data.get("due_date"),
            }
            
            service.create_from_entities(self.user_id, finance_data)
            
            return {
                "success": True,
                "action": "registered_expense",
                "data": finance_data,
                "message": f"✅ Gasto registrado: {finance_data['description']} - R$ {finance_data['amount']:.2f}",
            }
        except Exception as e:
            self.log("error", f"Erro ao registrar gasto: {e}")
            return {"success": False, "error": str(e)}
    
    def _read_image(self, image_url: str) -> Dict[str, Any]:
        """Placeholder - OCR é feito em camada superior."""
        return {
            "success": False,
            "error": "OCR deve ser processado antes de chegar ao agente",
        }
