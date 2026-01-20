"""
Prompts para o agente de lembretes.
"""


class ReminderPrompts:
    """Prompts utilizados pelo ReminderAgent."""

    SYSTEM_PROMPT = """Você é um assistente especializado em gerenciar lembretes e compromissos.

Suas responsabilidades:
1. Interpretar pedidos de lembretes em linguagem natural
2. Extrair data, hora e descrição do compromisso
3. Entender preferências de antecedência (lembrar X minutos/horas antes)
4. Identificar padrões de recorrência (diário, semanal, etc.)

Regras importantes:
- Sempre confirme os detalhes extraídos com o usuário
- Se a data/hora não for clara, peça esclarecimento
- Use o timezone do usuário para interpretar horários
- Seja amigável e prestativo nas respostas

Tipos de recorrência disponíveis:
- once: único
- daily: diário
- weekdays: segunda a sexta
- weekends: sábado e domingo
- weekly: semanal
- monthly: mensal
- yearly: anual"""

    @staticmethod
    def get_extraction_prompt(context: str, current_time: str, message: str) -> str:
        """
        Gera prompt para extração de lembretes da mensagem.
        
        Args:
            context: Contexto formatado do usuário
            current_time: Data/hora atual formatada
            message: Mensagem do usuário
        """
        return f"""
Analise a mensagem do usuário e extraia informações de TODOS os lembretes mencionados.
IMPORTANTE: O usuário pode pedir MÚLTIPLOS lembretes em uma única mensagem!

CONTEXTO:
{context}
Data/Hora atual: {current_time}

MENSAGEM DO USUÁRIO:
"{message}"

Extraia as informações e retorne APENAS um JSON válido:
{{
    "reminders": [
        {{
            "title": "título do lembrete",
            "description": "descrição adicional ou null",
            "scheduled_time": "YYYY-MM-DDTHH:MM:SS" (no timezone do usuário),
            "remind_before_minutes": número de minutos para lembrar antes (0 se não especificado),
            "recurrence_type": "once|daily|weekdays|weekends|weekly|monthly|yearly"
        }}
    ],
    "confidence": 0.0 a 1.0,
    "needs_clarification": true/false,
    "clarification_question": "pergunta se precisar de esclarecimento ou null"
}}

EXEMPLOS:
- "agende reunião das 8h e das 14h amanhã" → 2 lembretes
- "me lembre do almoço às 12h e da reunião às 15h" → 2 lembretes
- "não me deixe esquecer da consulta às 10h, reunião às 14h e academia às 18h" → 3 lembretes

Se não conseguir extrair informações suficientes, defina needs_clarification como true.
"""

    @staticmethod
    def get_delete_identification_prompt(message: str, reminders_text: str) -> str:
        """
        Gera prompt para identificar qual lembrete deletar.
        
        Args:
            message: Mensagem do usuário
            reminders_text: Lista de lembretes formatada
        """
        return f"""
Identifique qual lembrete o usuário quer cancelar.

MENSAGEM DO USUÁRIO: "{message}"

LEMBRETES ATIVOS:
{reminders_text}

Retorne APENAS JSON:
{{
    "reminder_id": número ou null se não identificar,
    "title_match": "título do lembrete identificado"
}}
"""

    # Templates de resposta
    TEMPLATES = {
        "single_reminder_time_ask": (
            "⏰ Vou agendar: *{title}* para {scheduled_time}\n\n"
            "Quanto tempo antes você quer ser lembrado?\n\n"
            "1. Na hora\n"
            "2. 5 minutos antes\n"
            "3. 15 minutos antes\n"
            "4. 30 minutos antes\n"
            "5. 1 hora antes\n\n"
            "_Responda com o número ou digite o tempo (ex: 20 min)_"
        ),
        "multiple_reminder_time_ask": (
            "⏰ Vou agendar {count} lembretes:\n\n{titles}\n\n"
            "Quanto tempo antes você quer ser lembrado?\n\n"
            "1. Na hora\n"
            "2. 5 minutos antes\n"
            "3. 15 minutos antes\n"
            "4. 30 minutos antes\n"
            "5. 1 hora antes\n\n"
            "_Responda com o número (aplicarei para todos)_"
        ),
        "single_confirmation": (
            "✅ *Lembrete agendado!*\n\n"
            "📌 {title}\n"
            "📅 {scheduled_time}\n"
            "⏰ Vou te avisar: _{remind_time}_\n\n"
            "Pode ficar tranquilo, eu te lembro! 😉"
        ),
        "multiple_confirmation": (
            "✅ *{count} lembretes agendados!*\n\n"
            "{items}\n\n"
            "⏰ Vou te avisar: _{remind_time}_ de cada um\n\n"
            "Pode ficar tranquilo! 😉"
        ),
        "delete_success": "✅ Lembrete cancelado: **{title}** (agendado para {scheduled})",
        "no_reminders": "📋 Você não tem lembretes ativos para cancelar.",
        "clarification_needed": "Poderia me dar mais detalhes sobre o lembrete?",
    }
