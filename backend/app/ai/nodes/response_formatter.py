"""
Response Formatter Node - Formatação de respostas.

Responsável por:
- Formatar resposta final para o usuário
- Processar resultados das tools
- Salvar dados no banco (finanças, lembretes, etc)
- Gerar resposta humanizada via LLM
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from langchain_core.messages import AIMessage

from app.ai.agents.prompts.response_prompts import ResponsePrompts
from app.ai.state import IRISState

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class ResponseFormatterNode:
    """Nó responsável pela formatação de respostas."""

    def __init__(self, llm: "ChatGoogleGenerativeAI"):
        """
        Args:
            llm: LLM principal para geração de respostas
        """
        self.llm = llm

    def format(self, state: IRISState) -> dict:
        """
        Formata resposta final para o usuário.
        
        IMPORTANTE: Retorna dict com atualizações (estado imutável - padrão LangGraph)
        """
        user_ctx = state.get("user_context")
        user_name = user_ctx.user_name if user_ctx else ""

        tool_results = state.get("tool_results", [])

        logger.info(f"[FORMATTER] 🔍 Tool results pendentes: {len(tool_results)}")

        # Se já tem resposta do agente E não há tool_results para processar, retornar vazio
        if state["messages"] and isinstance(state["messages"][-1], AIMessage) and not tool_results:
            logger.info("[FORMATTER] ⏭️ Resposta já existe e sem tool_results, pulando")
            return {}

        if tool_results:
            return self._process_tool_results(state, tool_results, user_name)
        else:
            return self._generate_general_response(state, user_name)

    def _process_tool_results(
        self, state: IRISState, tool_results: List[Dict], user_name: str
    ) -> dict:
        """Processa resultados das tools e gera resposta."""
        logger.info(f"[FORMATTER] 📦 Tool results recebidos: {len(tool_results)}")
        for tr in tool_results:
            logger.info(
                f"[FORMATTER] Tool: {tr.get('tool')} | "
                f"Success: {tr.get('success')} | "
                f"Result: {str(tr.get('result', {}))[:200]}"
            )

        successful = [r for r in tool_results if r.get("success")]
        failed = [r for r in tool_results if not r.get("success")]

        # Agregar resultados por tipo e executar ações pendentes
        aggregated = self._aggregate_results(successful, state)

        # Salvar no banco de dados
        db = state.get("db")
        user_id = state.get("user_id")
        if db and user_id:
            self._save_to_database(db, user_id, aggregated)

        # Extrair ações (sem mutar estado)
        next_action, entities = self._get_state_actions(aggregated)

        if failed:
            logger.warning(f"Alguns itens falharam: {failed}")

        # Processar respostas de integrações
        if aggregated["integration_responses"]:
            return self._handle_integration_responses(state, aggregated["integration_responses"])

        # Gerar resposta humanizada - retornar dict imutável
        return self._generate_tool_response(state, user_name, next_action, entities)

    def _aggregate_results(self, successful: List[Dict], state: IRISState) -> Dict[str, Any]:
        """Agrega resultados das tools por tipo e executa ações pendentes."""
        aggregated = {
            "finances": [],
            "reminders": [],
            "meetings": [],
            "contacts": [],
            "scheduled_messages": [],
            "integration_responses": [],
            "calendar_actions": [],
            "query_results": [],  # Resultados de consultas
            "action_results": [],  # Resultados de delete/update
        }

        db = state.get("db")
        user_id = state.get("user_id")

        for r in successful:
            result_data = r.get("result", {})

            # Se o resultado é string (tools de integração retornam strings diretas)
            if isinstance(result_data, str):
                aggregated["integration_responses"].append(result_data)
                continue

            # Se não é dict, pular
            if not isinstance(result_data, dict):
                continue

            if result_data.get("status") == "pending_execution":
                action = result_data.get("action", "")
                
                # Executar ações que precisam de banco de dados
                if db and user_id:
                    executed = self._execute_pending_action(db, user_id, action, result_data)
                    if executed:
                        aggregated["query_results"].append(executed)
                        continue
                
                # Agregar ações de criação para salvar depois
                self._aggregate_by_action(aggregated, action, result_data)
                
            elif result_data.get("status") == "pending_calendar_action":
                aggregated["calendar_actions"].append(result_data)

        return aggregated

    def _execute_pending_action(self, db: Any, user_id: int, action: str, result_data: Dict) -> Optional[Dict]:
        """
        Executa ações pendentes no banco de dados.
        Retorna resultado da execução ou None se não é uma ação de execução.
        """
        try:
            # ========== FINANÇAS ==========
            if action == "query_finance":
                from app.services.finance_service import FinanceService
                service = FinanceService(db)
                filters = result_data.get("filters", {})
                
                periodo = filters.get("periodo", "mes")
                ano = filters.get("ano")
                busca = filters.get("busca")
                
                summary = service.get_summary_by_period(user_id, periodo, ano, busca)
                logger.info(f"[EXECUTE] 📊 Query finance: período={periodo}, resultado={summary.get('summary', {})}")
                
                return {
                    "action": "query_finance",
                    "success": True,
                    "data": summary,
                }
                
            elif action == "delete_finance":
                from app.services.finance_service import FinanceService
                service = FinanceService(db)
                filters = result_data.get("filters", {})
                
                result = service.delete_by_filters(user_id, filters)
                logger.info(f"[EXECUTE] 🗑️ Delete finance: {result}")
                
                return {
                    "action": "delete_finance",
                    "success": result.get("deleted_count", 0) > 0,
                    "data": result,
                }
                
            elif action == "update_finance":
                from app.services.finance_service import FinanceService
                service = FinanceService(db)
                filters = result_data.get("filters", {})
                updates = result_data.get("updates", {})
                
                result = service.update_by_filters(user_id, filters, updates)
                logger.info(f"[EXECUTE] ✏️ Update finance: {result}")
                
                return {
                    "action": "update_finance",
                    "success": result.get("success", False),
                    "data": result,
                }
            
            # ========== LEMBRETES ==========
            elif action == "list_reminders":
                from app.services.reminder_service import ReminderService
                service = ReminderService(db)
                filters = result_data.get("filters", {})
                
                status = "active" if filters.get("apenas_pendentes", True) else "all"
                reminders, total = service.list_by_user(user_id, status=status, limit=20)
                
                # Converter para dicionários serializáveis
                reminders_data = [
                    {
                        "id": r.id,
                        "title": r.title,
                        "scheduled_time": r.scheduled_time.isoformat() if r.scheduled_time else None,
                        "is_completed": r.is_completed,
                    }
                    for r in reminders
                ]
                logger.info(f"[EXECUTE] ⏰ List reminders: {len(reminders_data)} encontrados")
                
                return {
                    "action": "list_reminders",
                    "success": True,
                    "data": {"reminders": reminders_data, "count": total},
                }
                
            elif action == "delete_reminder":
                from app.services.reminder_service import ReminderService
                service = ReminderService(db)
                filters = result_data.get("filters", {})
                
                result = service.delete_by_filters(user_id, filters)
                logger.info(f"[EXECUTE] 🗑️ Delete reminder: {result}")
                
                return {
                    "action": "delete_reminder",
                    "success": result.get("deleted_count", 0) > 0,
                    "data": result,
                }
            
            # ========== REUNIÕES ==========
            elif action == "list_meetings":
                from app.services.meeting_service import MeetingService
                service = MeetingService(db)
                
                meetings, total = service.list_by_user(user_id, limit=20)
                
                # Converter para dicionários serializáveis
                meetings_data = [
                    {
                        "id": m.id,
                        "title": m.title,
                        "scheduled_time": m.scheduled_time.isoformat() if m.scheduled_time else None,
                        "participants": m.participants,
                    }
                    for m in meetings
                ]
                logger.info(f"[EXECUTE] 📅 List meetings: {len(meetings_data)} encontradas")
                
                return {
                    "action": "list_meetings",
                    "success": True,
                    "data": {"meetings": meetings_data, "count": total},
                }
            
            # ========== CONTATOS ==========
            elif action == "list_contacts":
                from app.services.contact_service import ContactService
                service = ContactService(db)
                filters = result_data.get("filters", {})
                
                result = service.list(
                    user_id, 
                    group_name=filters.get("grupo"),
                    search=filters.get("busca"),
                    limit=50
                )
                
                # Converter para dicionários serializáveis
                contacts_data = [
                    {
                        "id": c.id,
                        "name": c.name,
                        "phone_number": c.phone_number,
                        "group_name": c.group_name,
                    }
                    for c in result.get("items", [])
                ]
                logger.info(f"[EXECUTE] 👤 List contacts: {len(contacts_data)} encontrados")
                
                return {
                    "action": "list_contacts",
                    "success": True,
                    "data": {"contacts": contacts_data, "count": result.get("total", 0)},
                }
                
            elif action == "delete_contact":
                from app.services.contact_service import ContactService
                service = ContactService(db)
                filters = result_data.get("filters", {})
                
                # Buscar contato por nome
                nome = filters.get("nome", "").lower().strip()
                result = service.list(user_id, search=nome, limit=1)
                items = result.get("items", [])
                
                if items:
                    contact = items[0]
                    service.delete(user_id, contact.id)
                    logger.info(f"[EXECUTE] 🗑️ Delete contact: {contact.name}")
                    return {
                        "action": "delete_contact",
                        "success": True,
                        "data": {"deleted": contact.name},
                    }
                else:
                    return {
                        "action": "delete_contact",
                        "success": False,
                        "data": {"error": "Contato não encontrado"},
                    }
            
            # ========== MENSAGENS AGENDADAS ==========
            elif action == "list_scheduled_messages":
                from app.services.scheduled_message_service import ScheduledMessageService
                service = ScheduledMessageService(db)
                filters = result_data.get("filters", {})
                
                status = filters.get("status")
                messages = service.list(user_id, status=status)
                
                logger.info(f"[EXECUTE] 📨 List scheduled messages: {len(messages)} encontradas")
                
                return {
                    "action": "list_scheduled_messages",
                    "success": True,
                    "data": {"messages": messages, "count": len(messages)},
                }
            
            # ========== TODOIST ==========
            elif action == "create_todoist_task":
                import asyncio
                from app.services.todoist_service import get_todoist_service
                service = get_todoist_service()
                task_data = result_data.get("task", {})
                
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    task = loop.run_until_complete(service.create_task(
                        content=task_data.get("content"),
                        description=task_data.get("description"),
                        due_string=task_data.get("due_string"),
                        priority=task_data.get("priority", 1),
                        labels=task_data.get("labels"),
                    ))
                    loop.close()
                    
                    if task:
                        logger.info(f"[EXECUTE] ✅ Todoist task criada: {task.get('content')}")
                        return {
                            "action": "create_todoist_task",
                            "success": True,
                            "data": {"task": task, "message": f"Tarefa '{task.get('content')}' criada no Todoist!"},
                        }
                except Exception as e:
                    logger.error(f"[EXECUTE] ❌ Erro ao criar tarefa Todoist: {e}")
                    
                return {
                    "action": "create_todoist_task",
                    "success": False,
                    "error": "Erro ao criar tarefa no Todoist",
                }
            
            elif action == "list_todoist_tasks":
                import asyncio
                from app.services.todoist_service import get_todoist_service
                service = get_todoist_service()
                filters = result_data.get("filters", {})
                filter_str = filters.get("filter", "today")
                
                if filter_str == "all":
                    filter_str = None
                
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    tasks = loop.run_until_complete(service.get_tasks(filter_str=filter_str))
                    loop.close()
                    
                    logger.info(f"[EXECUTE] 📋 Todoist tasks: {len(tasks)} encontradas")
                    return {
                        "action": "list_todoist_tasks",
                        "success": True,
                        "data": {"tasks": tasks, "count": len(tasks)},
                    }
                except Exception as e:
                    logger.error(f"[EXECUTE] ❌ Erro ao listar tarefas Todoist: {e}")
                    return {
                        "action": "list_todoist_tasks",
                        "success": False,
                        "error": str(e),
                    }
            
            elif action == "complete_todoist_task":
                import asyncio
                from app.services.todoist_service import get_todoist_service
                service = get_todoist_service()
                filters = result_data.get("filters", {})
                titulo_ou_id = filters.get("titulo_ou_id", "")
                
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    tasks = loop.run_until_complete(service.get_tasks())
                    
                    matching_task = None
                    for task in tasks:
                        if titulo_ou_id.lower() in task["content"].lower() or task["id"] == titulo_ou_id:
                            matching_task = task
                            break
                    
                    if matching_task:
                        success = loop.run_until_complete(service.complete_task(matching_task["id"]))
                        loop.close()
                        if success:
                            logger.info(f"[EXECUTE] ✅ Todoist task concluída: {matching_task['content']}")
                            return {
                                "action": "complete_todoist_task",
                                "success": True,
                                "data": {"message": f"Tarefa '{matching_task['content']}' concluída!"},
                            }
                    else:
                        loop.close()
                except Exception as e:
                    logger.error(f"[EXECUTE] ❌ Erro ao concluir tarefa Todoist: {e}")
                
                return {
                    "action": "complete_todoist_task",
                    "success": False,
                    "error": f"Tarefa '{titulo_ou_id}' não encontrada",
                }
            
            elif action == "update_todoist_task":
                import asyncio
                from app.services.todoist_service import get_todoist_service
                service = get_todoist_service()
                filters = result_data.get("filters", {})
                updates = result_data.get("updates", {})
                titulo = filters.get("titulo", "")
                
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    tasks = loop.run_until_complete(service.get_tasks())
                    
                    matching_task = None
                    for task in tasks:
                        if titulo.lower() in task["content"].lower():
                            matching_task = task
                            break
                    
                    if matching_task:
                        success = loop.run_until_complete(service.update_task(
                            task_id=matching_task["id"],
                            content=updates.get("content"),
                            due_string=updates.get("due_string"),
                            priority=updates.get("priority"),
                        ))
                        loop.close()
                        if success:
                            logger.info(f"[EXECUTE] ✏️ Todoist task atualizada: {matching_task['content']}")
                            return {
                                "action": "update_todoist_task",
                                "success": True,
                                "data": {"message": f"Tarefa '{matching_task['content']}' atualizada!"},
                            }
                    else:
                        loop.close()
                except Exception as e:
                    logger.error(f"[EXECUTE] ❌ Erro ao atualizar tarefa Todoist: {e}")
                
                return {
                    "action": "update_todoist_task",
                    "success": False,
                    "error": f"Tarefa '{titulo}' não encontrada",
                }
            
            elif action == "delete_todoist_task":
                import asyncio
                from app.services.todoist_service import get_todoist_service
                service = get_todoist_service()
                filters = result_data.get("filters", {})
                titulo_ou_id = filters.get("titulo_ou_id", "")
                
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    tasks = loop.run_until_complete(service.get_tasks())
                    
                    matching_task = None
                    for task in tasks:
                        if titulo_ou_id.lower() in task["content"].lower() or task["id"] == titulo_ou_id:
                            matching_task = task
                            break
                    
                    if matching_task:
                        success = loop.run_until_complete(service.delete_task(matching_task["id"]))
                        loop.close()
                        if success:
                            logger.info(f"[EXECUTE] 🗑️ Todoist task deletada: {matching_task['content']}")
                            return {
                                "action": "delete_todoist_task",
                                "success": True,
                                "data": {"message": f"Tarefa '{matching_task['content']}' deletada!"},
                            }
                    else:
                        loop.close()
                except Exception as e:
                    logger.error(f"[EXECUTE] ❌ Erro ao deletar tarefa Todoist: {e}")
                
                return {
                    "action": "delete_todoist_task",
                    "success": False,
                    "error": f"Tarefa '{titulo_ou_id}' não encontrada",
                }
            
            elif action == "check_todoist_alerts":
                import asyncio
                from app.services.todoist_service import get_todoist_service
                service = get_todoist_service()
                
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    alerts = loop.run_until_complete(service.check_deadlines())
                    loop.close()
                    
                    logger.info(f"[EXECUTE] ⚠️ Todoist alerts: {len(alerts)} encontrados")
                    return {
                        "action": "check_todoist_alerts",
                        "success": True,
                        "data": {"alerts": alerts, "count": len(alerts)},
                    }
                except Exception as e:
                    logger.error(f"[EXECUTE] ❌ Erro ao verificar alertas Todoist: {e}")
                    return {
                        "action": "check_todoist_alerts",
                        "success": False,
                        "error": str(e),
                    }
                
        except Exception as e:
            logger.error(f"[EXECUTE] ❌ Erro ao executar {action}: {e}")
            return {
                "action": action,
                "success": False,
                "error": str(e),
            }
        
        return None  # Ação não é de execução (ex: create_finance)

    def _aggregate_by_action(
        self, aggregated: Dict[str, List], action: str, result_data: Dict
    ) -> None:
        """Agrega resultado baseado na ação (apenas criações)."""
        action_mapping = {
            "create_finance": ("finances", "finance"),
            "create_reminder": ("reminders", "reminder"),
            "create_meeting": ("meetings", "meeting"),
            "create_contact": ("contacts", "contact"),
            "schedule_message": ("scheduled_messages", "scheduled_message"),
        }

        if action in action_mapping:
            list_key, item_key = action_mapping[action]
            if result_data.get(item_key):
                aggregated[list_key].append(result_data[item_key])

    def _save_to_database(
        self, db: Any, user_id: int, aggregated: Dict[str, List]
    ) -> None:
        """Salva dados agregados no banco de dados."""
        logger.info(f"[SAVE] 🔗 DB e user_id disponíveis: user_id={user_id}")

        # Salvar finanças
        if aggregated["finances"]:
            self._save_finances(db, user_id, aggregated["finances"])

        # Salvar lembretes
        if aggregated["reminders"]:
            self._save_reminders(db, user_id, aggregated["reminders"])

        # Salvar reuniões
        if aggregated["meetings"]:
            self._save_meetings(db, user_id, aggregated["meetings"])

        # Salvar contatos
        if aggregated["contacts"]:
            self._save_contacts(db, user_id, aggregated["contacts"])

        # Salvar mensagens agendadas
        if aggregated["scheduled_messages"]:
            self._save_scheduled_messages(db, user_id, aggregated["scheduled_messages"])

        # Log do resumo
        logger.info(
            f"[FORMATTER] 📊 Agregados - "
            f"Finances: {len(aggregated['finances'])}, "
            f"Reminders: {len(aggregated['reminders'])}, "
            f"Meetings: {len(aggregated['meetings'])}, "
            f"Contacts: {len(aggregated['contacts'])}"
        )

    def _save_finances(self, db: Any, user_id: int, finances: List[Dict]) -> None:
        """Salva transações financeiras."""
        from app.services.finance_service import FinanceService
        finance_service = FinanceService(db)
        for finance in finances:
            try:
                logger.info(f"[SAVE] 💰 Salvando: {finance}")
                finance_service.create_from_entities(user_id, finance)
                logger.info(f"[SAVE] ✅ Finança salva: {finance.get('description')}")
            except Exception as e:
                logger.error(f"[SAVE] ❌ Erro ao salvar finança: {e}")

    def _save_reminders(self, db: Any, user_id: int, reminders: List[Dict]) -> None:
        """Salva lembretes."""
        from app.services.reminder_service import ReminderService
        reminder_service = ReminderService(db)
        for reminder in reminders:
            try:
                reminder_service.create_from_entities(user_id, reminder)
                logger.info(f"[SAVE] ⏰ Lembrete: {reminder.get('title')}")
            except Exception as e:
                logger.error(f"Erro ao salvar lembrete: {e}")

    def _save_meetings(self, db: Any, user_id: int, meetings: List[Dict]) -> None:
        """Salva reuniões."""
        from app.services.meeting_service import MeetingService
        meeting_service = MeetingService(db)
        for meeting in meetings:
            try:
                meeting_service.create_from_entities(user_id, meeting)
                logger.info(f"[SAVE] 📅 Reunião: {meeting.get('title')}")
            except Exception as e:
                logger.error(f"Erro ao salvar reunião: {e}")

    def _save_contacts(self, db: Any, user_id: int, contacts: List[Dict]) -> None:
        """Salva contatos."""
        from app.services.contact_service import ContactService
        contact_service = ContactService(db)
        for contact in contacts:
            try:
                contact_service.create_from_dict(user_id, contact)
                logger.info(f"[SAVE] 👤 Contato: {contact.get('name')}")
            except Exception as e:
                logger.error(f"Erro ao salvar contato: {e}")

    def _save_scheduled_messages(
        self, db: Any, user_id: int, messages: List[Dict]
    ) -> None:
        """Salva mensagens agendadas."""
        from app.services.scheduled_message_service import ScheduledMessageService
        scheduled_service = ScheduledMessageService(db)
        for msg in messages:
            try:
                scheduled_service.create_from_entities(user_id, msg)
                logger.info(
                    f"[SAVE] 📨 Agendamento: "
                    f"{msg.get('recipient_name') or msg.get('group_name')}"
                )
            except Exception as e:
                logger.error(f"Erro ao agendar mensagem: {e}")

    def _get_state_actions(self, aggregated: Dict[str, Any]) -> tuple:
        """
        Extrai ações dos resultados agregados.
        Retorna (next_action, entities) sem mutar estado.
        """
        next_action = ""
        entities = {}
        
        # Processar resultados de queries (prioridade)
        query_results = aggregated.get("query_results", [])
        if query_results:
            query = query_results[0]
            next_action = query.get("action", "")
            entities = query.get("data", {})
            entities["query_success"] = query.get("success", False)
            logger.info(f"[STATE] Ação definida: {next_action} | Success: {entities.get('query_success')}")
            return next_action, entities
        
        # Processar ações de criação
        action_configs = [
            ("finances", "finance", "create_finance", "create_finances"),
            ("reminders", "reminder", "create_reminder", "create_reminders"),
            ("meetings", "meeting", "create_meeting", "create_meetings"),
            ("contacts", "contact", "create_contact", "create_contacts"),
            ("scheduled_messages", "scheduled_message", "schedule_message", "schedule_messages"),
        ]

        for list_key, item_key, single_action, plural_action in action_configs:
            items = aggregated.get(list_key, [])
            if len(items) > 1:
                next_action = plural_action
                entities = {list_key: items}
            elif len(items) == 1:
                next_action = single_action
                entities = {item_key: items[0]}

        return next_action, entities

    def _handle_integration_responses(
        self, state: IRISState, integration_responses: List[str]
    ) -> dict:
        """Processa respostas de tools de integração. Retorna dict imutável."""
        integration_context = "\n\n".join(integration_responses)

        integration_prompt = f"""Você é IRIS, assistente pessoal.

