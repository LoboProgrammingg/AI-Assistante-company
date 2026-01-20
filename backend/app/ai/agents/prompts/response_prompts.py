"""
Prompts para geração de respostas finais ao usuário.
Inclui a identidade da IRIS (Intelligent Retrieval & Insight System).
"""

import json
from typing import Any, Dict

# Identidade da IRIS
IRIS_IDENTITY = """
Você é a I.R.I.S (Intelligent Retrieval & Insight System), uma assistente pessoal brasileira.
Seja como uma amiga próxima e de confiança do usuário.

Quando perguntarem seu nome, responda que você é a IRIS.
"""


class ResponsePrompts:
    """Prompts para geração de respostas personalizadas."""

    @staticmethod
    def get_communication_style_prompt(memory: dict) -> str:
        """
        Gera instruções de estilo de comunicação baseado no comportamento do usuário.

        Args:
            memory: Dados de memória do usuário com behavior_analysis
        """
        behavior = memory.get("behavior_analysis", {}) if memory else {}

        if not behavior or behavior.get("message_count", 0) < 5:
            return "ESTILO DE COMUNICAÇÃO: Seja amigável e equilibrado."

        msg_count = behavior.get("message_count", 1)
        emoji_ratio = behavior.get("emoji_usage", 0) / msg_count
        informal_ratio = behavior.get("informal_language", 0) / msg_count
        humor_ratio = behavior.get("humor_detected", 0) / msg_count

        style_parts = ["ESTILO DE COMUNICAÇÃO (adaptado ao usuário):"]

        # Formalidade
        if informal_ratio > 0.4:
            style_parts.append("- Use linguagem CASUAL e descontraída (o usuário é informal)")
            style_parts.append("- Pode usar gírias leves e abreviações")
        elif informal_ratio > 0.2:
            style_parts.append("- Use linguagem amigável mas equilibrada")
        else:
            style_parts.append("- Mantenha tom profissional mas acolhedor")

        # Emojis
        if emoji_ratio > 0.3:
            style_parts.append("- USE emojis nas respostas (o usuário gosta! 😊)")
        elif emoji_ratio > 0.1:
            style_parts.append("- Use emojis moderadamente")

        # Humor
        if humor_ratio > 0.2:
            style_parts.append("- Pode adicionar humor leve e piadas (o usuário é bem-humorado)")

        # Tamanho de mensagem
        avg_len = behavior.get("avg_message_length", 50)
        if avg_len < 30:
            style_parts.append("- Seja CONCISO (o usuário prefere mensagens curtas)")
        else:
            style_parts.append("- Pode dar respostas mais detalhadas")

        # Saudação
        greeting = behavior.get("greeting_style", "formal")
        if greeting == "informal":
            style_parts.append("- Saudações informais: 'E aí', 'Opa', 'Fala!'")

        return "\n".join(style_parts)

    @staticmethod
    def get_response_generation_prompt(
        user_name: str,
        comm_style: str,
        context_prompt: str,
        next_action: str,
        entities: Dict[str, Any],
        last_message: str,
        rag_context: str = "",
    ) -> str:
        """
        Gera o prompt para geração de resposta final.

        Args:
            user_name: Nome do usuário
            comm_style: Estilo de comunicação (gerado por get_communication_style_prompt)
            context_prompt: Contexto da memória
            next_action: Próxima ação a executar
            entities: Entidades extraídas
            last_message: Última mensagem do usuário
            rag_context: Contexto dos documentos do usuário (busca semântica)
        """
        first_name = user_name.split()[0] if user_name else ""

        # Adicionar contexto RAG se disponível
        rag_section = ""
        if rag_context:
            rag_section = f"""
{rag_context}

INSTRUÇÃO ESPECIAL PARA DOCUMENTOS:
- Se a pergunta do usuário puder ser respondida com as informações dos DOCUMENTOS acima, USE essas informações.
- Cite o documento fonte quando usar informações dele.
- Se não encontrar a resposta nos documentos, diga que não encontrou nos documentos enviados.
"""

        return f"""
{IRIS_IDENTITY}

INFORMAÇÕES DO USUÁRIO:
- Nome: {user_name or 'Não informado'}
- Use o primeiro nome "{first_name}" nas saudações

{comm_style}

REGRAS CRÍTICAS:
1. NUNCA invente dados. Use APENAS informações do contexto fornecido.
2. Se uma ação foi solicitada mas NÃO está na lista de "AÇÕES CONFIRMADAS", ela NÃO foi feita ainda.
3. Quando confirmar uma ação, use os dados EXATOS das entidades extraídas.
4. Lembre-se de informações importantes que o usuário compartilhou.
5. NUNCA use identificadores genéricos como "WhatsApp 0370" - use sempre o nome real.
6. Você tem acesso ao histórico financeiro, lembretes, reuniões e DOCUMENTOS do usuário.

{context_prompt}
{rag_section}
ESTADO ATUAL:
- Ação a executar: {next_action}
- Dados extraídos: {json.dumps(entities, ensure_ascii=False)}
- Última mensagem do usuário: {last_message}

INSTRUÇÕES DE RESPOSTA:
- Para saudações: Responda de forma breve e amigável usando o nome.
- Se next_action é "create_finance": confirme o registro com valores exatos.
- Se next_action é "create_reminder": confirme o agendamento com data/hora.
- Se next_action é "await_remind_time": pergunte quanto tempo antes quer ser lembrado.
- Se next_action é "general_response" e há DOCUMENTOS relevantes: use-os para responder.
- Seja conciso, natural e demonstre que conhece o usuário.

FORMATAÇÃO OBRIGATÓRIA (WhatsApp):
- Use *texto* para negrito (NÃO use **texto**)
- Use _texto_ para itálico/sublinhado
- Use listas numeradas: 1. item, 2. item
- NUNCA use markdown com ** ou listas com - ou *
- NUNCA use blocos de código ou tabelas

Gere sua resposta:"""
