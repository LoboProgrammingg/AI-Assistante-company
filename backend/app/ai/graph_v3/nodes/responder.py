"""
Responder Node - Geração de respostas inteligentes via LLM Pro.

Responsabilidade:
- Gerar respostas INTELIGENTES baseadas nos dados REAIS do usuário
- Responder EXATAMENTE o que o usuário perguntou
- Usar contexto financeiro completo para análises
- Nunca dar respostas genéricas quando tem dados disponíveis

Usa Gemini Pro com contexto completo do banco de dados.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict

from langchain_core.messages import AIMessage

from app.ai.datetime_utils import get_datetime_context
from app.ai.graph_v3.state import IRISStateV3

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


RESPONSE_PROMPT = '''Você é IRIS, uma assistente pessoal EXTREMAMENTE inteligente e capaz.

DATA/HORA ATUAL: {datetime_context}
{user_context}

## PERGUNTA DO USUÁRIO
"{user_message}"

## DADOS DO USUÁRIO (DO BANCO DE DADOS)
{data_context}

## INSTRUÇÕES CRÍTICAS

1. **RESPONDA EXATAMENTE O QUE FOI PERGUNTADO** - Se pediu "5 maiores gastos", liste os 5 maiores gastos com valores.
2. **USE OS DADOS REAIS** - Você tem acesso aos dados do banco de dados acima. Use-os!
3. **SEJA ESPECÍFICA** - Dê valores, datas, descrições concretas.
4. **ANÁLISE INTELIGENTE** - Se perguntarem "como estou para economizar X", compare receitas - gastos com a meta.
5. **FORMATO WHATSAPP** - Use *negrito*, _itálico_, emojis apropriados.
6. **NUNCA DIGA "não tenho acesso"** - Você TEM os dados acima!

## EXEMPLOS DE RESPOSTAS

Pergunta: "Quais foram os 5 maiores gastos esse mês?"
Resposta:
📊 *Top 5 Maiores Gastos do Mês*

1. 🔴 *R$ 850,00* - Aluguel (01/01)
2. 🔴 *R$ 450,00* - Mercado (05/01)
3. 🔴 *R$ 200,00* - Conta de Luz (10/01)
4. 🔴 *R$ 150,00* - Uber (várias)
5. 🔴 *R$ 89,90* - Netflix (15/01)

💰 *Total desses gastos:* R$ 1.739,90

Pergunta: "Como estou para economizar 5000 esse mês?"
Resposta:
🎯 *Análise da Meta: R$ 5.000*

💵 Receitas: R$ 10.300,00
💸 Gastos: R$ 2.203,65
🟢 Economia atual: R$ 8.096,35

✅ *Parabéns!* Você já ultrapassou sua meta!
Economizou R$ 3.096,35 A MAIS que o objetivo.

Agora responda a pergunta do usuário usando os dados fornecidos:'''


GENERAL_PROMPT = '''Você é IRIS, assistente pessoal EXTREMAMENTE inteligente e capaz.

📅 DATA/HORA: {datetime_context}
{user_context}

## CONTEXTO COMPLETO DO USUÁRIO
{full_context}

## PERGUNTA/MENSAGEM
"{user_message}"

## INSTRUÇÕES

1. Você é uma IA COMPLETA com todo conhecimento de um modelo avançado
2. Use os dados do contexto acima quando relevante
3. Seja natural e amigável (estilo WhatsApp)
4. Use *negrito* para destaques, _itálico_ para ênfase
5. Responda COMPLETAMENTE a pergunta

Responda:'''


class ResponderNode:
    """Gerador de respostas via LLM Pro."""
    
    def __init__(self, llm: "ChatGoogleGenerativeAI"):
        self.llm = llm
    
    def respond(self, state: IRISStateV3) -> Dict[str, Any]:
        """Gera resposta usando LLM Pro."""
        # Se já tem template, usar direto
        template = state.get("response_template")
        if template:
            logger.info("[RESPONDER] ⚡ Usando template existente")
            return {"messages": [AIMessage(content=template)]}
        
        # Verificar se é resposta geral ou com contexto de execução
        execution_result = state.get("execution_result")
        
        if execution_result and not execution_result.response_template:
            return self._respond_with_context(state)
        
        return self._respond_general(state)
    
    def _respond_with_context(self, state: IRISStateV3) -> Dict[str, Any]:
        """Gera resposta com contexto de execução e dados completos."""
        user_message = state["messages"][-1].content if state["messages"] else ""
        user_name = state.get("user_name", "")
        
        # Construir contexto de dados completo
        data_context = self._build_data_context(state)
        
        prompt = RESPONSE_PROMPT.format(
            datetime_context=get_datetime_context(),
            user_context=f"👤 Usuário: {user_name}" if user_name else "",
            user_message=user_message,
            data_context=data_context,
        )
        
        try:
            response = self.llm.invoke(prompt)
            logger.info(f"[RESPONDER] 💬 Resposta inteligente: {len(response.content)} chars")
            return {"messages": [AIMessage(content=response.content)]}
        except Exception as e:
            logger.error(f"[RESPONDER] ❌ Erro: {e}")
            return {"messages": [AIMessage(content="Desculpe, tive um problema. Pode tentar novamente?")]}
    
    def _respond_general(self, state: IRISStateV3) -> Dict[str, Any]:
        """Gera resposta para conversas gerais com contexto completo."""
        user_message = state["messages"][-1].content if state["messages"] else ""
        user_name = state.get("user_name", "")
        
        # Construir contexto completo
        full_context = self._build_full_context(state)
        
        prompt = GENERAL_PROMPT.format(
            datetime_context=get_datetime_context(),
            user_context=f"👤 Usuário: {user_name}" if user_name else "",
            full_context=full_context,
            user_message=user_message,
        )
        
        try:
            response = self.llm.invoke(prompt)
            return {"messages": [AIMessage(content=response.content)]}
        except Exception as e:
            logger.error(f"[RESPONDER] ❌ Erro: {e}")
            return {"messages": [AIMessage(content="Tive um problema, pode repetir?")]}
    
    def _build_data_context(self, state: IRISStateV3) -> str:
        """Constrói contexto de dados completo para o LLM."""
        result = state.get("execution_result")
        entities = state.get("entities", {})
        
        lines = []
        
        # Adicionar dados da execução
        if result and result.success and result.data:
            data = result.data
            
            # Processar transações financeiras
            if "transactions" in data:
                transactions = data["transactions"]
                lines.append(f"### TRANSAÇÕES ENCONTRADAS ({len(transactions)}):")
                for i, t in enumerate(transactions[:20], 1):
                    tipo = "🔴" if t.get("type") == "expense" else "🟢"
                    lines.append(
                        f"{i}. {tipo} R$ {t.get('amount', 0):,.2f} - "
                        f"{t.get('description', 'Sem descrição')} "
                        f"({t.get('category', 'Outros')}) - {t.get('date', '')}"
                    )
                
                if len(transactions) > 20:
                    lines.append(f"... e mais {len(transactions) - 20} transações")
            
            # Processar resumo financeiro
            if "summary" in data:
                s = data["summary"]
                lines.append("")
                lines.append("### RESUMO FINANCEIRO:")
                lines.append(f"💵 Receitas: R$ {s.get('total_income', 0):,.2f}")
                lines.append(f"💸 Gastos: R$ {s.get('total_expenses', s.get('total_expense', 0)):,.2f}")
                balance = s.get('balance', 0)
                emoji = "🟢" if balance >= 0 else "🔴"
                lines.append(f"{emoji} Saldo: R$ {balance:,.2f}")
                lines.append(f"📊 Total de transações: {s.get('count', 0)}")
            
            # Processar categorias
            if "by_category" in data:
                cats = data["by_category"]
                if cats:
                    lines.append("")
                    lines.append("### GASTOS POR CATEGORIA:")
                    for cat in cats[:5]:
                        lines.append(f"  • {cat.get('category', 'Outros')}: R$ {cat.get('total', 0):,.2f}")
            
            # Processar total (para top N)
            if "total" in data:
                lines.append(f"")
                lines.append(f"💰 TOTAL: R$ {data['total']:,.2f}")
            
            # Processar lembretes
            if "reminders" in data or "active" in data:
                reminders = data.get("reminders", data.get("active", []))
                if reminders:
                    lines.append("")
                    lines.append("### LEMBRETES:")
                    for r in reminders[:10]:
                        lines.append(f"  • {r.get('title', '')} - {r.get('scheduled_time', '')}")
        
        # Se não teve dados da execução, buscar do contexto
        if not lines:
            context = state.get("context", {})
            if context:
                lines.append("### CONTEXTO DISPONÍVEL:")
                lines.append(str(context)[:2000])
        
        # Adicionar a pergunta original para contexto
        original_msg = entities.get("original_message", "")
        if original_msg:
            lines.insert(0, f"### PERGUNTA ORIGINAL: \"{original_msg}\"\n")
        
        return "\n".join(lines) if lines else "Nenhum dado específico encontrado."
    
    def _build_full_context(self, state: IRISStateV3) -> str:
        """Constrói contexto completo para respostas gerais."""
        db = state.get("db")
        user_id = state.get("user_id")
        
        if db and user_id:
            try:
                from app.ai.context import ContextBuilder
                builder = ContextBuilder(db, user_id, state.get("user_name", ""))
                return builder.build_full_context()
            except Exception as e:
                logger.warning(f"[RESPONDER] Erro ao construir contexto: {e}")
        
        # Fallback: usar contexto do state
        context_prompt = state.get("context_prompt", "")
        rag_context = state.get("rag_context", "")
        
        return f"{context_prompt}\n\n{rag_context}" if context_prompt or rag_context else "Nenhum contexto adicional disponível."
    
    def _summarize_execution(self, state: IRISStateV3) -> str:
        """Resume resultado da execução para log."""
        result = state.get("execution_result")
        if not result:
            return "Nenhuma ação executada"
        
        if result.success:
            data = result.data
            if isinstance(data, dict):
                if "transactions" in data:
                    return f"Sucesso - {len(data['transactions'])} transações"
                if "summary" in data:
                    s = data["summary"]
                    return f"Sucesso - Saldo: R$ {s.get('balance', 0):,.2f}"
                return f"Sucesso - {list(data.keys())[:3]}"
            return f"Sucesso"
        
        return f"Erro - {result.error or 'desconhecido'}"
