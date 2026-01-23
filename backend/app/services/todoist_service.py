"""
Todoist Monitor Service - Serviço de monitoramento de tarefas do Todoist.

Este serviço:
- Conecta à API do Todoist usando o token
- Faz polling a cada X minutos para buscar tarefas
- Alerta quando tarefas estão próximas do prazo (zona de alerta)
- Integra com a IA para gerar mensagens motivacionais
- Implementa idempotência para evitar spam de notificações
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Set
from zoneinfo import ZoneInfo

from todoist_api_python.api import TodoistAPI

from app.config import settings

logger = logging.getLogger(__name__)


class TodoistMonitorService:
    """
    Serviço de monitoramento de tarefas do Todoist.
    
    Funcionalidades:
    - Busca inteligente com polling configurável
    - Zona de alerta para tarefas próximas do prazo
    - Idempotência para evitar notificações duplicadas
    - Integração com LLM para mensagens motivacionais
    """

    def __init__(
        self,
        token: str = None,
        timezone: str = None,
        alert_minutes: int = None,
        polling_seconds: int = None,
    ):
        self.token = token or settings.TODOIST_API_KEY
        self.timezone = ZoneInfo(timezone or settings.DEFAULT_TIMEZONE)
        self.alert_minutes = alert_minutes or settings.TODOIST_ALERT_MINUTES
        self.polling_seconds = polling_seconds or settings.TODOIST_POLLING_SECONDS
        
        self._api: Optional[TodoistAPI] = None
        self._notified_task_ids: Set[str] = set()
        self._last_cleanup: datetime = datetime.now(self.timezone)
        self._is_running: bool = False
        self._pending_alerts: list = []

    @property
    def api(self) -> Optional[TodoistAPI]:
        """Retorna instância da API do Todoist (lazy loading)."""
        if not self._api and self.token:
            try:
                self._api = TodoistAPI(self.token)
                logger.info("✅ TodoistAPI inicializada com sucesso")
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar TodoistAPI: {e}")
        return self._api

    @property
    def is_configured(self) -> bool:
        """Verifica se o serviço está configurado corretamente."""
        return bool(self.token)

    def _cleanup_notified_ids(self) -> None:
        """Limpa o set de IDs notificados a cada 24h."""
        now = datetime.now(self.timezone)
        if (now - self._last_cleanup).total_seconds() >= 86400:  # 24h
            self._notified_task_ids.clear()
            self._last_cleanup = now
            logger.info("🧹 Set de notificações limpo (24h)")

    def _parse_due_datetime(self, due: dict) -> Optional[datetime]:
        """
        Converte o campo due do Todoist para datetime com timezone.
        
        Args:
            due: Dicionário com informações de prazo da tarefa
            
        Returns:
            datetime com timezone ou None se não houver prazo
        """
        if not due:
            return None

        due_datetime = due.get("datetime")
        due_date = due.get("date")
        
        if due_datetime:
            # Formato: 2024-01-23T10:00:00
            try:
                dt = datetime.fromisoformat(due_datetime.replace("Z", "+00:00"))
                return dt.astimezone(self.timezone)
            except ValueError:
                pass
        
        if due_date:
            # Formato: 2024-01-23 (apenas data, considerar fim do dia)
            try:
                dt = datetime.strptime(due_date, "%Y-%m-%d")
                dt = dt.replace(hour=23, minute=59, second=59, tzinfo=self.timezone)
                return dt
            except ValueError:
                pass
        
        return None

    def _is_in_alert_zone(self, due_datetime: datetime) -> tuple[bool, int]:
        """
        Verifica se a tarefa está na zona de alerta.
        
        Args:
            due_datetime: Data/hora do prazo
            
        Returns:
            Tupla (está_na_zona, minutos_restantes)
        """
        now = datetime.now(self.timezone)
        delta = due_datetime - now
        minutes_remaining = int(delta.total_seconds() / 60)
        
        # Regra: Se 0 < delta <= alert_minutes, disparar alerta
        is_in_zone = 0 < minutes_remaining <= self.alert_minutes
        
        return is_in_zone, minutes_remaining

    async def _generate_motivational_message(
        self,
        task_title: str,
        minutes_remaining: int,
        user_name: str = None,
    ) -> str:
        """
        Gera mensagem motivacional usando a IA (Gemini).
        
        Args:
            task_title: Título da tarefa
            minutes_remaining: Minutos restantes até o prazo
            user_name: Nome do usuário (opcional)
            
        Returns:
            Mensagem motivacional personalizada
        """
        name = user_name or "Usuário"
        
        if minutes_remaining <= 15:
            urgency = "⚠️ URGENTE"
        elif minutes_remaining <= 30:
            urgency = "⏰ Atenção"
        else:
            urgency = "📋 Lembrete"

        # Tentar usar LLM para mensagem personalizada
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.8,
                max_output_tokens=150,
            )
            
            prompt = f"""Gere uma mensagem curta e motivacional (máx 2 linhas) para lembrar {name} 
