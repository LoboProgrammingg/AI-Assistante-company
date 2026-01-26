"""
Templates de resposta para evitar chamadas LLM desnecessárias.

Princípio: Respostas simples e previsíveis não precisam de LLM.
"""

from typing import Any, Dict, Optional


class ResponseTemplates:
    """Templates de resposta para ações comuns."""
    
    # ==================== FINANÇAS ====================
    
    @staticmethod
    def finance_created(data: Dict[str, Any], user_name: str = "") -> str:
        amount = data.get("amount", 0)
        desc = data.get("description", "")
        category = data.get("category", "")
        tipo = data.get("type", "expense")
        
        emoji = "💸" if tipo == "expense" else "💰"
        tipo_text = "Gasto" if tipo == "expense" else "Receita"
        
        lines = [f"{emoji} *{tipo_text} registrado!*", "", f"📝 {desc}", f"💵 R$ {amount:,.2f}"]
        if category:
            lines.append(f"📂 {category}")
        return "\n".join(lines)
    
    @staticmethod
    def finance_summary(summary: Dict[str, Any], periodo: str) -> str:
        s = summary.get("summary", {})
        total_expense = s.get("total_expense", 0)
        total_income = s.get("total_income", 0)
        balance = s.get("balance", 0)
        count = s.get("count", 0)
        
        periodo_text = {"hoje": "de hoje", "semana": "da semana", "mes": "do mês", "ano": "do ano", "tudo": "totais"}.get(periodo, f"de {periodo}")
        
        if count == 0:
            return f"📊 Nenhuma transação encontrada {periodo_text}."
        
        emoji = "🟢" if balance >= 0 else "🔴"
        return f"📊 *Resumo financeiro {periodo_text}*\n\n💸 Gastos: R$ {total_expense:,.2f}\n💰 Receitas: R$ {total_income:,.2f}\n{emoji} Saldo: R$ {balance:,.2f}\n\n_{count} transação(ões)_"
    
    # ==================== LEMBRETES ====================
    
    @staticmethod
    def reminder_created(data: Dict[str, Any]) -> str:
        return f"⏰ *Lembrete criado!*\n\n📝 {data.get('title', '')}\n📅 {data.get('scheduled_time', '')}"
    
    @staticmethod
    def reminder_list(reminders: list, total: int) -> str:
        if not reminders:
            return "📭 Você não tem lembretes pendentes."
        
        lines = ["⏰ *Seus lembretes:*", ""]
        for r in reminders[:10]:
            time = r.get("scheduled_time", "")
            if hasattr(time, "strftime"):
                time = time.strftime("%d/%m %H:%M")
            lines.append(f"• {r.get('title', '')} - {time}")
        
        if total > 10:
            lines.append(f"\n_+{total - 10} lembretes_")
        return "\n".join(lines)
    
    # ==================== CALENDAR ====================
    
    @staticmethod
    def event_created(data: Dict[str, Any]) -> str:
        title = data.get("summary", data.get("title", "Reunião"))
        start = data.get("start", {})
        datetime_str = start.get("dateTime", "")[:16] if isinstance(start, dict) else str(start)
        meet_link = data.get("hangoutLink", "")
        
        lines = [f"📅 *Evento criado!*", "", f"📝 {title}", f"🕐 {datetime_str}"]
        if meet_link:
            lines.append(f"🔗 {meet_link}")
        return "\n".join(lines)
    
    @staticmethod
    def event_list(events: list, dias: int) -> str:
        if not events:
            return f"📅 Nenhum evento nos próximos {dias} dias."
        
        lines = [f"📅 *Próximos eventos ({dias} dias):*", ""]
        for e in events[:10]:
            start = e.get("start", {})
            datetime_str = start.get("dateTime", "")[:16] if isinstance(start, dict) else ""
            lines.append(f"• {e.get('summary', 'Sem título')} - {datetime_str}")
        return "\n".join(lines)
    
    # ==================== CONTATOS ====================
    
    @staticmethod
    def contact_created(data: Dict[str, Any]) -> str:
        name = data.get("name", "")
        group = data.get("group_name", "")
        msg = f"👤 Contato *{name}* salvo"
        if group:
            msg += f" no grupo _{group}_"
        return msg + "!"
    
    @staticmethod
    def contact_list(contacts: list, total: int) -> str:
        if not contacts:
            return "📭 Nenhum contato encontrado."
        
        lines = ["👥 *Seus contatos:*", ""]
        for c in contacts[:20]:
            name = c.get("name", "") if isinstance(c, dict) else getattr(c, "name", "")
            group = c.get("group_name", "") if isinstance(c, dict) else getattr(c, "group_name", "")
            lines.append(f"• {name}{f' ({group})' if group else ''}")
        
        if total > 20:
            lines.append(f"\n_+{total - 20} contatos_")
        return "\n".join(lines)
    
    # ==================== TODOIST ====================
    
    @staticmethod
    def todoist_task_created(data: Dict[str, Any]) -> str:
        content = data.get("content", "")
        due = data.get("due", {})
        due_string = due.get("string", "") if isinstance(due, dict) else ""
        msg = f"✅ Tarefa criada: *{content}*"
        if due_string:
            msg += f"\n📅 {due_string}"
        return msg
    
    @staticmethod
    def todoist_task_list(tasks: list) -> str:
        if not tasks:
            return "📭 Nenhuma tarefa encontrada."
        
        lines = ["📋 *Suas tarefas:*", ""]
        for t in tasks[:10]:
            due = t.get("due", {})
            due_str = due.get("string", "") if due else ""
            lines.append(f"• {t.get('content', '')}{f' ({due_str})' if due_str else ''}")
        
        if len(tasks) > 10:
            lines.append(f"\n_+{len(tasks) - 10} tarefas_")
        return "\n".join(lines)
    
    # ==================== ERROS ====================
    
    @staticmethod
    def error_generic(action: str, error: str) -> str:
        action_names = {
            "create_finance": "registrar transação",
            "query_finance": "consultar finanças",
            "create_reminder": "criar lembrete",
            "create_event": "criar evento",
            "create_contact": "salvar contato",
            "create_todoist_task": "criar tarefa",
        }
        return f"❌ Não consegui {action_names.get(action, action)}.\n\n_{error}_"
    
    # ==================== SAUDAÇÕES ====================
    
    @staticmethod
    def greeting(hour: int) -> str:
        if 5 <= hour < 12:
            return "Bom dia! ☀️ Como posso ajudar?"
        elif 12 <= hour < 18:
            return "Boa tarde! 👋 Como posso ajudar?"
        return "Boa noite! 🌙 Como posso ajudar?"
    
    @staticmethod
    def thanks() -> str:
        return "Por nada! 😊 Estou aqui se precisar de algo mais."


