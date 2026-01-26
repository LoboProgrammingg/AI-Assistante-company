"""
UserDataLoader - Carrega TODOS os dados do usuário do banco de dados.

Este módulo é responsável por buscar dados completos do usuário para
fornecer contexto rico à IA, permitindo respostas inteligentes e precisas.

Dados carregados:
- Finanças (30 dias + mês anterior)
- Lembretes ativos
- Contatos
- Reuniões recentes
- Mensagens agendadas
- Metas do usuário
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from calendar import monthrange

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import (
    Finance, FinanceType, FinanceCategory,
    Reminder,
    Contact,
    Meeting,
    ScheduledMessage, ScheduledMessageStatus,
    UserMemory,
)

logger = logging.getLogger(__name__)


class UserDataLoader:
    """Carrega dados completos do usuário para contexto da IA."""
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._cache: Dict[str, Any] = {}
    
    def load_full_context(self, include_previous_month: bool = True) -> Dict[str, Any]:
        """
        Carrega contexto completo do usuário.
        
        Args:
            include_previous_month: Se True, inclui dados do mês anterior
            
        Returns:
            Dict com todos os dados do usuário
        """
        if "full_context" in self._cache:
            return self._cache["full_context"]
        
        context = {
            "finance": self._load_finance_data(include_previous_month),
            "reminders": self._load_reminders(),
            "contacts": self._load_contacts(),
            "meetings": self._load_meetings(),
            "scheduled_messages": self._load_scheduled_messages(),
            "goals": self._load_goals(),
            "summary": {},
        }
        
        context["summary"] = self._build_summary(context)
        
        self._cache["full_context"] = context
        logger.info(f"[DATA_LOADER] Contexto carregado para user {self.user_id}")
        
        return context
    
    def _load_finance_data(self, include_previous_month: bool = True) -> Dict[str, Any]:
        """Carrega dados financeiros completos."""
        today = date.today()
        
        # Período atual (mês atual)
        current_month_start = date(today.year, today.month, 1)
        _, last_day = monthrange(today.year, today.month)
        current_month_end = date(today.year, today.month, last_day)
        
        # Período anterior (mês passado)
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
        
        prev_month_start = date(prev_year, prev_month, 1)
        _, prev_last_day = monthrange(prev_year, prev_month)
        prev_month_end = date(prev_year, prev_month, prev_last_day)
        
        # Buscar transações do mês atual
        current_transactions = self._get_transactions(current_month_start, current_month_end)
        current_summary = self._calculate_summary(current_transactions)
        
        result = {
            "current_month": {
                "period": f"{current_month_start.strftime('%d/%m/%Y')} - {current_month_end.strftime('%d/%m/%Y')}",
                "transactions": current_transactions,
                "summary": current_summary,
                "by_category": self._group_by_category(current_transactions),
            }
        }
        
        if include_previous_month:
            prev_transactions = self._get_transactions(prev_month_start, prev_month_end)
            prev_summary = self._calculate_summary(prev_transactions)
            
            result["previous_month"] = {
                "period": f"{prev_month_start.strftime('%d/%m/%Y')} - {prev_month_end.strftime('%d/%m/%Y')}",
                "transactions": prev_transactions,
                "summary": prev_summary,
                "by_category": self._group_by_category(prev_transactions),
            }
        
        # Top gastos do mês atual
        expenses = [t for t in current_transactions if t["type"] == "expense"]
        result["top_expenses"] = sorted(expenses, key=lambda x: x["amount"], reverse=True)[:10]
        
        # Top receitas do mês atual
        incomes = [t for t in current_transactions if t["type"] == "income"]
        result["top_incomes"] = sorted(incomes, key=lambda x: x["amount"], reverse=True)[:10]
        
        return result
    
    def _get_transactions(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Busca transações em um período."""
        transactions = (
            self.db.query(Finance)
            .filter(
                and_(
                    Finance.user_id == self.user_id,
                    Finance.transaction_date >= start_date,
                    Finance.transaction_date <= end_date,
                )
            )
            .order_by(Finance.transaction_date.desc())
            .all()
        )
        
        return [
            {
                "id": t.id,
                "description": t.description or "Sem descrição",
                "amount": float(t.amount),
                "type": t.type.value,
                "category": t.category.name if t.category else "Outros",
                "date": t.transaction_date.strftime("%Y-%m-%d"),
                "tags": t.tags or [],
            }
            for t in transactions
        ]
    
    def _calculate_summary(self, transactions: List[Dict]) -> Dict[str, Any]:
        """Calcula resumo das transações."""
        total_income = sum(t["amount"] for t in transactions if t["type"] == "income")
        total_expenses = sum(t["amount"] for t in transactions if t["type"] == "expense")
        balance = total_income - total_expenses
        
        return {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "balance": balance,
            "count": len(transactions),
            "savings_rate": round((balance / total_income * 100), 2) if total_income > 0 else 0,
        }
    
    def _group_by_category(self, transactions: List[Dict]) -> List[Dict[str, Any]]:
        """Agrupa transações por categoria."""
        categories = {}
        for t in transactions:
            cat = t["category"]
            if cat not in categories:
                categories[cat] = {"category": cat, "total": 0, "count": 0, "type": t["type"]}
            categories[cat]["total"] += t["amount"]
            categories[cat]["count"] += 1
        
        return sorted(categories.values(), key=lambda x: x["total"], reverse=True)
    
    def _load_reminders(self) -> Dict[str, Any]:
        """Carrega lembretes do usuário."""
        now = datetime.now()
        
        # Lembretes ativos
        active = (
            self.db.query(Reminder)
            .filter(
                and_(
                    Reminder.user_id == self.user_id,
                    Reminder.is_active == True,
                    Reminder.is_completed == False,
                )
            )
            .order_by(Reminder.scheduled_time.asc())
            .limit(50)
            .all()
        )
        
        # Próximos lembretes (próximos 7 dias)
        next_week = now + timedelta(days=7)
        upcoming = [r for r in active if r.scheduled_time and r.scheduled_time <= next_week]
        
        return {
            "active": [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "scheduled_time": r.scheduled_time.strftime("%Y-%m-%d %H:%M") if r.scheduled_time else None,
                    "is_recurring": r.recurrence_type.value != "once" if r.recurrence_type else False,
                }
                for r in active
            ],
            "upcoming_count": len(upcoming),
            "total_active": len(active),
        }
    
    def _load_contacts(self) -> Dict[str, Any]:
        """Carrega contatos do usuário."""
        contacts = (
            self.db.query(Contact)
            .filter(
                and_(
                    Contact.user_id == self.user_id,
                    Contact.is_active == True,
                )
            )
            .order_by(Contact.name.asc())
            .all()
        )
        
        # Agrupar por grupo
        by_group = {}
        for c in contacts:
            group = c.group_name or "outros"
            if group not in by_group:
                by_group[group] = []
            by_group[group].append({
                "id": c.id,
                "name": c.name,
                "phone": c.phone_number,
            })
        
        return {
            "total": len(contacts),
            "by_group": by_group,
            "list": [
                {
                    "id": c.id,
                    "name": c.name,
                    "phone": c.phone_number,
                    "group": c.group_name or "outros",
                }
                for c in contacts[:30]  # Limite para não sobrecarregar
            ],
        }
    
    def _load_meetings(self) -> Dict[str, Any]:
        """Carrega reuniões recentes."""
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        meetings = (
            self.db.query(Meeting)
            .filter(
                and_(
                    Meeting.user_id == self.user_id,
                    Meeting.created_at >= thirty_days_ago,
                )
            )
            .order_by(Meeting.date.desc())
            .limit(20)
            .all()
        )
        
        return {
            "total": len(meetings),
            "recent": [
                {
                    "id": m.id,
                    "title": m.title,
                    "date": m.date.strftime("%Y-%m-%d %H:%M") if m.date else None,
                    "summary": m.summary[:200] if m.summary else None,
                    "action_items": m.action_items or [],
                }
                for m in meetings[:10]
            ],
        }
    
    def _load_scheduled_messages(self) -> Dict[str, Any]:
        """Carrega mensagens agendadas."""
        pending = (
            self.db.query(ScheduledMessage)
            .filter(
                and_(
                    ScheduledMessage.user_id == self.user_id,
                    ScheduledMessage.status == ScheduledMessageStatus.PENDING,
                )
            )
            .order_by(ScheduledMessage.scheduled_time.asc())
            .all()
        )
        
        return {
            "pending_count": len(pending),
            "pending": [
                {
                    "id": m.id,
                    "recipient": m.recipient_name or m.group_name or "Desconhecido",
                    "message_preview": m.message[:50] + "..." if len(m.message) > 50 else m.message,
                    "scheduled_time": m.scheduled_time.strftime("%Y-%m-%d %H:%M") if m.scheduled_time else None,
                }
                for m in pending[:10]
            ],
        }
    
    def _load_goals(self) -> Dict[str, Any]:
        """Carrega metas do usuário (do sistema de memória)."""
        try:
            goals_memory = (
                self.db.query(UserMemory)
                .filter(
                    and_(
                        UserMemory.user_id == self.user_id,
                        UserMemory.memory_type == "goal",
                        UserMemory.is_active == True,
                    )
                )
                .all()
            )
            
            return {
                "active": [
                    {
                        "id": g.id,
                        "content": g.content,
                        "created_at": g.created_at.strftime("%Y-%m-%d") if g.created_at else None,
                    }
                    for g in goals_memory
                ],
                "total": len(goals_memory),
            }
        except Exception:
            return {"active": [], "total": 0}
    
    def _build_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Constrói resumo geral do contexto."""
        finance = context.get("finance", {})
        current = finance.get("current_month", {}).get("summary", {})
        
        return {
            "finance": {
                "current_balance": current.get("balance", 0),
                "current_expenses": current.get("total_expenses", 0),
                "current_income": current.get("total_income", 0),
                "transactions_count": current.get("count", 0),
            },
            "reminders": {
                "active_count": context.get("reminders", {}).get("total_active", 0),
                "upcoming_count": context.get("reminders", {}).get("upcoming_count", 0),
            },
            "contacts": {
                "total": context.get("contacts", {}).get("total", 0),
            },
            "meetings": {
                "recent_count": context.get("meetings", {}).get("total", 0),
            },
            "messages": {
                "pending_count": context.get("scheduled_messages", {}).get("pending_count", 0),
            },
        }
    
    def get_finance_for_period(self, period: str, year: int = None) -> Dict[str, Any]:
        """
        Busca dados financeiros para um período específico.
        
        Args:
            period: 'hoje', 'semana', 'mes', 'ano', ou nome do mês
            year: Ano específico (opcional)
        """
        today = date.today()
        year = year or today.year
        
        MONTH_NAMES = {
            "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
            "abril": 4, "maio": 5, "junho": 6, "julho": 7,
            "agosto": 8, "setembro": 9, "outubro": 10,
            "novembro": 11, "dezembro": 12,
        }
        
        period_lower = period.lower().strip()
        
        if period_lower in MONTH_NAMES:
            month = MONTH_NAMES[period_lower]
            start = date(year, month, 1)
            _, last_day = monthrange(year, month)
            end = date(year, month, last_day)
        elif period_lower == "hoje":
            start = end = today
        elif period_lower == "semana":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
        elif period_lower == "mes":
            start = date(today.year, today.month, 1)
            _, last_day = monthrange(today.year, today.month)
            end = date(today.year, today.month, last_day)
        elif period_lower == "ano":
            start = date(year, 1, 1)
            end = date(year, 12, 31)
        elif period_lower == "mes_anterior":
            if today.month == 1:
                prev_month, prev_year = 12, today.year - 1
            else:
                prev_month, prev_year = today.month - 1, today.year
            start = date(prev_year, prev_month, 1)
            _, last_day = monthrange(prev_year, prev_month)
            end = date(prev_year, prev_month, last_day)
        else:
            start = date(today.year, today.month, 1)
            _, last_day = monthrange(today.year, today.month)
            end = date(today.year, today.month, last_day)
        
        transactions = self._get_transactions(start, end)
        summary = self._calculate_summary(transactions)
        
        return {
            "period": f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}",
            "transactions": transactions,
            "summary": summary,
            "by_category": self._group_by_category(transactions),
            "top_expenses": sorted(
                [t for t in transactions if t["type"] == "expense"],
                key=lambda x: x["amount"],
                reverse=True
            )[:10],
        }
    
    def search_transactions(self, query: str, period: str = "mes") -> List[Dict[str, Any]]:
        """Busca transações por termo."""
        data = self.get_finance_for_period(period)
        query_lower = query.lower()
        
        return [
            t for t in data["transactions"]
            if query_lower in t["description"].lower() or query_lower in t["category"].lower()
        ]
    
    def clear_cache(self):
        """Limpa cache interno."""
        self._cache.clear()