da tarefa "{task_title}" que vence em {minutes_remaining} minutos.
Seja direto, use emojis e incentive a ação imediata.
Responda APENAS com a mensagem, sem explicações."""

            response = await llm.ainvoke(prompt)
            return f"{urgency} | {response.content.strip()}"
            
        except Exception as e:
            logger.warning(f"Erro ao gerar mensagem com IA: {e}")
            # Fallback para mensagem padrão
            return (
                f"{urgency} | {name}, faltam {minutes_remaining} min para "
                f"'{task_title}'. Vamos lá! 💪"
            )

    async def check_deadlines(self, user_name: str = None) -> list[dict]:
        """
        Verifica tarefas próximas do prazo.
        
        Args:
            user_name: Nome do usuário para personalizar mensagens
            
        Returns:
            Lista de alertas gerados
        """
        if not self.api:
            logger.warning("⚠️ TodoistAPI não configurada")
            return []

        self._cleanup_notified_ids()
        alerts = []

        try:
            # Buscar tarefas com filtro: vence hoje e ainda não expirou
            tasks = self.api.get_tasks(filter="today & !overdue")
            
            for task in tasks:
                # Verificar idempotência
                if task.id in self._notified_task_ids:
                    continue

                # Converter prazo para datetime
                due_datetime = self._parse_due_datetime(task.due.__dict__ if task.due else None)
                if not due_datetime:
                    continue

                # Verificar se está na zona de alerta
                is_in_zone, minutes_remaining = self._is_in_alert_zone(due_datetime)
                
                if is_in_zone:
                    # Gerar mensagem motivacional
                    message = await self._generate_motivational_message(
                        task_title=task.content,
                        minutes_remaining=minutes_remaining,
                        user_name=user_name,
                    )
                    
                    alert = {
                        "task_id": task.id,
                        "task_title": task.content,
                        "due_datetime": due_datetime.isoformat(),
                        "minutes_remaining": minutes_remaining,
                        "message": message,
                        "priority": task.priority,
                        "project_id": task.project_id,
                    }
                    
                    alerts.append(alert)
                    self._notified_task_ids.add(task.id)
                    
                    logger.info(
                        f"🔔 Alerta gerado: {task.content} "
                        f"(faltam {minutes_remaining} min)"
                    )

        except Exception as e:
            logger.error(f"❌ Erro ao verificar deadlines: {e}")

        return alerts

    async def start_monitoring(
        self,
        user_name: str = None,
        callback: callable = None,
    ) -> None:
        """
        Inicia o loop de monitoramento de tarefas.
        
        Args:
            user_name: Nome do usuário para personalizar mensagens
            callback: Função a ser chamada quando um alerta é gerado
        """
        if not self.is_configured:
            logger.error("❌ Todoist não configurado. Defina TODOIST_API_KEY.")
            return

        self._is_running = True
        logger.info(
            f"🚀 Iniciando monitoramento Todoist "
            f"(polling: {self.polling_seconds}s, alerta: {self.alert_minutes}min)"
        )

        while self._is_running:
            try:
                alerts = await self.check_deadlines(user_name)
                
                if alerts and callback:
                    for alert in alerts:
                        await callback(alert)
                
                self._pending_alerts.extend(alerts)
                
            except Exception as e:
                logger.error(f"❌ Erro no loop de monitoramento: {e}")
            
            await asyncio.sleep(self.polling_seconds)

    def stop_monitoring(self) -> None:
        """Para o loop de monitoramento."""
        self._is_running = False
        logger.info("⏹️ Monitoramento Todoist parado")

    def get_pending_alerts(self) -> list[dict]:
        """Retorna e limpa alertas pendentes."""
        alerts = self._pending_alerts.copy()
        self._pending_alerts.clear()
        return alerts

    # ==================== Métodos de CRUD ====================

    async def get_tasks(
        self,
        filter_str: str = None,
        project_id: str = None,
        include_welcome: bool = False,
    ) -> list[dict]:
        """
        Busca tarefas do Todoist.
        
        Args:
            filter_str: Filtro do Todoist (ex: "today", "overdue", "p1")
            project_id: ID do projeto para filtrar
            include_welcome: Incluir tarefas de boas-vindas
            
        Returns:
            Lista de tarefas
        """
        if not self.api:
            return []

        try:
            if filter_str:
                tasks = self.api.get_tasks(filter=filter_str)
            elif project_id:
                tasks = self.api.get_tasks(project_id=project_id)
            else:
                tasks = self.api.get_tasks()

            # Filtrar tarefas de boas-vindas do Todoist (se solicitado)
            if include_welcome:
                # Retorna todas as tarefas sem filtro
                return [
                    {
                        "id": task.id,
                        "content": task.content,
                        "description": task.description,
                        "due": task.due.__dict__ if task.due else None,
                        "priority": task.priority,
                        "project_id": task.project_id,
                        "labels": task.labels,
                        "is_completed": task.is_completed,
                        "created_at": task.created_at,
                        "url": task.url,
                    }
                    for task in tasks
                ]
            else:
                # Filtra tarefas de boas-vindas do Todoist
                # Detecta tarefas de onboarding por padrões específicos
                def is_onboarding_task(task_content: str) -> bool:
                    content = task_content.lower()
                    
                    # Padrão 1: Contém links markdown com URLs do Todoist/YouTube
                    # Ex: ([Assista](https://youtu.be/...))
                    if "](http" in content and ("todoist" in content or "youtu" in content):
                        return True
                    
                    # Padrão 2: Contém formato de link markdown com ações
                    if any(action in content for action in [
                        "[assista]", "[leia]", "[download]", "[obtenha", "[assinar]",
                        "(assista)", "(leia)", "(download)",
                    ]):
                        return True
                    
                    # Padrão 3: Frases específicas de onboarding (PT-BR)
                    onboarding_pt = [
                        "visualização de tarefas",
                        "captar:",
                        "esclarecer:",
                        "concluir:",
                        "descobrir os layouts",
                        "transformar qualquer e-mail",
                        "receba inspirações",
                        "separe 5 minutos todos os dias",
                        "conectar seu calendário para ver",
                        "risque as tarefas da lista",
                        "desktop: **",
                        "atalhos do teclado",
                        "entrada e hoje",
                        "em breve",
                    ]
                    if any(phrase in content for phrase in onboarding_pt):
                        return True
                    
                    # Padrão 4: Frases específicas de onboarding (EN)
                    onboarding_en = [
                        "getting started",
                        "capture:",
                        "clarify:",
                        "complete:",
                        "discover layouts",
                        "forward emails",
                        "keyboard shortcuts",
                        "monthly inspiration",
                        "check off tasks",
                    ]
                    return any(phrase in content for phrase in onboarding_en)
                
                filtered_tasks = []
                for task in tasks:
                    # Incluir apenas se não for tarefa de onboarding
                    if not is_onboarding_task(task.content):
                        filtered_tasks.append({
                            "id": task.id,
                            "content": task.content,
                            "description": task.description,
                            "due": task.due.__dict__ if task.due else None,
                            "priority": task.priority,
                            "project_id": task.project_id,
                            "labels": task.labels,
                            "is_completed": task.is_completed,
                            "created_at": task.created_at,
                            "url": task.url,
                        })
                
                return filtered_tasks
        except Exception as e:
            logger.error(f"❌ Erro ao buscar tarefas: {e}")
            return []

    async def get_task(self, task_id: str) -> Optional[dict]:
        """Busca uma tarefa específica pelo ID."""
        if not self.api:
            return None

        try:
            task = self.api.get_task(task_id)
            return {
                "id": task.id,
                "content": task.content,
                "description": task.description,
                "due": task.due.__dict__ if task.due else None,
                "priority": task.priority,
                "project_id": task.project_id,
                "labels": task.labels,
                "is_completed": task.is_completed,
                "created_at": task.created_at,
                "url": task.url,
            }
        except Exception as e:
            logger.error(f"❌ Erro ao buscar tarefa {task_id}: {e}")
            return None

    async def create_task(
        self,
        content: str,
        description: str = None,
        due_string: str = None,
        due_datetime: str = None,
        priority: int = 1,
        project_id: str = None,
        labels: list[str] = None,
    ) -> Optional[dict]:
        """
        Cria uma nova tarefa no Todoist.
        
        Args:
            content: Título da tarefa
            description: Descrição (opcional)
            due_string: Prazo em linguagem natural (ex: "amanhã às 10h")
            due_datetime: Prazo em formato ISO (ex: "2024-01-23T10:00:00")
            priority: Prioridade (1-4, onde 4 é mais urgente)
            project_id: ID do projeto
            labels: Lista de labels
            
        Returns:
            Tarefa criada ou None se falhar
        """
        if not self.api:
            return None

        try:
            kwargs = {"content": content}
            
            if description:
                kwargs["description"] = description
            if due_string:
                kwargs["due_string"] = due_string
            if due_datetime:
                kwargs["due_datetime"] = due_datetime
            if priority:
                kwargs["priority"] = priority
            if project_id:
                kwargs["project_id"] = project_id
            if labels:
                kwargs["labels"] = labels

            task = self.api.add_task(**kwargs)
            
            logger.info(f"✅ Tarefa criada: {content}")
            
            return {
                "id": task.id,
                "content": task.content,
                "description": task.description,
                "due": task.due.__dict__ if task.due else None,
                "priority": task.priority,
                "project_id": task.project_id,
                "url": task.url,
            }
        except Exception as e:
            logger.error(f"❌ Erro ao criar tarefa: {e}")
            return None

    async def complete_task(self, task_id: str) -> bool:
        """Marca uma tarefa como concluída."""
        if not self.api:
            return False

        try:
            self.api.close_task(task_id)
            logger.info(f"✅ Tarefa {task_id} concluída")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao concluir tarefa {task_id}: {e}")
            return False

    async def update_task(
        self,
        task_id: str,
        content: str = None,
        description: str = None,
        due_string: str = None,
        priority: int = None,
    ) -> bool:
        """Atualiza uma tarefa existente."""
        if not self.api:
            return False

        try:
            kwargs = {}
            if content:
                kwargs["content"] = content
            if description:
                kwargs["description"] = description
            if due_string:
                kwargs["due_string"] = due_string
            if priority:
                kwargs["priority"] = priority

            self.api.update_task(task_id, **kwargs)
            logger.info(f"✅ Tarefa {task_id} atualizada")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar tarefa {task_id}: {e}")
            return False

    async def delete_task(self, task_id: str) -> bool:
        """Deleta uma tarefa."""
        if not self.api:
            return False

        try:
            self.api.delete_task(task_id)
            logger.info(f"✅ Tarefa {task_id} deletada")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao deletar tarefa {task_id}: {e}")
            return False

    async def get_projects(self, include_welcome: bool = False) -> list[dict]:
        """Retorna todos os projetos do Todoist."""
        if not self.api:
            return []

        try:
            projects = self.api.get_projects()
            
            if include_welcome:
                # Retorna todos os projetos sem filtro
                return [
                    {
                        "id": project.id,
                        "name": project.name,
                        "color": project.color,
                        "is_favorite": project.is_favorite,
                        "url": project.url,
                    }
                    for project in projects
                ]
            else:
                # Filtra projetos de boas-vindas
                welcome_keywords = [
                    "inbox",
                    "primeiros passos",
                    "getting started",
                    "welcome",
                    "bem-vindo",
                    "tutorial",
                    "exemplos",
                    "samples"
                ]
                
                filtered_projects = []
                for project in projects:
                    name_lower = project.name.lower()
                    # Verificar se é projeto de boas-vindas
                    is_welcome_project = any(keyword in name_lower for keyword in welcome_keywords)
                    
                    # Incluir apenas se não for projeto de boas-vindas
                    if not is_welcome_project:
                        filtered_projects.append({
                            "id": project.id,
                            "name": project.name,
                            "color": project.color,
                            "is_favorite": project.is_favorite,
                            "url": project.url,
                        })
                
                return filtered_projects
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar projetos: {e}")
            return []

    async def get_labels(self) -> list[dict]:
        """Retorna todas as labels do Todoist."""
        if not self.api:
            return []

        try:
            labels = self.api.get_labels()
            return [
                {
                    "id": label.id,
                    "name": label.name,
                    "color": label.color,
                }
                for label in labels
            ]
        except Exception as e:
            logger.error(f"❌ Erro ao buscar labels: {e}")
            return []


# Singleton para reutilização
_todoist_service: Optional[TodoistMonitorService] = None


def get_todoist_service() -> TodoistMonitorService:
    """Retorna instância singleton do serviço Todoist."""
    global _todoist_service
    if _todoist_service is None:
        _todoist_service = TodoistMonitorService()
    return _todoist_service