def get_template(action_type: str, data: Dict[str, Any] = None, error: str = None, **kwargs) -> Optional[str]:
    """Retorna template apropriado para a ação."""
    data = data or {}
    
    templates = {
        "create_finance": lambda: ResponseTemplates.finance_created(data, kwargs.get("user_name", "")),
        "query_finance": lambda: ResponseTemplates.finance_summary(data, kwargs.get("periodo", "mes")),
        "create_reminder": lambda: ResponseTemplates.reminder_created(data),
        "list_reminders": lambda: ResponseTemplates.reminder_list(data.get("reminders", []), data.get("total", 0)),
        "create_event": lambda: ResponseTemplates.event_created(data),
        "list_events": lambda: ResponseTemplates.event_list(data.get("events", []), kwargs.get("dias", 7)),
        "create_contact": lambda: ResponseTemplates.contact_created(data),
        "list_contacts": lambda: ResponseTemplates.contact_list(data.get("contacts", []), data.get("total", 0)),
        "create_todoist_task": lambda: ResponseTemplates.todoist_task_created(data),
        "list_todoist_tasks": lambda: ResponseTemplates.todoist_task_list(data.get("tasks", [])),
    }
    
    if error:
        return ResponseTemplates.error_generic(action_type, error)
    
    template_func = templates.get(action_type)
    if template_func:
        try:
            return template_func()
        except Exception:
            return None
    return None