DADOS OBTIDOS DAS FERRAMENTAS:
{integration_context}

PERGUNTA DO USUÁRIO:
{state["messages"][-1].content if state["messages"] else ""}

Responda de forma natural e amigável, usando os dados acima. Seja conciso."""

        response = self.llm.invoke(integration_prompt)
        return {"messages": [AIMessage(content=response.content)]}

    def _generate_tool_response(self, state: IRISState, user_name: str, next_action: str = "", entities: dict = None) -> dict:
        """Gera resposta humanizada baseada nos resultados das tools. Retorna dict imutável."""
        response_prompt = ResponsePrompts.get_response_generation_prompt(
            user_name=user_name,
            comm_style="",
            context_prompt=state.get("context_prompt", ""),
            next_action=next_action or state.get("next_action", ""),
            entities=entities or state.get("entities", {}),
            last_message=state["messages"][-1].content if state["messages"] else "",
            rag_context=state.get("rag_context", ""),
        )

        response = self.llm.invoke(response_prompt)
        return {
            "messages": [AIMessage(content=response.content)],
            "next_action": next_action,
            "entities": entities or {},
        }

    def _generate_general_response(self, state: IRISState, user_name: str) -> dict:
        """Gera resposta para chat geral. Retorna dict imutável."""
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
        return {"messages": [AIMessage(content=response.content)]}
