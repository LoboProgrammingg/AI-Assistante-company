"""
Grafo LangGraph v2 - IRIS com melhores práticas.

Melhorias implementadas:
- Estado tipado herdando de MessagesState
- Tools com Pydantic schemas
- Persistência com PostgreSQL Checkpointer
- Proteção contra loops infinitos
- Separação clara: LLM decide, ToolNode executa
"""

import json
import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, SystemMessage

# Timezone padrão: Cuiabá-MT (UTC-4)
TIMEZONE_DEFAULT = ZoneInfo("America/Cuiaba")


def get_current_datetime() -> datetime:
    """Retorna data/hora atual no timezone de Cuiabá-MT."""
    return datetime.now(TIMEZONE_DEFAULT)


def get_datetime_context() -> str:
    """Retorna string formatada com data/hora atual para contexto da IA."""
    now = get_current_datetime()
    dias_semana = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    
    dia_semana = dias_semana[now.weekday()]
    mes = meses[now.month - 1]
    
    return f"Hoje é {dia_semana}, {now.day} de {mes} de {now.year}. Horário atual: {now.strftime('%H:%M')} (Cuiabá-MT)."


from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.ai.agents.prompts.classifier_prompts import ClassifierPrompts
from app.ai.agents.prompts.response_prompts import ResponsePrompts
from app.ai.checkpointer import get_thread_config
from app.ai.memory import MemoryManager
from app.ai.state import IRISState, UserContext, create_initial_state
from app.ai.tools.contact_tools import ContactTools
from app.ai.tools.finance_tools import FinanceTools
from app.ai.tools.meeting_tools import MeetingTools
from app.ai.tools.reminder_tools import ReminderTools
from app.ai.tools.integrations.tavily_search import tavily_tools
from app.ai.tools.integrations.yfinance_tools import yfinance_tools
from app.ai.tools.integrations.brasil_api import brasil_api_tools
from app.ai.tools.integrations.google_calendar import google_calendar_tools
from app.config import settings
from app.core.llm_optimizer import get_optimizer

logger = logging.getLogger(__name__)


