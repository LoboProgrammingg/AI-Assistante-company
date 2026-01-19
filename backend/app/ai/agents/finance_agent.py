import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.ai.agents.base_agent import BaseAgent
from app.utils.timezone_helper import get_current_time_for_user

logger = logging.getLogger(__name__)


def get_user_finances(db: Session, user_id: int, start_date: date = None, end_date: date = None, category: str = None) -> List[Dict]:
    """Consulta finanças reais do usuário no banco de dados."""
    from app.models import Finance, FinanceCategory
    
    query = db.query(Finance).filter(Finance.user_id == user_id)
    
    if start_date:
        query = query.filter(Finance.transaction_date >= start_date)
    if end_date:
        query = query.filter(Finance.transaction_date <= end_date)
    
    # Filtrar por categoria se especificada
    if category:
        cat = db.query(FinanceCategory).filter(FinanceCategory.name.ilike(f"%{category}%")).first()
        if cat:
            query = query.filter(Finance.category_id == cat.id)
    
    finances = query.order_by(Finance.transaction_date.desc()).limit(50).all()
    
    result = []
    for f in finances:
        cat_name = f.category.name if f.category else "Outros"
        result.append({
            "id": f.id,
            "type": f.type.value if f.type else "expense",
            "amount": f.amount,
            "description": f.description,
            "category": cat_name,
            "date": f.transaction_date.strftime("%d/%m/%Y") if f.transaction_date else "",
            "tags": f.tags or []
        })
    return result


