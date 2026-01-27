"""
Prompts para classificação de intenções do usuário.
Centralizados aqui para fácil manutenção e visualização.
"""


class ClassifierPrompts:
    """Prompts utilizados pelo classificador de intenções."""

    @staticmethod
    def get_classification_prompt(conversation_history: str, message: str, audio_hint: str = "") -> str:
        """
        Gera o prompt de classificação de intenção.

        Args:
            conversation_history: Histórico da conversa formatado
            message: Mensagem atual do usuário (truncada em 1000 chars)
            audio_hint: Dica adicional se for áudio longo
        """
        return f"""Classifique a intenção da mensagem do usuário.

HISTÓRICO: {conversation_history if conversation_history else "Sem histórico"}

MENSAGEM: "{message[:1000]}"
{audio_hint}

## REGRAS DE CLASSIFICAÇÃO:

### 🔴 TAREFA vs LEMBRETE (CRÍTICO!):
- "Anota/cria/adiciona uma TAREFA" → task (gerenciador interno)
- "To-do", "lista de tarefas" → task
- "Me LEMBRA de algo" / "LEMBRETE" → reminder (notificação com horário)
- "Agenda/marca um COMPROMISSO" → calendar (Google Calendar)

### 📌 INTENÇÕES:

**finance** - Dinheiro e gastos:
- Valores em R$, gastos, receitas, preços
- "Gastei 50 no uber", "Recebi 1000"
- Delete/edite gastos

**reminder** - Lembretes com notificação:
- "Me lembra às 10h", "Lembrete de tomar remédio"
- Notificações em horários específicos
- Delete/edite lembretes

**task** - Tarefas e to-do:
- "Cria uma tarefa", "Anota pra fazer"
- "Minhas tarefas", "Lista de pendências"
- Coisas a fazer sem horário específico

**calendar** - Eventos no Google Calendar:
- "Agenda uma reunião", "Marca evento"
- "Agende no Google Calendar", "Reunião com clientes"
- Eventos que precisam de convites ou links

**transcription** - APENAS transcrições longas:
- Textos longos com diálogos de reuniões
- "Resuma essa reunião", "Analise a transcrição"
- NÃO é para agendar reuniões!

**general** - TODO O RESTO:
- Perguntas gerais, conversas
- Pesquisas na web
- Qualquer dúvida ou pedido de informação

⚠️ NA DÚVIDA → general (a IA é inteligente e resolve)

JSON:
{{"intent": "finance|reminder|task|calendar|general", "confidence": 0.0-1.0, "entities": {{}}, "reasoning": "..."}}
"""

    @staticmethod
    def get_audio_hint(message_length: int) -> str:
        """Retorna dica para áudios longos."""
        if message_length > 500:
            return "\nATENÇÃO: Esta mensagem veio de um ÁUDIO LONGO. Se parecer uma transcrição de reunião ou discussão com múltiplos participantes, classifique como 'meeting'."
        return ""