class IRISGraphV2:
    """
    Grafo LangGraph v2 seguindo melhores práticas.

    Arquitetura Hub-and-Spoke:
    - Router central classifica intenção
    - Sub-handlers processam cada domínio
    - ToolNode executa ações
    - Proteção contra loops
    """

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.model = model or settings.GEMINI_MODEL

        # LLM principal (para respostas)
        self.llm = ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self.api_key,
            temperature=0.3,
            max_output_tokens=8000,  # Reduzido para respostas mais rápidas
        )
        
        # LLM rápido para classificação (flash é 10x mais rápido)
        self.llm_fast = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=self.api_key,
            temperature=0.1,
            max_output_tokens=500,  # Classificação precisa de pouco output
        )

        # Coletar todas as tools (core + integrações)
        self.all_tools = (
            FinanceTools.get_all_tools()
            + ReminderTools.get_all_tools()
            + MeetingTools.get_all_tools()
            + ContactTools.get_all_tools()
            + tavily_tools.get_tools()
            + yfinance_tools.get_tools()
            + brasil_api_tools.get_tools()
            + google_calendar_tools.get_tools()
        )

        # LLM com tools bound
        self.llm_with_tools = self.llm.bind_tools(self.all_tools)

        # Compilar grafo
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Constrói o grafo de estados."""
        workflow = StateGraph(IRISState)

        # Nós principais
        workflow.add_node("router", self._router_node)
        workflow.add_node("finance_agent", self._finance_agent_node)
        workflow.add_node("reminder_agent", self._reminder_agent_node)
        workflow.add_node("meeting_agent", self._meeting_agent_node)
        workflow.add_node("contact_agent", self._contact_agent_node)
        workflow.add_node("general_chat", self._general_chat_node)
        workflow.add_node("tool_executor", self._tool_executor_node)
        workflow.add_node("response_formatter", self._response_formatter_node)
        workflow.add_node("error_handler", self._error_handler_node)

        # Entrada
        workflow.set_entry_point("router")

        # Router -> Agents (condicional)
        workflow.add_conditional_edges(
            "router",
            self._route_by_intent,
            {
                "finance": "finance_agent",
                "reminder": "reminder_agent",
                "meeting": "meeting_agent",
                "contact": "contact_agent",
                "general": "general_chat",
                "error": "error_handler",
            },
        )

        # Agents -> Tool executor ou Response (condicional)
        for agent in ["finance_agent", "reminder_agent", "meeting_agent", "contact_agent"]:
            workflow.add_conditional_edges(
                agent,
                self._should_execute_tools,
                {
                    "execute": "tool_executor",
                    "respond": "response_formatter",
                    "error": "error_handler",
                },
            )

        # Tool executor -> Response formatter
        workflow.add_edge("tool_executor", "response_formatter")

        # General chat -> Response formatter
        workflow.add_edge("general_chat", "response_formatter")

        # Response formatter -> END
        workflow.add_edge("response_formatter", END)

        # Error handler -> END
        workflow.add_edge("error_handler", END)

        return workflow.compile()

    def _router_node(self, state: IRISState) -> IRISState:
        """
        Nó Router: classifica intenção e roteia.
        Implementa proteção contra loops.
        """
        # Proteção contra loops
        state["step_count"] = state.get("step_count", 0) + 1
        if state["step_count"] > state.get("max_steps", 15):
            state["error"] = "Limite de passos atingido"
            state["intent"] = "error"
            return state

        last_message = state["messages"][-1]
        optimizer = get_optimizer()

        # Tentar classificação rápida (sem LLM)
        use_fast, fast_intent = optimizer.should_use_fast_classification(last_message.content)
        if use_fast and fast_intent:
            state["intent"] = fast_intent
            state["confidence"] = 0.85
            logger.info(f"[ROUTER] ⚡ Fast: {fast_intent}")
            return state

        # Classificação com LLM rápido (flash)
        user_ctx = state.get("user_context") or {}
        is_audio = user_ctx.is_audio if isinstance(user_ctx, UserContext) else False

        classification_prompt = ClassifierPrompts.get_classification_prompt(
            conversation_history=self._format_conversation(state),
            message=last_message.content,
            audio_hint=ClassifierPrompts.get_audio_hint(len(last_message.content)) if is_audio else "",
        )

        optimizer.track_call()
        response = self.llm_fast.invoke(classification_prompt)  # Usar LLM rápido

        try:
            json_start = response.content.find("{")
            json_end = response.content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                classification = json.loads(response.content[json_start:json_end])
                state["intent"] = classification.get("intent", "general")
                state["confidence"] = classification.get("confidence", 0.5)
                state["entities"] = classification.get("entities", {})
            else:
                state["intent"] = "general"
                state["confidence"] = 0.5
        except Exception as e:
            logger.error(f"Erro na classificação: {e}")
            state["intent"] = "general"
            state["confidence"] = 0.3

        logger.info(f"[ROUTER] 🎯 Intent: {state['intent']} ({state['confidence']:.0%})")
        return state

    def _route_by_intent(self, state: IRISState) -> str:
        """Determina próximo nó baseado na intenção."""
        if state.get("error"):
            return "error"
        return state.get("intent", "general")

    def _should_execute_tools(self, state: IRISState) -> str:
        """Decide se deve executar tools ou responder."""
        if state.get("error"):
            return "error"

        # Se há tool_calls pendentes, executar
        if state.get("tool_calls"):
            return "execute"

        return "respond"

    def _finance_agent_node(self, state: IRISState) -> IRISState:
        """Agente de finanças usando tools."""
        return self._process_with_tools(state, "finance")

    def _reminder_agent_node(self, state: IRISState) -> IRISState:
        """Agente de lembretes usando tools."""
        return self._process_with_tools(state, "reminder")

    def _meeting_agent_node(self, state: IRISState) -> IRISState:
        """Agente de reuniões usando tools."""
        return self._process_with_tools(state, "meeting")

    def _contact_agent_node(self, state: IRISState) -> IRISState:
        """Agente de contatos usando tools."""
        return self._process_with_tools(state, "contact")

    def _process_with_tools(self, state: IRISState, domain: str) -> IRISState:
        """
        Processa mensagem usando LLM com tools.
        O LLM decide qual tool chamar, ToolNode executa.
        """
        last_message = state["messages"][-1]

        # System prompt específico do domínio
        system_prompts = {
            "finance": """Você é um assistente especializado em finanças pessoais.

⚠️ REGRA OBRIGATÓRIA: Você DEVE chamar a tool registrar_transacao para CADA gasto/receita mencionado.
NUNCA responda apenas com texto. SEMPRE chame a tool primeiro, depois responda.

REGRAS CRÍTICAS:

