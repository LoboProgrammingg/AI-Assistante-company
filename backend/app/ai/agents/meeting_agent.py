import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from app.ai.agents.base_agent import BaseAgent
from app.utils.timezone_helper import get_current_time_for_user

logger = logging.getLogger(__name__)


class MeetingAgent(BaseAgent):
    """Agente especializado em reuniões - agendamento e análise."""

    def __init__(self):
        super().__init__(
            name="MeetingAgent",
            description="Especialista em agendar reuniões e analisar transcrições",
            temperature=0.3
        )

    @property
    def system_prompt(self) -> str:
        return """Você é um assistente especializado em reuniões.

Suas responsabilidades:
1. AGENDAR reuniões (horário, título, participantes)
2. Resumir transcrições de reuniões
3. Extrair action items de reuniões

Regras:
- Sempre confirme o agendamento com data, hora e título
- Seja objetivo e conciso
- Mantenha o contexto da conversa anterior"""

    def _get_conversation_history(self, context: Dict[str, Any]) -> str:
        """Extrai histórico de conversa do contexto."""
        memory = context.get("memory", {})
        conversation = memory.get("conversation", [])
        
        if not conversation:
            return ""
        
        lines = []
        for msg in conversation[-8:]:
            role = "Usuário" if msg.get("role") == "user" else "Assistente"
            content = msg.get("content", "")[:300]
            lines.append(f"{role}: {content}")
        
        return "\n".join(lines)

    def process_sync(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa mensagem de reunião - agendamento ou análise."""
        
        user_timezone = context.get("timezone", "America/Sao_Paulo")
        current_time = get_current_time_for_user(user_timezone)
        conversation_history = self._get_conversation_history(context)
        
        # Verificar se há reunião pendente (aguardando confirmação)
        pending_meeting = context.get("pending_meeting")
        
        # Primeiro, classificar a intenção
        intent_prompt = f"""
Analise a mensagem do usuário sobre reunião.

HISTÓRICO DA CONVERSA (IMPORTANTE - MANTENHA O CONTEXTO):
{conversation_history if conversation_history else "Sem histórico"}

DATA/HORA ATUAL: {current_time.strftime("%d/%m/%Y %H:%M")} ({current_time.strftime("%A")})

MENSAGEM ATUAL: "{message}"

{"REUNIÃO PENDENTE AGUARDANDO CONFIRMAÇÃO: " + json.dumps(pending_meeting, ensure_ascii=False) if pending_meeting else ""}

Determine a intenção:
1. "schedule" - agendar/marcar nova reunião (mencionou horário, data ou título)
2. "confirm" - confirmando algo do histórico (ex: "sim", "ok", "pode ser", "isso", "confirma")
3. "analyze" - analisar transcrição de reunião (texto longo, parece uma conversa/discussão)
4. "clarify" - precisa de mais informações

IMPORTANTE: Se o usuário disser "sim", "ok", "pode ser", "confirma" após uma pergunta sobre reunião no histórico, 
a intenção é "confirm" e você deve usar os dados do histórico/pending_meeting.

Retorne APENAS JSON:
{{
    "intent": "schedule|confirm|analyze|clarify",
    "reasoning": "explicação breve"
}}
"""
        intent_response = self.invoke_llm_sync(intent_prompt)
        
        try:
            json_start = intent_response.find("{")
            json_end = intent_response.rfind("}") + 1
            intent_data = json.loads(intent_response[json_start:json_end])
        except:
            intent_data = {"intent": "clarify"}
        
        intent = intent_data.get("intent", "clarify")
        logger.info(f"MeetingAgent intent: {intent} - {intent_data.get('reasoning', '')}")
        
        # Se é confirmação e temos reunião pendente, criar
        if intent == "confirm" and pending_meeting:
            return self._create_meeting_from_pending(pending_meeting, current_time)
        
        # Se é agendamento, extrair dados
        if intent == "schedule" or intent == "confirm":
            return self._handle_schedule(message, context, current_time, conversation_history)
        
        # Se é análise de transcrição longa
        if intent == "analyze" and len(message) > 200:
            return self._handle_analysis(message, context)
        
        # Precisa mais informações
        return {
            "response": "Para agendar uma reunião, me diga:\n📅 Data (ex: hoje, amanhã, segunda)\n⏰ Horário (ex: 14h, 15:30)\n📝 Título/Assunto (opcional)",
            "entities": {},
            "next_action": "await_clarification",
            "confidence": 0.3
        }

    def _handle_schedule(
        self,
        message: str,
        context: Dict[str, Any],
        current_time,
        conversation_history: str
    ) -> Dict[str, Any]:
        """Processa agendamento de reunião."""
        
        extraction_prompt = f"""
Extraia os detalhes da reunião a ser agendada.

HISTÓRICO (USE PARA COMPLETAR INFORMAÇÕES FALTANTES):
{conversation_history}

DATA/HORA ATUAL: {current_time.strftime("%d/%m/%Y %H:%M")} (Ano: {current_time.year})

MENSAGEM: "{message}"

REGRAS:
- Se o usuário confirmar "sim/ok" para uma data mencionada no histórico, USE essa data
- "hoje" = {current_time.strftime("%Y-%m-%d")}
- "amanhã" = {(current_time + timedelta(days=1)).strftime("%Y-%m-%d")}
- Se só tiver hora, assuma hoje
- Se faltar título, use "Reunião"

Retorne APENAS JSON:
{{
    "title": "título da reunião",
    "scheduled_time": "YYYY-MM-DD HH:MM",
    "participants": ["participante1", "participante2"] ou [],
    "description": "descrição ou null",
    "has_all_info": true/false,
    "missing": ["lista do que falta"] ou []
}}
"""
        response = self.invoke_llm_sync(extraction_prompt)
        
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            extracted = json.loads(response[json_start:json_end])
        except:
            return {
                "response": "Não consegui entender os detalhes. Pode repetir? Ex: 'Reunião às 14h de hoje'",
                "entities": {},
                "next_action": "await_clarification",
                "confidence": 0.0
            }
        
        # Se tem todas as informações, criar reunião
        if extracted.get("has_all_info") and extracted.get("scheduled_time"):
            title = extracted.get("title", "Reunião")
            scheduled = extracted.get("scheduled_time")
            
            try:
                meeting_datetime = datetime.strptime(scheduled, "%Y-%m-%d %H:%M")
                formatted_date = meeting_datetime.strftime("%d/%m/%Y às %H:%M")
            except:
                formatted_date = scheduled
            
            confirmation = f"✅ *Reunião agendada!*\n\n📝 {title}\n📅 {formatted_date}"
            
            if extracted.get("participants"):
                confirmation += f"\n👥 Participantes: {', '.join(extracted['participants'])}"
            
            return {
                "response": confirmation,
                "entities": {"meeting": extracted},
                "next_action": "create_meeting",
                "confidence": 0.9
            }
        
        # Se falta informação, perguntar e salvar pending
        missing = extracted.get("missing", [])
        
        if not extracted.get("scheduled_time"):
            return {
                "response": f"Para qual data e horário você gostaria de agendar a reunião '{extracted.get('title', 'Reunião')}'?",
                "entities": {"pending_meeting": extracted},
                "next_action": "await_meeting_time",
                "confidence": 0.6
            }
        
        return {
            "response": "Poderia confirmar os detalhes da reunião?",
            "entities": {"pending_meeting": extracted},
            "next_action": "await_clarification",
            "confidence": 0.5
        }

    def _create_meeting_from_pending(self, pending: Dict, current_time) -> Dict[str, Any]:
        """Cria reunião a partir de dados pendentes confirmados."""
        title = pending.get("title", "Reunião")
        scheduled = pending.get("scheduled_time")
        
        if not scheduled:
            # Assume hoje se não tiver data
            scheduled = current_time.strftime("%Y-%m-%d") + " " + pending.get("time", "14:00")
        
        try:
            meeting_datetime = datetime.strptime(scheduled, "%Y-%m-%d %H:%M")
            formatted_date = meeting_datetime.strftime("%d/%m/%Y às %H:%M")
        except:
            formatted_date = scheduled
        
        confirmation = f"✅ *Reunião agendada!*\n\n📝 {title}\n📅 {formatted_date}"
        
        return {
            "response": confirmation,
            "entities": {"meeting": pending},
            "next_action": "create_meeting",
            "confidence": 0.95
        }

    def _handle_analysis(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa análise de transcrição de reunião."""
        transcription = context.get("transcription") or message

        analysis_prompt = f"""
Analise a seguinte transcrição de reunião:

---
{transcription}
---

Extraia todas as informações relevantes e retorne APENAS um JSON válido:
{{
    "title": "título sugerido para a reunião",
    "summary": "resumo executivo em 2-3 parágrafos",
    "duration_estimate": número estimado de minutos (ou null),
    "key_topics": [
        {{"topic": "tópico 1", "summary": "breve resumo do que foi discutido"}}
    ],
    "action_items": [
        {{
            "task": "descrição da tarefa",
            "responsible": "nome do responsável ou null",
            "deadline": "prazo mencionado ou null",
            "priority": "high|medium|low"
        }}
    ],
    "participants": [
        {{"name": "nome identificado", "role": "papel na reunião ou null"}}
    ],
    "decisions": [
        {{"decision": "decisão tomada", "context": "contexto da decisão"}}
    ],
    "keywords": ["palavra1", "palavra2"],
    "sentiment": "positive|neutral|negative",
    "confidence": 0.0 a 1.0
}}

Seja detalhado na análise. Se não conseguir identificar algo, use null ou lista vazia.
"""

        try:
            response = self.invoke_llm_sync(analysis_prompt)
            
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                extracted = json.loads(response[json_start:json_end])
            else:
                raise ValueError("JSON não encontrado na resposta")
                
        except Exception as e:
            logger.error(f"Erro ao analisar reunião: {e}")
            extracted = {
                "title": "Reunião",
                "summary": "Não foi possível gerar um resumo automático.",
                "key_topics": [],
                "action_items": [],
                "participants": [],
                "decisions": [],
                "keywords": [],
                "sentiment": "neutral",
                "confidence": 0.3
            }

        summary_response = self._format_summary_response(extracted)

        return {
            "response": summary_response,
            "entities": {"meeting": extracted},
            "next_action": "create_meeting",
            "confidence": extracted.get("confidence", 0.7)
        }

    async def process(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Wrapper async para process_sync."""
        return self.process_sync(message, context)

    def _format_summary_response(self, data: Dict[str, Any]) -> str:
        """Formata resposta amigável com o resumo da reunião (formatação WhatsApp)."""
        
        parts = ["📋 *Análise da Reunião*\n"]
        
        if data.get("title"):
            parts.append(f"*Título:* {data['title']}\n")
        
        if data.get("summary"):
            parts.append(f"\n*Resumo:*\n{data['summary']}\n")
        
        if data.get("key_topics"):
            parts.append("\n*Tópicos Principais:*")
            for i, topic in enumerate(data["key_topics"][:5], 1):
                parts.append(f"{i}. {topic.get('topic', 'N/A')}")
        
        if data.get("action_items"):
            parts.append("\n\n*Tarefas Identificadas:*")
            for i, item in enumerate(data["action_items"][:5], 1):
                task = item.get("task", "N/A")
                responsible = item.get("responsible", "A definir")
                parts.append(f"{i}. {task} _({responsible})_")
        
        if data.get("decisions"):
            parts.append("\n\n*Decisões Tomadas:*")
            for i, decision in enumerate(data["decisions"][:3], 1):
                parts.append(f"{i}. {decision.get('decision', 'N/A')}")
        
        parts.append("\n\n✅ Reunião salva com sucesso!")
        
        return "\n".join(parts)

    def extract_entities(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extrai entidades de forma síncrona."""
        return {}
