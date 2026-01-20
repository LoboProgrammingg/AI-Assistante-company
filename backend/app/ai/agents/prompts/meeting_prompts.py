"""
Prompts para o agente de reuniões.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class MeetingPrompts:
    """Prompts utilizados pelo MeetingAgent."""

    SYSTEM_PROMPT = """Você é um assistente especializado em reuniões.

Suas responsabilidades:
1. AGENDAR reuniões (horário, título, participantes)
2. Resumir transcrições de reuniões
3. Extrair action items de reuniões

Regras:
- Sempre confirme o agendamento com data, hora e título
- Seja objetivo e conciso
- Mantenha o contexto da conversa anterior"""

    @staticmethod
    def get_intent_prompt(
        conversation_history: str,
        current_time: datetime,
        message: str,
        pending_meeting: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Gera prompt para classificar intenção de reunião.

        Args:
            conversation_history: Histórico da conversa
            current_time: Data/hora atual
            message: Mensagem do usuário
            pending_meeting: Reunião pendente (se existir)
        """
        pending_json = json.dumps(pending_meeting, ensure_ascii=False) if pending_meeting else ""
        pending_text = f"REUNIÃO PENDENTE AGUARDANDO CONFIRMAÇÃO: {pending_json}" if pending_meeting else ""

        return f"""
Analise a mensagem do usuário sobre reunião.

HISTÓRICO DA CONVERSA (IMPORTANTE - MANTENHA O CONTEXTO):
{conversation_history if conversation_history else "Sem histórico"}

DATA/HORA ATUAL: {current_time.strftime("%d/%m/%Y %H:%M")} ({current_time.strftime("%A")})

MENSAGEM ATUAL: "{message}"

{pending_text}

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

    @staticmethod
    def get_schedule_extraction_prompt(conversation_history: str, current_time: datetime, message: str) -> str:
        """
        Gera prompt para extração de dados de agendamento.

        Args:
            conversation_history: Histórico da conversa
            current_time: Data/hora atual
            message: Mensagem do usuário
        """
        tomorrow = current_time + timedelta(days=1)

        return f"""
Extraia os detalhes da reunião a ser agendada.

HISTÓRICO (USE PARA COMPLETAR INFORMAÇÕES FALTANTES):
{conversation_history}

DATA/HORA ATUAL: {current_time.strftime("%d/%m/%Y %H:%M")} (Ano: {current_time.year})

MENSAGEM: "{message}"

REGRAS:
- Se o usuário confirmar "sim/ok" para uma data mencionada no histórico, USE essa data
- "hoje" = {current_time.strftime("%Y-%m-%d")}
- "amanhã" = {tomorrow.strftime("%Y-%m-%d")}
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

    @staticmethod
    def get_analysis_prompt(transcription: str) -> str:
        """
        Gera prompt para análise de transcrição.

        Args:
            transcription: Transcrição da reunião
        """
        return f"""
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

    # Templates de resposta
    TEMPLATES = {
        "schedule_success": ("✅ *Reunião agendada!*\n\n" "📝 {title}\n" "📅 {formatted_date}"),
        "schedule_with_participants": "\n👥 Participantes: {participants}",
        "ask_time": "Para qual data e horário você gostaria de agendar a reunião '{title}'?",
        "ask_details": (
            "Para agendar uma reunião, me diga:\n"
            "📅 Data (ex: hoje, amanhã, segunda)\n"
            "⏰ Horário (ex: 14h, 15:30)\n"
            "📝 Título/Assunto (opcional)"
        ),
        "analysis_header": "📋 *Análise da Reunião*\n",
        "analysis_title": "*Título:* {title}\n",
        "analysis_summary": "\n*Resumo:*\n{summary}\n",
        "analysis_topics_header": "\n*Tópicos Principais:*",
        "analysis_topic_item": "{i}. {topic}",
        "analysis_actions_header": "\n\n*Tarefas Identificadas:*",
        "analysis_action_item": "{i}. {task} _({responsible})_",
        "analysis_decisions_header": "\n\n*Decisões Tomadas:*",
        "analysis_decision_item": "{i}. {decision}",
        "analysis_footer": "\n\n✅ Reunião salva com sucesso!",
    }
