"""
Prompts para o agente de contatos.
"""


class ContactPrompts:
    """Prompts utilizados pelo ContactAgent."""

    @staticmethod
    def get_intent_classification_prompt(history: str, message: str) -> str:
        """
        Gera prompt para classificar intenção de contato.
        
        Args:
            history: Histórico da conversa
            message: Mensagem do usuário
        """
        return f"""Classifique a intenção do usuário relacionada a CONTATOS.

HISTÓRICO:
{history if history else "Sem histórico"}

MENSAGEM: "{message}"

INTENÇÕES POSSÍVEIS:
1. schedule_message - AGENDAR envio de mensagem para um contato em horário específico (ex: "manda mensagem pra Maruza às 14h", "envia para João amanhã às 9h")
2. send_broadcast - Enviar mensagem AGORA para um GRUPO de contatos (ex: "manda mensagem pros funcionários", "avisa a família que...")
3. create_contact - Salvar/adicionar um novo contato
4. list_groups - Listar grupos de contatos existentes
5. list_contacts - Listar contatos (de um grupo específico ou todos)

Retorne APENAS JSON:
{{
    "intent": "schedule_message|send_broadcast|create_contact|list_groups|list_contacts",
    "contact_name": "nome do contato para agendar" ou null,
    "group_names": ["lista de grupos mencionados"] ou null,
    "message_to_send": "mensagem a ser enviada" ou null,
    "scheduled_time": "horário extraído (ex: '14:00', '09:30', 'amanhã às 10h')" ou null,
    "phone_number": "telefone" ou null
}}

EXEMPLOS:
- "manda mensagem pra Maruza às 14h: reunião confirmada" → intent=schedule_message, contact_name="Maruza", scheduled_time="14:00", message_to_send="reunião confirmada"
- "envia para João amanhã às 9h dizendo bom dia" → intent=schedule_message, contact_name="João", scheduled_time="amanhã às 9h", message_to_send="bom dia"
- "manda pros funcionários: reunião amanhã" → intent=send_broadcast, group_names=["funcionarios"], message_to_send="reunião amanhã"
- "salva João 11999998888 como funcionário" → intent=create_contact, contact_name="João", phone_number="11999998888", group_names=["funcionario"]
"""

    @staticmethod
    def get_contact_extraction_prompt(history: str, message: str) -> str:
        """
        Gera prompt para extração de informações de contato.
        
        Args:
            history: Histórico da conversa
            message: Mensagem do usuário
        """
        return f"""Extraia informações de TODOS os contatos mencionados na mensagem.
IMPORTANTE: O usuário pode mencionar MÚLTIPLOS contatos em uma única mensagem!

HISTÓRICO DA CONVERSA:
{history if history else "Sem histórico"}

MENSAGEM ATUAL: "{message}"

O usuário pode usar QUALQUER nome de grupo (não precisa ser de uma lista fixa).
Exemplos de grupos: funcionários, família, amigos, clientes, fornecedores, equipe, etc.

Retorne APENAS JSON:
{{
    "contacts": [
        {{
            "name": "nome do contato",
            "phone_number": "telefone do contato",
            "group_name": "grupo mencionado ou null"
        }}
    ],
    "group_name_global": "grupo mencionado para todos os contatos ou null"
}}

EXEMPLOS:
- "Salva João (11999998888) e Maria (11888887777) como funcionários" → 2 contatos
- "Adiciona Maruza Lobo Lima (5565981407734) / Kleber Camara (5565956320582) no grupo funcionários" → 2 contatos
- "Meus funcionários: Ana 11999999999, Pedro 11888888888, Carlos 11777777777" → 3 contatos

REGRAS:
- Extraia TODOS os contatos mencionados
- Extraia números de telefone mesmo sem formatação
- Se o grupo for mencionado uma vez, aplique para todos
- Se não mencionar grupo, deixe null (será "outros" por padrão)
"""

    # Templates de resposta
    TEMPLATES = {
        "contact_saved": (
            "✅ *Contato salvo!*\n\n"
            "👤 {name}\n"
            "📱 {phone}\n"
            "👥 {group}"
        ),
        "multiple_contacts_saved": (
            "✅ *{count} contatos salvos!*\n\n"
            "{contacts_list}\n\n"
            "👥 Grupo: {group}"
        ),
        "contact_not_found": (
            "❌ Não encontrei o contato *{name}*.\n\n"
            "Você pode adicionar com:\n"
            "_Salva {name} 11999998888 como amigo_"
        ),
        "ask_name": "📱 Número anotado: *{phone}*\n\nQual é o nome desse contato?",
        "ask_phone": "👤 Nome anotado: *{name}*\n\nQual é o número de telefone?",
        "ask_message": "Qual mensagem você quer enviar para *{recipient}*?",
        "ask_time": "A que horas você quer que eu envie a mensagem para *{recipient}*?",
        "message_scheduled": (
            "✅ *Mensagem agendada!*\n\n"
            "👤 Para: {recipient}\n"
            "⏰ Horário: {time} ({date})\n"
            "💬 Mensagem: _{message}_"
        ),
        "no_groups": (
            "📋 Você ainda não tem grupos de contatos.\n\n"
            "Para criar, adicione um contato:\n"
            "_Salva João 11999998888 como funcionário_"
        ),
        "groups_list_header": "📋 *Seus grupos de contatos:*\n\n",
        "group_item": "👥 *{name}* - {count} contato(s)\n",
        "groups_footer": (
            "\n_Para ver contatos de um grupo:_ listar funcionários\n"
            "_Para enviar mensagem:_ manda pros funcionários: sua mensagem"
        ),
        "no_contacts": (
            "📋 Você ainda não tem contatos salvos.\n\n"
            "Para adicionar:\n"
            "_Salva João 11999998888 como funcionário_"
        ),
        "contacts_list_header": "📋 *Seus contatos:* ({total} total)\n\n",
        "contact_item": "👤 *{name}* ({group}) - {phone}\n",
        "no_contacts_in_group": "📋 Nenhum contato encontrado no grupo *{group}*.",
        "broadcast_no_contacts": (
            "⚠️ Nenhum contato encontrado no(s) grupo(s): *{groups}*\n\n"
            "Você pode adicionar contatos dizendo:\n"
            "_Salva João 11999998888 como funcionário_"
        ),
        "need_info": (
            "Para salvar um contato, preciso do *nome* e *número de telefone*.\n\n"
            "Exemplo: _Salva o contato João 11999998888 como funcionário_"
        ),
        "error": "Desculpe, não consegui processar. Pode repetir o nome e telefone do contato?",
    }