1. VALORES EXATOS: Use EXATAMENTE o valor que o usuário informou.
   - "45 reais de uber" → registrar_transacao(valor=45, descricao="Uber")
   - "80 de café" → registrar_transacao(valor=80, descricao="Café da manhã")
   - "130 de almoço" → registrar_transacao(valor=130, descricao="Almoço")

2. MÚLTIPLAS TRANSAÇÕES: Chame registrar_transacao UMA VEZ PARA CADA valor.
   Exemplo: "uber 45, café 80, almoço 130" = TRÊS chamadas de tool separadas.

3. DESCRIÇÃO CURTA: Máximo 2-3 palavras.
   - "Uber para voltar para casa" → "Uber"
   - "Mensalidade da creche" → "Creche"

4. CONSULTAS: Use consultar_financas.
   - "gastos de janeiro" → consultar_financas(periodo="janeiro")

5. DELETAR: Use deletar_transacao.
   - "delete o uber" → deletar_transacao(descricao="uber")

LEMBRE-SE: Você DEVE chamar as tools. Não apenas responda com texto!""",
            "reminder": """Você é um assistente especializado em lembretes.

REGRAS CRÍTICAS OBRIGATÓRIAS:

1. HORÁRIO EXATO: Use EXATAMENTE o horário que o usuário informou. 
   - Se o usuário disse "8:20", use 08:20. NÃO mude para 8:40 ou qualquer outro horário.
   - Se o usuário disse "às 10h", use 10:00. NÃO arredonde.
   - NUNCA invente ou modifique horários. Use o que foi dito LITERALMENTE.

2. MÚLTIPLOS LEMBRETES: Chame criar_lembrete UMA VEZ PARA CADA lembrete.
   Exemplo: "Me lembra às 10h e às 14h" = DUAS chamadas de tool com horários 10:00 e 14:00.

3. FORMATO DE DATA/HORA: Use formato YYYY-MM-DD HH:MM
   - "amanhã às 8:20" → data de amanhã + 08:20
   - "hoje às 15h" → data de hoje + 15:00

4. NUNCA ALUCIINE: Se o usuário não informou um horário específico, PERGUNTE.
   NÃO invente horários. NÃO modifique valores informados.

5. CONFIRME OS DADOS: Antes de criar, repita o horário EXATO para o usuário.""",
            "meeting": """Você é um assistente especializado em reuniões.

REGRA CRÍTICA: Quando o usuário mencionar MÚLTIPLAS reuniões, você DEVE chamar a tool criar_reuniao UMA VEZ PARA CADA reunião.

NUNCA ignore nenhuma reunião mencionada. Registre TODAS.""",
            "contact": """Você é um assistente especializado em contatos e mensagens.

REGRAS CRÍTICAS:

1. CRIAR CONTATOS: Quando o usuário mencionar contatos com telefone, chame criar_contato.
   - "Adiciona João 11999998888 no grupo Funcionários" → criar_contato(nome="João", telefone="11999998888", grupo="Funcionários")
   - SEMPRE extraia o grupo mencionado (Família, Trabalho, Funcionários, Clientes, etc.)

2. MÚLTIPLOS CONTATOS: Chame criar_contato UMA VEZ PARA CADA contato.

3. AGENDAR MENSAGENS: Quando o usuário quiser enviar uma mensagem depois, use agendar_mensagem.
   - "Manda uma mensagem pro João amanhã às 9h dizendo bom dia" → agendar_mensagem()
   - "Envia para o grupo Funcionários às 18h: reunião cancelada" → agendar_mensagem(grupo="Funcionários")

4. ENVIAR PARA GRUPO: Se for para um grupo inteiro, use o parâmetro 'grupo' com o nome do grupo.

NUNCA ignore nenhum contato mencionado. Registre TODOS.""",
        }

        # Incluir contexto do usuário (contatos, finanças, etc) no prompt
        context_prompt = state.get("context_prompt", "")
        domain_prompt = system_prompts.get(domain, "")
        
        # Busca semântica nos documentos do usuário (RAG)
        rag_context = ""
        db = state.get("db")
        user_id = state.get("user_id")
        if db and user_id:
            try:
                from app.services.embedding_service import EmbeddingService
                embedding_service = EmbeddingService(db)
                rag_context = embedding_service.get_relevant_context(user_id, last_message.content, max_tokens=1500)
                if rag_context:
                    logger.debug(f"[RAG] Contexto encontrado ({len(rag_context)} chars)")
            except Exception as e:
                logger.debug(f"[RAG] Sem contexto: {e}")
        
        # Contexto de data/hora atual
        datetime_context = get_datetime_context()
        
        # Combinar prompt do domínio com contexto do usuário e RAG
        full_system_prompt = f"""{domain_prompt}

