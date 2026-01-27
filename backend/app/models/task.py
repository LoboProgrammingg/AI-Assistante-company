"""
Modelo de Tarefas - Gerenciador de Tarefas Avançado.

Funcionalidades:
- Tarefas com título, descrição, prioridade
- Status Kanban (backlog, todo, in_progress, done)
- Projetos para organização
- Etiquetas/tags
- Subtarefas
- Data de vencimento com alertas
- Recorrência (similar a lembretes)
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, RecurrenceType, utc_now


class TaskPriority(enum.Enum):
    """Prioridade da tarefa."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(enum.Enum):
    """Status Kanban da tarefa."""
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class Project(Base):
    """Modelo de Projeto para organizar tarefas."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#3B82F6")  # Hex color
    icon = Column(String(50), nullable=True)
    
    is_active = Column(Boolean, default=True)
    is_favorite = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}')>"


class TaskLabel(Base):
    """Modelo de Etiquetas para tarefas."""
    __tablename__ = "task_labels"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(50), nullable=False)
    color = Column(String(7), default="#6B7280")  # Hex color

    created_at = Column(DateTime, default=utc_now)

    # Relationships
    user = relationship("User", back_populates="task_labels")

    def __repr__(self):
        return f"<TaskLabel(id={self.id}, name='{self.name}')>"


class Task(Base):
    """Modelo de Tarefa com funcionalidades avançadas."""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Hierarquia
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True)

    # Conteúdo
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Status e Prioridade
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO, nullable=False, index=True)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False, index=True)
    
    # Datas
    due_date = Column(DateTime, nullable=True, index=True)
    remind_before_minutes = Column(Integer, default=60)
    
    # Recorrência
    recurrence_type = Column(Enum(RecurrenceType), default=RecurrenceType.ONCE)
    
    # Metadados
    labels = Column(JSON, default=[])  # Lista de label IDs
    estimated_minutes = Column(Integer, nullable=True)
    actual_minutes = Column(Integer, nullable=True)
    
    # Controle
    is_active = Column(Boolean, default=True)
    notified = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="tasks")
    project = relationship("Project", back_populates="tasks")
    subtasks = relationship("Task", back_populates="parent", cascade="all, delete-orphan")
    parent = relationship("Task", back_populates="subtasks", remote_side=[id])

    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title[:30]}', status={self.status.value})>"
    
    @property
    def is_overdue(self) -> bool:
        """Verifica se a tarefa está atrasada."""
        if self.due_date and self.status not in [TaskStatus.DONE, TaskStatus.CANCELLED]:
            return datetime.utcnow() > self.due_date
        return False
    
    @property
    def subtask_count(self) -> int:
        """Conta subtarefas."""
        return len(self.subtasks) if self.subtasks else 0
    
    @property
    def completed_subtask_count(self) -> int:
        """Conta subtarefas completas."""
        if not self.subtasks:
            return 0
        return sum(1 for s in self.subtasks if s.status == TaskStatus.DONE)
