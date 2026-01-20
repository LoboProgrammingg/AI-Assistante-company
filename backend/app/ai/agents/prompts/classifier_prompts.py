"""
Prompts para classificação de intenções do usuário.
Centralizados aqui para fácil manutenção e visualização.
"""


class ClassifierPrompts:
    """Prompts utilizados pelo classificador de intenções."""

    @staticmethod
    def get_classification_prompt(
        conversation_history: str,
        message: str,
        audio_hint: str = ""
    ) -> str:
        """
        Gera o prompt de classificação de intenção.
        
        Args:
            conversation_history: Histórico da conversa formatado
            message: Mensagem atual do usuário (truncada em 1000 chars)
            audio_hint: Dica adicional se for áudio longo
        """
        return f"""
Você é um assistente especializado em classificar intenções de mensagens.
Analise a mensagem ATUAL do usuário considerando o CONTEXTO da conversa anterior.

HISTÓRICO DA CONVERSA (últimas mensagens):
{conversation_history if conversation_history else "Sem histórico anterior"}

MENSAGEM ATUAL DO USUÁRIO: "{message[:1000]}"
{audio_hint}

REGRAS DE CLASSIFICAÇÃO:
1. Se o usuário menciona VALORES em reais (R$, reais), PREÇOS ou GASTOS → finance
2. Se menciona HORÁRIO, DATA, AGENDAR, LEMBRAR, compromisso → reminder
3. Se menciona REUNIÃO, TRANSCRIÇÃO, ATAS ou parece uma discussão longa com participantes → meeting
4. Se menciona CONTATO, SALVAR NÚMERO, ADICIONAR PESSOA, TELEFONE de alguém, grupo de pessoas → contact
5. Se é uma CONTINUAÇÃO de uma conversa anterior (ex: "sim", "prossiga", "ok"), 
   MANTENHA a mesma intenção do histórico
6. Apenas classifique como "general" se REALMENTE for conversa casual

Intenções:
- reminder: Agendamentos, lembretes, compromissos, horários
- finance: Gastos, receitas, valores, dinheiro, preços
- meeting: Transcrições de reuniões, resumos de reunião, discussões longas
- contact: Adicionar contatos, salvar números, gerenciar pessoas/grupos
- general: Apenas conversas gerais sem ação específica

Retorne APENAS JSON válido:
{{
    "intent": "reminder|finance|meeting|contact|general",
    "confidence": 0.0-1.0,
    "entities": {{}},
    "reasoning": "breve explicação da classificação"
}}
"""

    @staticmethod
    def get_audio_hint(message_length: int) -> str:
        """Retorna dica para áudios longos."""
        if message_length > 500:
            return "\nATENÇÃO: Esta mensagem veio de um ÁUDIO LONGO. Se parecer uma transcrição de reunião ou discussão com múltiplos participantes, classifique como 'meeting'."
        return ""