📅 DATA/HORA ATUAL: {datetime_context}

{context_prompt}

{rag_context}

IMPORTANTE: 
- Use a DATA/HORA ATUAL acima para registrar transações e lembretes.
- Se o usuário mencionar um nome (ex: Maria), verifique nos CONTATOS.
- Se a pergunta puder ser respondida com os DOCUMENTOS acima, use essas informações.
- NÃO peça informações que você já tem."""

        messages = [SystemMessage(content=full_system_prompt), last_message]

        # Chamar LLM com tools
        response = self.llm_with_tools.invoke(messages)

        # Verificar se há tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            state["tool_calls"] = response.tool_calls
            logger.info(f"[AGENT] 🛠️ Tools chamadas: {[tc['name'] for tc in response.tool_calls]}")
        else:
            # ⚠️ PROBLEMA: LLM respondeu sem chamar tools!
            logger.warning(f"[AGENT] ⚠️ LLM respondeu SEM chamar tools para intent={domain}!")
            logger.warning(f"[AGENT] Resposta: {response.content[:200] if response.content else 'vazio'}")
            state["messages"] = list(state["messages"]) + [response]

        return state

    def _tool_executor_node(self, state: IRISState) -> IRISState:
        """
        Executa as tools chamadas pelo LLM.
        Separação clara: LLM decide, este nó executa.
        """
        tool_calls = state.get("tool_calls", [])
        tool_results = []

        for tc in tool_calls:
            tool_name = tc.get("name", "")
            tool_args = tc.get("args", {})

            try:
                # Encontrar e executar a tool
                for tool in self.all_tools:
                    if tool.name == tool_name:
                        result = tool.invoke(tool_args)
                        tool_results.append({"tool": tool_name, "result": result, "success": True})
                        break
            except Exception as e:
                logger.error(f"Erro ao executar tool {tool_name}: {e}")
                tool_results.append({"tool": tool_name, "error": str(e), "success": False})

        state["tool_results"] = tool_results
        state["tool_calls"] = []  # Limpar após execução

        return state

    def _general_chat_node(self, state: IRISState) -> IRISState:
        """
        Conversa geral com acesso a tools de pesquisa, investimentos, consultas e RAG.
        Inclui: Web Search (Tavily), Investimentos (yFinance), Brasil API, Google Calendar.
        """
        last_message = state["messages"][-1]
        
        # Busca semântica nos documentos do usuário (RAG)
        rag_context = ""
        db = state.get("db")
        user_id = state.get("user_id")
        if db and user_id:
            try:
                from app.services.embedding_service import EmbeddingService
                embedding_service = EmbeddingService(db)
                rag_context = embedding_service.get_relevant_context(user_id, last_message.content, max_tokens=2000)
                if rag_context:
                    logger.debug(f"[RAG] Contexto geral ({len(rag_context)} chars)")
                    state["rag_context"] = rag_context
            except Exception as e:
                logger.debug(f"[RAG] Sem contexto geral")
        
        # Contexto de data/hora atual
        datetime_context = get_datetime_context()
        
        # System prompt com acesso às tools de pesquisa e consulta
        system_prompt = f"""Você é IRIS, assistente pessoal inteligente.

📅 DATA/HORA ATUAL: {datetime_context}

SUAS CAPACIDADES ESPECIAIS:
1. PESQUISA WEB: Use _search_web ou _search_news para buscar informações atualizadas na internet.
2. INVESTIMENTOS: Use _get_stock_price, _get_stock_info, _get_crypto_price, _get_currency_rate para dados financeiros.
   - Ações brasileiras: adicione .SA (ex: PETR4.SA, VALE3.SA)
   - Criptos: BTC, ETH, SOL
   - Câmbio: USD, EUR para BRL
3. BRASIL API:
   - _consultar_cep: Endereço completo por CEP
   - _consultar_clima: Previsão do tempo
   - _listar_feriados: Feriados nacionais
   - _consultar_taxas: Selic, CDI, IPCA
   - _listar_bancos / _consultar_banco: Códigos bancários
   - _consultar_fipe: Preços de veículos
