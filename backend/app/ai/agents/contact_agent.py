"""
Agente especializado em gerenciamento de contatos e envio de mensagens.
Utiliza prompts centralizados para fácil manutenção.
"""
import logging
import json
import re
from typing import Dict, Any, Optional, List
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.ai.agents.prompts.contact_prompts import ContactPrompts
from app.services.contact_service import ContactService, ContactGroupService, normalize_group_name
from app.services.message_broadcast_service import MessageBroadcastService
from app.services.whatsapp_service import WhatsAppService
from app.models import ScheduledMessage, ScheduledMessageStatus, Contact
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)


class ContactAgent:
    """Agente especializado em gerenciamento de contatos e envio de mensagens para grupos."""

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.2,
        )
        self.whatsapp_service = WhatsAppService(
            account_sid=settings.TWILIO_ACCOUNT_SID,
            auth_token=settings.TWILIO_AUTH_TOKEN,
            whatsapp_number=settings.TWILIO_WHATSAPP_NUMBER
        )

    def process(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa mensagem relacionada a contatos."""
        try:
            db = context.get("db")
            user_id = context.get("user_id")
            
            # Verificar se há contato pendente esperando informação
            pending = context.get("pending_contact") or context.get("memory", {}).get("pending_contact")
            
            if pending:
                return self._complete_pending_contact(message, pending, context)
            
            # Verificar se há broadcast pendente esperando confirmação
            pending_broadcast = context.get("pending_broadcast")
            if pending_broadcast:
                return self._handle_broadcast_confirmation(message, pending_broadcast, context)
            
            # Classificar a intenção específica de contatos
            intent_result = self._classify_contact_intent(message, context)
            intent = intent_result.get("intent", "create_contact")
            
            if intent == "schedule_message":
                return self._handle_schedule_message(message, intent_result, context)
            elif intent == "send_broadcast":
                return self._handle_broadcast_request(message, intent_result, context)
            elif intent == "list_groups":
                return self._handle_list_groups(context)
            elif intent == "list_contacts":
                return self._handle_list_contacts(intent_result, context)
            else:
                # Criar contato
                return self._extract_contact_info(message, context)
                
        except Exception as e:
            logger.error(f"Erro no ContactAgent: {e}")
            return self._error_response()

    def _get_conversation_history(self, context: Dict[str, Any]) -> str:
        """Extrai histórico de conversa do contexto."""
        memory = context.get("memory", {})
        conversation = memory.get("conversation", [])
        
        if not conversation:
            return ""
        
        lines = []
        for msg in conversation[-6:]:
            role = "Usuário" if msg.get("role") == "user" else "Assistente"
            content = msg.get("content", "")[:200]
            lines.append(f"{role}: {content}")
        
        return "\n".join(lines)

    def _classify_contact_intent(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Classifica a intenção específica relacionada a contatos."""
        history = self._get_conversation_history(context)
        
        prompt = ContactPrompts.get_intent_classification_prompt(history, message)
        response = self.llm.invoke(prompt)
        return self._parse_json(response.content)

    def _handle_schedule_message(self, message: str, intent_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa solicitação de agendamento de mensagem para contato."""
        db = context.get("db")
        user_id = context.get("user_id")
        
        contact_name = intent_result.get("contact_name")
        message_to_send = intent_result.get("message_to_send")
        scheduled_time_str = intent_result.get("scheduled_time")
        group_names = intent_result.get("group_names", [])
        
        if not db or not user_id:
            return self._error_response()
        
        # Se não tem contato nem grupo, perguntar
        if not contact_name and not group_names:
            return {
                "response": "Para quem você quer enviar a mensagem agendada?\n\nExemplo: _Manda mensagem pra Maruza às 14h: Reunião confirmada_",
                "intent": "contact",
                "entities": {},
                "next_action": "none",
            }
        
        # Buscar contato pelo nome
        contact_service = ContactService(db)
        contact = None
        
        if contact_name:
            contacts = contact_service.search_by_name(user_id, contact_name)
            if not contacts:
                return {
                    "response": f"❌ Não encontrei o contato *{contact_name}*.\n\nVocê pode adicionar com:\n_Salva {contact_name} 11999998888 como amigo_",
                    "intent": "contact",
                    "entities": {},
                    "next_action": "none",
                }
            contact = contacts[0]  # Usar primeiro match
        
        # Se não tem mensagem, perguntar
        if not message_to_send:
            recipient = contact.name if contact else ", ".join(group_names)
            return {
                "response": f"Qual mensagem você quer enviar para *{recipient}*?",
                "intent": "contact",
                "entities": {"pending_schedule": {
                    "contact_id": contact.id if contact else None,
                    "contact_name": contact.name if contact else None,
                    "group_names": group_names,
                    "scheduled_time": scheduled_time_str
                }},
                "next_action": "await_schedule_message",
            }
        
        # Se não tem horário, perguntar
        if not scheduled_time_str:
            recipient = contact.name if contact else ", ".join(group_names)
            return {
                "response": f"A que horas você quer que eu envie a mensagem para *{recipient}*?",
                "intent": "contact",
                "entities": {"pending_schedule": {
                    "contact_id": contact.id if contact else None,
                    "contact_name": contact.name if contact else None,
                    "group_names": group_names,
                    "message": message_to_send
                }},
                "next_action": "await_schedule_time",
            }
        
        # Converter horário para datetime
        scheduled_dt = self._parse_scheduled_time(scheduled_time_str, context)
        if not scheduled_dt:
            return {
                "response": "Não consegui entender o horário. Por favor, informe como:\n_às 14h_, _amanhã às 9h30_, _15:00_",
                "intent": "contact",
                "entities": {},
                "next_action": "none",
            }
        
        # Criar mensagem agendada
        try:
            scheduled_msg = ScheduledMessage(
                user_id=user_id,
                contact_id=contact.id if contact else None,
                recipient_name=contact.name if contact else None,
                recipient_phone=contact.phone_number if contact else None,
                group_name=normalize_group_name(group_names[0]) if group_names else None,
                message=message_to_send,
                scheduled_time=scheduled_dt,
                status=ScheduledMessageStatus.PENDING
            )
            db.add(scheduled_msg)
            db.commit()
            db.refresh(scheduled_msg)
            
            # Formatar resposta
            user_tz = pytz.timezone("America/Sao_Paulo")
            local_time = scheduled_dt.replace(tzinfo=pytz.utc).astimezone(user_tz)
            time_str = local_time.strftime("%H:%M")
            date_str = local_time.strftime("%d/%m")
            
            recipient = contact.name if contact else f"grupo {group_names[0]}"
            
            return {
                "response": f"✅ *Mensagem agendada!*\n\n👤 Para: {recipient}\n⏰ Horário: {time_str} ({date_str})\n💬 Mensagem: _{message_to_send}_",
                "intent": "contact",
                "entities": {"scheduled_message_id": scheduled_msg.id},
                "next_action": "message_scheduled",
            }
        
        except Exception as e:
            logger.error(f"Erro ao agendar mensagem: {e}")
            return {
                "response": "❌ Erro ao agendar a mensagem. Por favor, tente novamente.",
                "intent": "contact",
                "entities": {},
                "next_action": "none",
            }

    def _parse_scheduled_time(self, time_str: str, context: Dict[str, Any]) -> Optional[datetime]:
        """Converte string de horário para datetime UTC."""
        try:
            user_tz = pytz.timezone("America/Sao_Paulo")
            now = datetime.now(user_tz)
            
            # Limpar string
            time_str = time_str.lower().strip()
            
            # Padrões comuns
            import re
            
            # "14:00", "14h", "14h30", "14:30"
            time_match = re.search(r'(\d{1,2})[h:]?(\d{2})?', time_str)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                
                # Determinar a data
                if "amanhã" in time_str or "amanha" in time_str:
                    target_date = now.date() + timedelta(days=1)
                elif "depois de amanhã" in time_str:
                    target_date = now.date() + timedelta(days=2)
                else:
                    target_date = now.date()
                    # Se o horário já passou, agendar para amanhã
                    if hour < now.hour or (hour == now.hour and minute <= now.minute):
                        target_date = now.date() + timedelta(days=1)
                
                # Criar datetime local
                local_dt = user_tz.localize(datetime(
                    target_date.year, target_date.month, target_date.day, hour, minute
                ))
                
                # Converter para UTC
                return local_dt.astimezone(pytz.utc).replace(tzinfo=None)
            
            return None
        
        except Exception as e:
            logger.error(f"Erro ao parsear horário '{time_str}': {e}")
            return None

    def _handle_broadcast_request(self, message: str, intent_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa solicitação de envio de mensagem para grupo(s)."""
        db = context.get("db")
        user_id = context.get("user_id")
        
        group_names = intent_result.get("group_names", [])
        message_to_send = intent_result.get("message_to_send")
        
        if not group_names:
            return {
                "response": "Para qual grupo você quer enviar a mensagem?\n\nExemplo: _Manda para os funcionários: Reunião amanhã às 9h_",
                "intent": "contact",
                "entities": {},
                "next_action": "none",
            }
        
        if not message_to_send:
            groups_str = ", ".join(group_names)
            return {
                "response": f"Qual mensagem você quer enviar para *{groups_str}*?",
                "intent": "contact",
                "entities": {"pending_broadcast": {"group_names": group_names}},
                "next_action": "await_broadcast_message",
            }
        
        # Tem grupo e mensagem - enviar broadcast
        if db and user_id:
            return self._execute_broadcast(user_id, group_names, message_to_send, db)
        
        return {
            "response": "❌ Erro: não foi possível acessar o banco de dados.",
            "intent": "contact",
            "entities": {},
            "next_action": "none",
        }

    def _execute_broadcast(self, user_id: int, group_names: List[str], message: str, db) -> Dict[str, Any]:
        """Executa o envio de broadcast para os grupos."""
        broadcast_service = MessageBroadcastService(db, self.whatsapp_service)
        
        # Normalizar nomes dos grupos
        normalized_groups = [normalize_group_name(g) for g in group_names]
        
        # Verificar se existem contatos nos grupos
        contact_service = ContactService(db)
        total_contacts = 0
        for group in normalized_groups:
            contacts = contact_service.get_by_group(user_id, group)
            total_contacts += len(contacts)
        
        if total_contacts == 0:
            groups_str = ", ".join(group_names)
            return {
                "response": f"⚠️ Nenhum contato encontrado no(s) grupo(s): *{groups_str}*\n\nVocê pode adicionar contatos dizendo:\n_Salva João 11999998888 como funcionário_",
                "intent": "contact",
                "entities": {},
                "next_action": "none",
            }
        
        # Executar broadcast
        result = broadcast_service.send_broadcast(
            user_id=user_id,
            message=message,
            group_names=normalized_groups
        )
        
        # Formatar resposta
        response_text = broadcast_service.format_broadcast_summary(result, group_names)
        
        return {
            "response": response_text,
            "intent": "contact",
            "entities": {"broadcast_result": result},
            "next_action": "broadcast_sent",
        }

    def _handle_broadcast_confirmation(self, message: str, pending: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa confirmação/mensagem para broadcast pendente."""
        db = context.get("db")
        user_id = context.get("user_id")
        group_names = pending.get("group_names", [])
        
        # A mensagem atual é o conteúdo do broadcast
        if db and user_id:
            return self._execute_broadcast(user_id, group_names, message.strip(), db)
        
        return self._error_response()

    def _handle_list_groups(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Lista todos os grupos de contatos do usuário."""
        db = context.get("db")
        user_id = context.get("user_id")
        
        if not db or not user_id:
            return self._error_response()
        
        contact_service = ContactService(db)
        groups_summary = contact_service.get_groups_summary(user_id)
        
        if not groups_summary:
            return {
                "response": "📋 Você ainda não tem grupos de contatos.\n\nPara criar, adicione um contato:\n_Salva João 11999998888 como funcionário_",
                "intent": "contact",
                "entities": {},
                "next_action": "none",
            }
        
        msg = "📋 *Seus grupos de contatos:*\n\n"
        for g in groups_summary:
            msg += f"👥 *{g['group_name'].title()}* - {g['count']} contato(s)\n"
        
        msg += "\n_Para ver contatos de um grupo:_ listar funcionários"
        msg += "\n_Para enviar mensagem:_ manda pros funcionários: sua mensagem"
        
        return {
            "response": msg,
            "intent": "contact",
            "entities": {"groups": groups_summary},
            "next_action": "list_groups",
        }

    def _handle_list_contacts(self, intent_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Lista contatos de um grupo específico."""
        db = context.get("db")
        user_id = context.get("user_id")
        group_names = intent_result.get("group_names", [])
        
        if not db or not user_id:
            return self._error_response()
        
        contact_service = ContactService(db)
        
        if group_names:
            # Listar contatos de grupos específicos
            group_name = normalize_group_name(group_names[0])
            contacts = contact_service.get_by_group(user_id, group_name)
            
            if not contacts:
                return {
                    "response": f"📋 Nenhum contato encontrado no grupo *{group_names[0]}*.",
                    "intent": "contact",
                    "entities": {},
                    "next_action": "none",
                }
            
            msg = f"📋 *Contatos em {group_names[0].title()}:*\n\n"
            for c in contacts[:15]:  # Limitar a 15
                msg += f"👤 *{c.name}* - {c.phone_number}\n"
            
            if len(contacts) > 15:
                msg += f"\n_...e mais {len(contacts) - 15} contatos_"
        else:
            # Listar todos os contatos
            result = contact_service.list(user_id, limit=15)
            contacts = result["items"]
            
            if not contacts:
                return {
                    "response": "📋 Você ainda não tem contatos salvos.\n\nPara adicionar:\n_Salva João 11999998888 como funcionário_",
                    "intent": "contact",
                    "entities": {},
                    "next_action": "none",
                }
            
            msg = f"📋 *Seus contatos:* ({result['total']} total)\n\n"
            for c in contacts:
                msg += f"👤 *{c.name}* ({c.group_name}) - {c.phone_number}\n"
            
            if result["total"] > 15:
                msg += f"\n_...e mais {result['total'] - 15} contatos_"
        
        return {
            "response": msg,
            "intent": "contact",
            "entities": {},
            "next_action": "list_contacts",
        }

    def _extract_contact_info(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai informações de contato(s) da mensagem."""
        history = self._get_conversation_history(context)
        db = context.get("db")
        user_id = context.get("user_id")
        
        prompt = ContactPrompts.get_contact_extraction_prompt(history, message)

        response = self.llm.invoke(prompt)
        extracted = self._parse_json(response.content)
        
        contacts = extracted.get("contacts", [])
        global_group = extracted.get("group_name_global")
        
        # Aplicar grupo global se existir
        if global_group:
            for contact in contacts:
                if not contact.get("group_name"):
                    contact["group_name"] = global_group
        
        # Se extraiu múltiplos contatos completos
        if len(contacts) > 1:
            valid_contacts = [c for c in contacts if c.get("name") and c.get("phone_number")]
            if valid_contacts:
                return self._create_multiple_contacts_response(valid_contacts, db, user_id)
        
        # Se extraiu apenas um contato
        if len(contacts) == 1:
            contact = contacts[0]
            name = contact.get("name")
            phone = contact.get("phone_number")
            group_name = contact.get("group_name") or global_group
            
            if name and phone:
                contact_data = {"name": name, "phone_number": phone, "group_name": group_name or "outros"}
                return self._create_contact_response(contact_data, db, user_id)
            
            if phone and not name:
                return {
                    "response": f"📱 Número anotado: *{phone}*\n\nQual é o nome desse contato?",
                    "intent": "contact",
                    "entities": {"pending_contact": {"phone_number": phone, "group_name": group_name}},
                    "next_action": "await_contact_name",
                }
            
            if name and not phone:
                return {
                    "response": f"👤 Nome anotado: *{name}*\n\nQual é o número de telefone?",
                    "intent": "contact",
                    "entities": {"pending_contact": {"name": name, "group_name": group_name}},
                    "next_action": "await_contact_phone",
                }
        
        # Não conseguiu extrair nada útil
        return {
            "response": "Para salvar um contato, preciso do *nome* e *número de telefone*.\n\nExemplo: _Salva o contato João 11999998888 como funcionário_",
            "intent": "contact",
            "entities": {},
            "next_action": "none",
        }

    def _create_multiple_contacts_response(self, contacts: List[Dict[str, Any]], db=None, user_id: int = None) -> Dict[str, Any]:
        """Cria resposta de confirmação para múltiplos contatos e salva no banco."""
        saved_contacts = []
        
        for contact in contacts:
            group_name = contact.get("group_name", "outros")
            contact["group_name"] = group_name
            
            if db and user_id:
                try:
                    contact_service = ContactService(db)
                    contact_service.create_from_dict(user_id, contact)
                    saved_contacts.append(contact)
                    logger.info(f"Contato {contact['name']} salvo no banco")
                except Exception as e:
                    logger.error(f"Erro ao salvar contato {contact['name']}: {e}")
        
        if not saved_contacts:
            return {
                "response": "❌ Erro ao salvar os contatos. Por favor, tente novamente.",
                "intent": "contact",
                "entities": {},
                "next_action": "none",
            }
        
        # Formatar resposta
        group_label = saved_contacts[0].get("group_name", "outros").replace("_", " ").title()
        contacts_list = "\n".join([f"👤 *{c['name']}* - {c['phone_number']}" for c in saved_contacts])
        
        return {
            "response": f"✅ *{len(saved_contacts)} contatos salvos!*\n\n{contacts_list}\n\n👥 Grupo: {group_label}",
            "intent": "contact",
            "entities": {"contacts": saved_contacts},
            "next_action": "create_contact",
        }

    def _complete_pending_contact(self, message: str, pending: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Completa um contato pendente com informação faltante."""
        db = context.get("db")
        user_id = context.get("user_id")
        
        name = pending.get("name")
        phone = pending.get("phone_number")
        group_name = pending.get("group_name") or pending.get("group")
        
        # Se falta nome, a mensagem atual é o nome
        if not name:
            name = message.strip()
            if phone:
                contact = {"name": name, "phone_number": phone, "group_name": group_name or "outros"}
                return self._create_contact_response(contact, db, user_id)
        
        # Se falta telefone, extrair da mensagem
        if not phone:
            phone_match = re.search(r'[\d\s\-\(\)]{8,}', message)
            if phone_match:
                phone = re.sub(r'[^\d]', '', phone_match.group())
                contact = {"name": name, "phone_number": phone, "group_name": group_name or "outros"}
                return self._create_contact_response(contact, db, user_id)
            else:
                return {
                    "response": "Não consegui identificar o número. Por favor, digite apenas o telefone:",
                    "intent": "contact",
                    "entities": {"pending_contact": pending},
                    "next_action": "await_contact_phone",
                }
        
        # Já tem tudo
        contact = {"name": name, "phone_number": phone, "group_name": group_name or "outros"}
        return self._create_contact_response(contact, db, user_id)

    def _create_contact_response(self, contact: Dict[str, Any], db=None, user_id: int = None) -> Dict[str, Any]:
        """Cria resposta de confirmação de contato e salva no banco."""
        group_name = contact.get("group_name", "outros")
        group_label = group_name.replace("_", " ").title()
        
        # Salvar no banco se tiver acesso
        if db and user_id:
            try:
                contact_service = ContactService(db)
                contact_service.create_from_dict(user_id, contact)
                logger.info(f"Contato {contact['name']} salvo no banco")
            except Exception as e:
                logger.error(f"Erro ao salvar contato: {e}")
        
        return {
            "response": f"✅ *Contato salvo!*\n\n👤 {contact['name']}\n📱 {contact['phone_number']}\n👥 {group_label}",
            "intent": "contact",
            "entities": {"contacts": [contact]},
            "next_action": "create_contact",
        }

    def _parse_json(self, content: str) -> Dict[str, Any]:
        """Extrai JSON da resposta."""
        try:
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass
        return {}

    def _error_response(self) -> Dict[str, Any]:
        """Retorna resposta de erro."""
        return {
            "response": "Desculpe, não consegui processar. Pode repetir o nome e telefone do contato?",
            "intent": "contact",
            "entities": {},
            "next_action": "none",
        }