class FinanceAgent(BaseAgent):
    """Agente especializado em finanças pessoais."""

    def __init__(self):
        super().__init__(
            name="FinanceAgent",
            description="Especialista em registrar e analisar transações financeiras",
            temperature=0.3
        )

    # Mapeamento de categorias com palavras-chave para identificação automática
    EXPENSE_CATEGORIES = {
        "Moradia": ["aluguel", "prestação", "casa", "apartamento", "condomínio", "iptu", "manutenção casa", "reforma"],
        "Contas": ["luz", "água", "gás", "energia", "telefone", "internet", "tv cabo", "celular", "conta"],
        "Alimentação": ["almoço", "jantar", "café", "lanche", "restaurante", "supermercado", "mercado", "padaria", "delivery", "ifood", "comida", "pizza", "hamburguer"],
        "Transporte": ["uber", "99", "taxi", "combustível", "gasolina", "álcool", "ônibus", "metrô", "passagem", "pedágio", "estacionamento"],
        "Saúde": ["médico", "remédio", "farmácia", "consulta", "exame", "plano de saúde", "dentista", "hospital", "academia"],
        "Educação": ["curso", "escola", "faculdade", "universidade", "livro", "apostila", "mensalidade", "material escolar"],
        "Lazer": ["cinema", "show", "teatro", "viagem", "hotel", "netflix", "spotify", "streaming", "jogo", "hobby", "festa", "bar"],
        "Vestuário": ["roupa", "calçado", "sapato", "tênis", "camisa", "calça", "vestido", "acessório", "bolsa", "relógio"],
        "Dívidas": ["cartão", "empréstimo", "financiamento", "parcela", "fatura", "juros", "dívida"],
        "Investimentos": ["investimento", "poupança", "ação", "fundo", "tesouro", "cdb", "reserva"],
        "Serviços Financeiros": ["tarifa", "taxa bancária", "anuidade", "ted", "pix", "transferência"],
        "Outros": []
    }
    
    INCOME_CATEGORIES = {
        "Salário": ["salário", "pagamento", "holerite", "contracheque"],
        "Freelance": ["freelance", "freela", "serviço", "trabalho extra", "bico"],
        "Investimentos": ["dividendo", "rendimento", "juros", "lucro"],
        "Vendas": ["venda", "vendi", "vendido"],
        "Outros": []
    }

    @property
    def system_prompt(self) -> str:
        return """Você é um assistente especializado em finanças pessoais.

Suas responsabilidades:
1. Registrar gastos e receitas
2. Categorizar transações automaticamente usando as categorias definidas
3. Gerar resumos financeiros
4. Identificar padrões de gastos
5. Responder perguntas sobre histórico financeiro (inclusive por categoria)

CATEGORIAS DE DESPESA (use EXATAMENTE estes nomes):
- Moradia: aluguel, prestação da casa, impostos (IPTU), condomínio, manutenção
- Contas: eletricidade, água, gás, telefone, internet, TV a cabo
- Alimentação: supermercado, restaurantes, lanchonetes, delivery, padaria
- Transporte: combustível, Uber/99, ônibus/metrô, manutenção veículo, pedágio, estacionamento
- Saúde: consultas médicas, remédios, plano de saúde, academia, dentista
- Educação: mensalidades, cursos, livros, materiais didáticos
- Lazer: cinema, shows, viagens, streaming (Netflix/Spotify), hobbies
- Vestuário: roupas, calçados, acessórios
- Dívidas: cartão de crédito, empréstimos, financiamentos
- Investimentos: aportes em fundos, poupança, ações
- Serviços Financeiros: taxas bancárias, tarifas, anuidades
- Outros: despesas diversas não categorizadas

CATEGORIAS DE RECEITA:
- Salário
- Freelance
- Investimentos
- Vendas
- Outros

Regras:
- SEMPRE use uma das categorias listadas acima (exatamente como escrito)
- Sempre confirme o valor e categoria registrados
- Para consultas por categoria, filtre APENAS transações daquela categoria
- Use R$ para valores em reais
- Quando perguntarem "quanto gastei com X", filtre pela categoria correspondente"""

    def process_sync(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa mensagem relacionada a finanças (versão síncrona)."""
        
        user_timezone = context.get("timezone", "America/Sao_Paulo")
        current_time = get_current_time_for_user(user_timezone)
        
        intent_prompt = f"""
Analise a mensagem do usuário sobre finanças.

MENSAGEM: "{message}"

Determine a intenção:
1. "register" - registrar nova transação
2. "query" - consultar histórico/resumo
3. "delete" - cancelar/remover/deletar transação
4. "clarify" - precisa de mais informações

Retorne APENAS JSON:
{{
    "intent": "register|query|delete|clarify",
    "sub_intent": "descrição específica"
}}
"""

        intent_response = self.invoke_llm_sync(intent_prompt)
        
        try:
            json_start = intent_response.find("{")
            json_end = intent_response.rfind("}") + 1
            intent_data = json.loads(intent_response[json_start:json_end])
        except:
            intent_data = {"intent": "clarify"}

        if intent_data.get("intent") == "register":
            return self._handle_register_sync(message, context, current_time)
        elif intent_data.get("intent") == "query":
            return self._handle_query_sync(message, context)
        elif intent_data.get("intent") == "delete":
            return self._handle_delete_sync(message, context)
        else:
            return {
                "response": "Poderia me dar mais detalhes? Você quer registrar um gasto/receita ou consultar seu histórico?",
                "entities": {},
                "next_action": "await_clarification",
                "confidence": 0.0
            }

    async def process(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa mensagem relacionada a finanças (versão assíncrona - redireciona para síncrona)."""
        return self.process_sync(message, context)

    def _handle_register_sync(
        self,
        message: str,
        context: Dict[str, Any],
        current_time
    ) -> Dict[str, Any]:
        """Processa registro de transação (versão síncrona). Suporta MÚLTIPLAS transações."""
        
        extraction_prompt = f"""
Extraia TODAS as transações financeiras mencionadas na mensagem.
O usuário pode mencionar múltiplos gastos e/ou receitas de uma só vez.

CONTEXTO:
{self.format_context(context)}
Data atual: {current_time.strftime("%d/%m/%Y")} (Ano: {current_time.year}, Mês: {current_time.month})

MENSAGEM: "{message}"

REGRAS PARA DATA:
- Se mencionar "ontem": use a data de ontem
- Se mencionar "dia X" ou "todo dia X": use dia X do mês atual (ou mês anterior se X > dia atual)
- Se mencionar "semana passada": use 7 dias atrás
- Se mencionar data específica (ex: 05/01): use essa data
- Se NÃO mencionar data: use a data atual
- Receitas recorrentes (salário, aluguel) que "caem" em um dia específico: use esse dia

IMPORTANTE: Identifique CADA transação separadamente. Exemplos:
- "gastei 80 no café e 150 de gasolina" = 2 despesas
- "gastei 50 no almoço e recebi 300 de venda" = 1 despesa + 1 receita
- "paguei luz 200, água 80 e internet 100" = 3 despesas

Retorne APENAS JSON com uma LISTA de transações:
{{
    "transactions": [
        {{
            "type": "expense|income",
            "amount": número (apenas o valor, sem R$),
            "description": "descrição da transação",
            "category": "categoria mais apropriada",
            "transaction_date": "YYYY-MM-DD",
            "is_recurring": true/false,
            "recurrence_day": dia do mês se for recorrente,
            "tags": ["tag1", "tag2"],
            "confidence": 0.0 a 1.0
        }}
    ]
}}

Se houver apenas UMA transação, retorne lista com 1 item.
Se não conseguir identificar nenhuma transação válida, retorne lista vazia.
"""

        response = self.invoke_llm_sync(extraction_prompt)
        
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            extracted = json.loads(response[json_start:json_end])
            transactions = extracted.get("transactions", [])
        except:
            return {
                "response": "Não consegui entender os valores. Pode repetir? Ex: 'Gastei 50 reais com almoço e 30 com café'",
                "entities": {},
                "next_action": "await_clarification",
                "confidence": 0.0
            }

        if not transactions:
            return {
                "response": "Não consegui identificar nenhuma transação. Pode repetir com os valores? Ex: 'Gastei 80 no café e 150 de gasolina'",
                "entities": {},
                "next_action": "await_clarification",
                "confidence": 0.0
            }

        # Processar múltiplas transações
        if len(transactions) == 1:
            # Apenas uma transação - formato simples
            t = transactions[0]
            type_text = "Gasto" if t.get("type") == "expense" else "Receita"
            amount = t.get("amount", 0)
            category = t.get("category", "Outros")
            date_str = t.get("transaction_date", current_time.strftime("%Y-%m-%d"))
            
            try:
                date_formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                date_formatted = date_str
            
            confirmation = f"✅ *{type_text} registrado!*\n\n💰 R$ {amount:.2f}\n📝 {t.get('description', message)}\n📁 Categoria: {category}\n📅 Data: {date_formatted}"

            return {
                "response": confirmation,
                "entities": {"finance": t},
                "next_action": "create_finance",
                "confidence": t.get("confidence", 0.8)
            }
        else:
            # Múltiplas transações
            confirmation_lines = [f"✅ *{len(transactions)} transações registradas!*\n"]
            
            total_expenses = 0
            total_income = 0
            
            for i, t in enumerate(transactions, 1):
                type_text = "📉 Gasto" if t.get("type") == "expense" else "📈 Receita"
                amount = t.get("amount", 0)
                category = t.get("category", "Outros")
                
                if t.get("type") == "expense":
                    total_expenses += amount
                else:
                    total_income += amount
                
                confirmation_lines.append(f"{i}. {type_text}: R$ {amount:.2f} - {t.get('description', 'Sem descrição')} ({category})")
            
            # Resumo
            confirmation_lines.append("")
            if total_expenses > 0:
                confirmation_lines.append(f"💸 Total gastos: R$ {total_expenses:.2f}")
            if total_income > 0:
                confirmation_lines.append(f"💰 Total receitas: R$ {total_income:.2f}")
            
            confirmation = "\n".join(confirmation_lines)

            return {
                "response": confirmation,
                "entities": {"finances": transactions},
                "next_action": "create_finances",
                "confidence": 0.9
            }

    async def _handle_register(
        self,
        message: str,
        context: Dict[str, Any],
        current_time
    ) -> Dict[str, Any]:
        """Processa registro de transação."""
        return self._handle_register_sync(message, context, current_time)

    def _detect_category_in_message(self, message: str) -> Optional[str]:
        """Detecta se a mensagem menciona uma categoria específica."""
        message_lower = message.lower()
        
        # Mapeamento de palavras-chave para categorias
        category_keywords = {
            "alimentação": ["alimentação", "alimentacao", "comida", "alimento", "refeição", "refeicao"],
            "moradia": ["moradia", "casa", "aluguel", "apartamento"],
            "contas": ["contas", "conta de luz", "conta de água", "utilidades"],
            "transporte": ["transporte", "uber", "combustível", "gasolina", "ônibus"],
            "saúde": ["saúde", "saude", "médico", "remédio", "farmácia", "academia"],
            "educação": ["educação", "educacao", "curso", "escola", "faculdade"],
            "lazer": ["lazer", "entretenimento", "diversão", "cinema", "viagem"],
            "vestuário": ["vestuário", "vestuario", "roupa", "roupas", "calçado"],
            "dívidas": ["dívidas", "dividas", "dívida", "divida", "cartão", "empréstimo"],
            "investimentos": ["investimento", "investimentos", "poupança", "ação"],
            "serviços financeiros": ["serviços financeiros", "taxa", "tarifa bancária"],
        }
        
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return category.title()
        return None

    def _handle_query_sync(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa consulta financeira usando dados REAIS do banco (versão síncrona)."""
        
        db = context.get("db")
        user_id = context.get("user_id")
        user_timezone = context.get("timezone", "America/Sao_Paulo")
        current_time = get_current_time_for_user(user_timezone)
        today = current_time.date()
        
        if not db or not user_id:
            return {
                "response": "📊 Para consultar seu histórico financeiro, acesse a página de Finanças no menu.",
                "entities": {},
                "next_action": "query_finance",
                "confidence": 0.5
            }
        
        message_lower = message.lower()
        
        # Detectar categoria mencionada
        category_filter = self._detect_category_in_message(message)
        
        # Determinar período baseado na mensagem
        start_date = today.replace(day=1)  # Default: mês atual
        end_date = today
        period_description = "este mês"
        
        if "hoje" in message_lower:
            start_date = today
            end_date = today
            period_description = f"hoje ({today.strftime('%d/%m/%Y')})"
        elif "semana" in message_lower:
            start_date = today - timedelta(days=7)
            period_description = "últimos 7 dias"
        elif "mês" in message_lower or "mes" in message_lower or "mensal" in message_lower:
            start_date = today.replace(day=1)
            period_description = "este mês"
        elif "ontem" in message_lower:
            start_date = today - timedelta(days=1)
            end_date = today - timedelta(days=1)
            period_description = f"ontem ({start_date.strftime('%d/%m/%Y')})"
        elif "ano" in message_lower:
            start_date = today.replace(month=1, day=1)
            period_description = "este ano"
        
        # Consultar dados REAIS do banco (com filtro de categoria se especificado)
        finances = get_user_finances(db, user_id, start_date, end_date, category_filter)
        
        # Montar descrição
        if category_filter:
            filter_desc = f" com **{category_filter}**"
        else:
            filter_desc = ""
        
        if not finances:
            if category_filter:
                return {
                    "response": f"📊 Você não tem gastos com **{category_filter}** {period_description}.",
                    "entities": {"query": {"period": period_description, "category": category_filter, "count": 0}},
                    "next_action": "query_finance",
                    "confidence": 1.0
                }
            return {
                "response": f"📊 Você não tem transações registradas para {period_description}.",
                "entities": {"query": {"period": period_description, "count": 0}},
                "next_action": "query_finance",
                "confidence": 1.0
            }
        
        # Calcular totais
        total_expense = sum(f["amount"] for f in finances if f["type"] == "expense")
        total_income = sum(f["amount"] for f in finances if f["type"] == "income")
        
        # Agrupar por categoria se não houver filtro
        if not category_filter:
            by_category = {}
            for f in finances:
                cat = f.get("category", "Outros")
                if cat not in by_category:
                    by_category[cat] = 0
                if f["type"] == "expense":
                    by_category[cat] += f["amount"]
        
        # Separar gastos e receitas
        expenses = [f for f in finances if f["type"] == "expense"]
        incomes = [f for f in finances if f["type"] == "income"]
        
        # Formatar resposta (WhatsApp usa *negrito* e _itálico_)
        if category_filter:
            response_lines = [f"📊 *Gastos com {category_filter}* ({period_description}):\n"]
        else:
            response_lines = [f"📊 *Suas transações {period_description}:*"]
        
        # Mostrar receitas primeiro
        if incomes and not category_filter:
            response_lines.append("")
            response_lines.append("*💰 Receitas:*")
            for i, f in enumerate(incomes[:5], 1):
                date_str = f.get("date", "")
                cat = f.get("category", "Outros")
                response_lines.append(f"{i}. 🟢 {f['description']} - R$ {f['amount']:.2f}")
                response_lines.append(f"    📁 {cat} | 📅 {date_str}")
        
        # Mostrar gastos
        if expenses:
            response_lines.append("")
            response_lines.append("*💸 Gastos:*")
            for i, f in enumerate(expenses[:10], 1):
                date_str = f.get("date", "")
                cat = f.get("category", "Outros")
                response_lines.append(f"{i}. 🔴 {f['description']} - R$ {f['amount']:.2f}")
                response_lines.append(f"    📁 {cat} | 📅 {date_str}")
        
        if len(finances) > 15:
            response_lines.append(f"\n_... e mais {len(finances) - 15} transações._")
        
        # Resumo
        response_lines.append("")
        response_lines.append("─" * 20)
        response_lines.append(f"*Total de gastos:* R$ {total_expense:.2f}")
        if total_income > 0:
            response_lines.append(f"*Total de receitas:* R$ {total_income:.2f}")
            saldo = total_income - total_expense
            emoji_saldo = "📈" if saldo >= 0 else "📉"
            response_lines.append(f"{emoji_saldo} *Saldo:* R$ {saldo:.2f}")
        
        # Resumo por categoria
        if by_category and not category_filter:
            response_lines.append("")
            response_lines.append("*Por categoria:*")
            sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
            for i, (cat, amount) in enumerate(sorted_cats[:5], 1):
                if amount > 0:
                    response_lines.append(f"{i}. {cat}: R$ {amount:.2f}")
        
        return {
            "response": "\n".join(response_lines),
            "entities": {"query": {"period": period_description, "total_expense": total_expense, "total_income": total_income, "count": len(finances)}},
            "next_action": "query_finance",
            "confidence": 1.0
        }

    def _handle_delete_sync(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa solicitação de deleção de transação (versão síncrona)."""
        
        db = context.get("db")
        user_id = context.get("user_id")
        
        if not db or not user_id:
            return {
                "response": "❌ Para deletar transações, acesse a página de Finanças no menu.",
                "entities": {},
                "next_action": "none",
                "confidence": 0.5
            }
        
        # Buscar transações recentes para identificar qual deletar
        from app.models import Finance
        recent = db.query(Finance).filter(
            Finance.user_id == user_id
        ).order_by(Finance.created_at.desc()).limit(10).all()
        
        if not recent:
            return {
                "response": "📊 Você não tem transações registradas para deletar.",
                "entities": {},
                "next_action": "none",
                "confidence": 1.0
            }
        
        # Usar IA para identificar qual transação deletar
        transactions_text = "\n".join([
            f"ID {t.id}: {t.description} - R$ {t.amount:.2f} ({t.transaction_date.strftime('%d/%m/%Y')})"
            for t in recent
        ])
        
        identify_prompt = f"""
Identifique qual transação o usuário quer deletar.

MENSAGEM DO USUÁRIO: "{message}"

TRANSAÇÕES RECENTES:
{transactions_text}

Retorne APENAS JSON:
{{
    "transaction_id": número ou null se não identificar,
    "description_match": "descrição da transação identificada"
}}
"""
        
        response = self.invoke_llm_sync(identify_prompt)
        
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            identified = json.loads(response[json_start:json_end])
        except:
            identified = {"transaction_id": None}
        
        transaction_id = identified.get("transaction_id")
        
        if transaction_id:
            # Buscar a transação
            transaction = db.query(Finance).filter(
                Finance.id == transaction_id,
                Finance.user_id == user_id
            ).first()
            
            if transaction:
                desc = transaction.description
                amount = transaction.amount
                
                return {
                    "response": f"🗑️ Transação encontrada: *{desc}* - R$ {amount:.2f}\n\nConfirma a exclusão? (sim/não)",
                    "entities": {"delete_finance": {"id": transaction_id, "description": desc, "amount": amount}},
                    "next_action": "confirm_delete_finance",
                    "confidence": 0.9
                }
        
        # Listar transações para o usuário escolher
        options = "\n".join([
            f"{i+1}. *{t.description}* - R$ {t.amount:.2f} ({t.transaction_date.strftime('%d/%m')})"
            for i, t in enumerate(recent[:5])
        ])
        
        return {
            "response": f"🔍 Qual transação você quer deletar?\n\n{options}\n\nDiga qual você quer remover.",
            "entities": {"recent_finances": [{"id": t.id, "description": t.description} for t in recent[:5]]},
            "next_action": "await_delete_selection",
            "confidence": 0.7
        }

    async def _handle_query(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper async para _handle_query_sync."""
        return self._handle_query_sync(message, context)

    async def _handle_delete(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper async para _handle_delete_sync."""
        return self._handle_delete_sync(message, context)

    def extract_entities(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extrai entidades de forma síncrona."""
        return {}