4. GOOGLE CALENDAR: _listar_eventos, _criar_evento, _verificar_disponibilidade

{rag_context}

REGRAS:
- Se o usuário perguntar sobre algo que precisa de dados atualizados, USE as tools.
- Para investimentos, SEMPRE consulte dados reais, NUNCA invente valores.
- Responda de forma natural e útil."""

        messages = [SystemMessage(content=system_prompt), last_message]
        
        # Usar LLM com tools para poder acessar pesquisa, investimentos, etc.
        response = self.llm_with_tools.invoke(messages)
        
        # Verificar se há tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            state["tool_calls"] = response.tool_calls
            logger.info(f"[GENERAL] 🛠️ Tools: {[tc['name'] for tc in response.tool_calls]}")
        else:
            state["messages"] = list(state["messages"]) + [response]
        
        state["next_action"] = "general_response"
        return state

    def _response_formatter_node(self, state: IRISState) -> IRISState:
        """Formata resposta final para o usuário."""
        user_ctx = state.get("user_context")
        user_name = user_ctx.user_name if user_ctx else ""

        # Gerar resposta baseada nos resultados
        tool_results = state.get("tool_results", [])
        
        # DEBUG: Verificar se há tool_results pendentes
        logger.info(f"[FORMATTER] 🔍 Tool results pendentes: {len(tool_results)}")
        
        # Se já tem resposta do agente E não há tool_results para processar, retornar
        if state["messages"] and isinstance(state["messages"][-1], AIMessage) and not tool_results:
            logger.info("[FORMATTER] ⏭️ Resposta já existe e sem tool_results, pulando")
            return state

        if tool_results:
            # DEBUG: Log dos tool_results recebidos
            logger.info(f"[FORMATTER] 📦 Tool results recebidos: {len(tool_results)}")
            for tr in tool_results:
                logger.info(f"[FORMATTER] Tool: {tr.get('tool')} | Success: {tr.get('success')} | Result: {str(tr.get('result', {}))[:200]}")
            
            # Construir resposta baseada nos resultados das tools
            successful = [r for r in tool_results if r.get("success")]
            failed = [r for r in tool_results if not r.get("success")]

            # Agregar TODOS os resultados por tipo de ação
            finances_list = []
            reminders_list = []
            meetings_list = []
            contacts_list = []
            scheduled_messages_list = []

            # Lista para armazenar respostas diretas de tools de integração
            integration_responses = []
            
            for r in successful:
                result_data = r.get("result", {})
                
                # Se o resultado é string (tools de integração retornam strings diretas)
                if isinstance(result_data, str):
                    integration_responses.append(result_data)
                    continue
                
                # Se não é dict, pular
                if not isinstance(result_data, dict):
                    continue
                
                if result_data.get("status") == "pending_execution":
                    action = result_data.get("action", "")
                    
                    if action == "create_finance" and result_data.get("finance"):
                        finances_list.append(result_data["finance"])
                    elif action == "create_reminder" and result_data.get("reminder"):
                        reminders_list.append(result_data["reminder"])
                    elif action == "create_meeting" and result_data.get("meeting"):
                        meetings_list.append(result_data["meeting"])
                    elif action == "create_contact" and result_data.get("contact"):
                        contacts_list.append(result_data["contact"])
                    elif action == "schedule_message" and result_data.get("scheduled_message"):
                        scheduled_messages_list.append(result_data["scheduled_message"])
                    else:
                        # Ação única (consulta, delete, etc)
                        state["next_action"] = action
                        state["entities"] = result_data
                elif result_data.get("status") == "pending_calendar_action":
                    # Tools de Google Calendar retornam dict com status especial
                    state["calendar_action"] = result_data

            # Obter db e user_id do contexto
            db = state.get("db")
            user_id = state.get("user_id")

            # DEBUG: Log das listas agregadas
            logger.info(f"[FORMATTER] 📊 Agregados - Finances: {len(finances_list)}, Reminders: {len(reminders_list)}, Meetings: {len(meetings_list)}, Contacts: {len(contacts_list)}")
            
            # Executar saves no banco de dados
            if db and user_id:
                logger.info(f"[SAVE] 🔗 DB e user_id disponíveis: user_id={user_id}")
                # Salvar finanças
                if finances_list:
                    from app.services.finance_service import FinanceService
                    finance_service = FinanceService(db)
                    for finance in finances_list:
                        try:
                            logger.info(f"[SAVE] 💰 Salvando: {finance}")
                            finance_service.create_from_entities(user_id, finance)
                            logger.info(f"[SAVE] ✅ Finança salva: {finance.get('description')}")
                        except Exception as e:
                            logger.error(f"[SAVE] ❌ Erro ao salvar finança: {e}")

                # Salvar lembretes
                if reminders_list:
                    from app.services.reminder_service import ReminderService
                    reminder_service = ReminderService(db)
                    for reminder in reminders_list:
                        try:
                            reminder_service.create_from_entities(user_id, reminder)
                            logger.info(f"[SAVE] ⏰ Lembrete: {reminder.get('title')}")
                        except Exception as e:
                            logger.error(f"Erro ao salvar lembrete: {e}")

                # Salvar reuniões
                if meetings_list:
                    from app.services.meeting_service import MeetingService
                    meeting_service = MeetingService(db)
                    for meeting in meetings_list:
                        try:
                            meeting_service.create_from_entities(user_id, meeting)
                            logger.info(f"[SAVE] 📅 Reunião: {meeting.get('title')}")
                        except Exception as e:
                            logger.error(f"Erro ao salvar reunião: {e}")

                # Salvar contatos
                if contacts_list:
                    from app.services.contact_service import ContactService
                    contact_service = ContactService(db)
                    for contact in contacts_list:
                        try:
                            contact_service.create_from_dict(user_id, contact)
                            logger.info(f"[SAVE] 👤 Contato: {contact.get('name')}")
                        except Exception as e:
                            logger.error(f"Erro ao salvar contato: {e}")

                # Salvar mensagens agendadas
                if scheduled_messages_list:
                    from app.services.scheduled_message_service import ScheduledMessageService
                    scheduled_service = ScheduledMessageService(db)
                    for msg in scheduled_messages_list:
                        try:
                            scheduled_service.create_from_entities(user_id, msg)
                            logger.info(f"[SAVE] 📨 Agendamento: {msg.get('recipient_name') or msg.get('group_name')}")
                        except Exception as e:
                            logger.error(f"Erro ao agendar mensagem: {e}")

            # Definir ações para resposta
            if len(finances_list) > 1:
                state["next_action"] = "create_finances"
                state["entities"] = {"finances": finances_list}
            elif len(finances_list) == 1:
                state["next_action"] = "create_finance"
                state["entities"] = {"finance": finances_list[0]}

            if len(reminders_list) > 1:
                state["next_action"] = "create_reminders"
                state["entities"] = {"reminders": reminders_list}
            elif len(reminders_list) == 1:
                state["next_action"] = "create_reminder"
                state["entities"] = {"reminder": reminders_list[0]}

            if len(meetings_list) > 1:
                state["next_action"] = "create_meetings"
                state["entities"] = {"meetings": meetings_list}
            elif len(meetings_list) == 1:
                state["next_action"] = "create_meeting"
                state["entities"] = {"meeting": meetings_list[0]}

            if len(contacts_list) > 1:
                state["next_action"] = "create_contacts"
                state["entities"] = {"contacts": contacts_list}
            elif len(contacts_list) == 1:
                state["next_action"] = "create_contact"
                state["entities"] = {"contact": contacts_list[0]}

            if len(scheduled_messages_list) > 1:
                state["next_action"] = "schedule_messages"
                state["entities"] = {"scheduled_messages": scheduled_messages_list}
            elif len(scheduled_messages_list) == 1:
                state["next_action"] = "schedule_message"
                state["entities"] = {"scheduled_message": scheduled_messages_list[0]}

            if failed:
                logger.warning(f"Alguns itens falharam: {failed}")

            # Se temos respostas de tools de integração (clima, busca, etc), usar diretamente
            if integration_responses:
                # Combinar todas as respostas de integração
                integration_context = "\n\n".join(integration_responses)
                
                # Gerar resposta humanizada baseada nos dados das integrações
                integration_prompt = f"""Você é IRIS, assistente pessoal.

DADOS OBTIDOS DAS FERRAMENTAS:
{integration_context}

PERGUNTA DO USUÁRIO:
{state["messages"][-1].content if state["messages"] else ""}

Responda de forma natural e amigável, usando os dados acima. Seja conciso."""

                response = self.llm.invoke(integration_prompt)
                state["messages"] = list(state["messages"]) + [AIMessage(content=response.content)]
                return state

            # Gerar resposta humanizada (incluindo contexto RAG se disponível)
            response_prompt = ResponsePrompts.get_response_generation_prompt(
                user_name=user_name,
                comm_style="",
                context_prompt=state.get("context_prompt", ""),
                next_action=state.get("next_action", ""),
                entities=state.get("entities", {}),
                last_message=state["messages"][-1].content if state["messages"] else "",
                rag_context=state.get("rag_context", ""),
            )

            response = self.llm.invoke(response_prompt)
            state["messages"] = list(state["messages"]) + [AIMessage(content=response.content)]
        else:
            # Resposta para chat geral (incluindo RAG)
            response_prompt = ResponsePrompts.get_response_generation_prompt(
                user_name=user_name,
                comm_style="",
                context_prompt=state.get("context_prompt", ""),
                next_action="general_response",
                entities={},
                last_message=state["messages"][-1].content if state["messages"] else "",
                rag_context=state.get("rag_context", ""),
            )
            response = self.llm.invoke(response_prompt)
            state["messages"] = list(state["messages"]) + [AIMessage(content=response.content)]

        return state

    def _error_handler_node(self, state: IRISState) -> IRISState:
        """Trata erros de forma amigável."""
        error = state.get("error", "Erro desconhecido")
        logger.error(f"Erro no grafo: {error}")

        error_message = (
            "Desculpe, ocorreu um erro ao processar sua solicitação. "
            "Por favor, tente novamente ou reformule sua mensagem."
        )

        state["messages"] = list(state["messages"]) + [AIMessage(content=error_message)]
        return state

    def _format_conversation(self, state: IRISState) -> str:
        """Formata histórico de conversa."""
        memory_ctx = state.get("memory_context")
        if not memory_ctx:
            return ""

        conversation = memory_ctx.conversation if hasattr(memory_ctx, "conversation") else []
        if not conversation:
            return ""

        lines = []
        for msg in conversation[-5:]:
            role = "Usuário" if msg.get("role") == "user" else "Assistente"
            content = msg.get("content", "")[:150]
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    async def process_message(
        self, user_id: int, session_id: str, message: str, context: dict = None, db: Optional[Session] = None
    ) -> dict:
        """
        Processa mensagem do usuário.

        Args:
            user_id: ID do usuário
            session_id: ID da sessão
            message: Mensagem do usuário
            context: Contexto adicional
            db: Sessão do banco

        Returns:
            Dict com response, intent, entities, next_action
        """
        import time
        start_time = time.time()
        
        # Preview da mensagem (primeiros 50 chars)
        msg_preview = message[:50] + "..." if len(message) > 50 else message
        logger.info(f"[IRIS] ▶️ Processando: \"{msg_preview}\" (user={user_id})")
        
        enriched_context = context or {}
        memory_manager = None

        # Enriquecer contexto
        if db:
            enriched_context["db"] = db
            memory_manager = MemoryManager(db, user_id)
            memory_context = memory_manager.get_full_context()
            enriched_context["memory"] = memory_context
            enriched_context["context_prompt"] = memory_manager.build_context_prompt()

        # Criar estado inicial
        initial_state = create_initial_state(
            user_id=user_id, session_id=session_id, message=message, context=enriched_context
        )

        # Configuração com thread_id para persistência
        config = get_thread_config(user_id, session_id)

        # Executar grafo
        result = await self.graph.ainvoke(initial_state, config=config)

        response_text = result["messages"][-1].content if result["messages"] else "Erro ao processar mensagem."

        # Aprender com a interação
        if memory_manager:
            memory_manager.learn_from_message(
                message=message,
                intent=result.get("intent", ""),
                entities=result.get("entities", {}),
                response=response_text,
            )

        # Log de conclusão com timing
        elapsed = time.time() - start_time
        intent = result.get("intent", "general")
        logger.info(f"[IRIS] ✅ Concluído em {elapsed:.1f}s | Intent: {intent} | Resposta: {len(response_text)} chars")

        return {
            "response": response_text,
            "intent": result.get("intent", "general"),
            "entities": result.get("entities", {}),
            "next_action": result.get("next_action", ""),
            "confidence": result.get("confidence", 0.0),
        }


# Singleton para reutilização
_graph_instance: Optional[IRISGraphV2] = None


def get_iris_graph() -> IRISGraphV2:
    """Retorna instância singleton do grafo."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = IRISGraphV2()
    return _graph_instance
