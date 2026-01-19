from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON, Enum, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()


def utc_now():
    """Retorna datetime atual em UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


class RecurrenceType(enum.Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKDAYS = "weekdays"  # Segunda a Sexta
    WEEKENDS = "weekends"  # Sábado e Domingo
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class FinanceType(enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class ContactGroupEnum(enum.Enum):
    """Grupos padrão de contatos (mantido para compatibilidade)."""
    FAMILY = "family"
    FRIEND = "friend"
    EMPLOYEE = "employee"
    COLLEAGUE = "colleague"
    CLIENT = "client"
    OTHER = "other"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    session_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    timezone = Column(String, default="America/Sao_Paulo")
    language = Column(String, default="pt-BR")
    
    # Campos de autenticação
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    last_interaction = Column(DateTime, default=utc_now)
    
    # User preferences
    preferences = Column(JSON, default={})
    
    # Relationships
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    finances = relationship("Finance", back_populates="user", cascade="all, delete-orphan")
    meetings = relationship("Meeting", back_populates="user", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")
    contact_groups = relationship("CustomContactGroup", back_populates="user", cascade="all, delete-orphan")
    scheduled_messages = relationship("ScheduledMessage", back_populates="user", cascade="all, delete-orphan")
    verification_tokens = relationship("VerificationToken", back_populates="user", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Message content
    message_type = Column(String)  # text, audio, image
    content = Column(Text, nullable=True)
    audio_url = Column(String, nullable=True)
    audio_transcription = Column(Text, nullable=True)
    
    # Message direction
    direction = Column(String)  # incoming, outgoing
    
    # WhatsApp specific
    wa_message_id = Column(String, unique=True, index=True)
    wa_status = Column(String, nullable=True)
    
    # AI Processing
    intent = Column(String, nullable=True)
    entities = Column(JSON, nullable=True)
    ai_response = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=utc_now)
    processed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="messages")


class Reminder(Base):
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Reminder details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Timing
    scheduled_time = Column(DateTime, nullable=False)
    remind_before_minutes = Column(Integer, default=0)
    actual_reminder_time = Column(DateTime, nullable=False)
    
    # Recurrence
    recurrence_type = Column(Enum(RecurrenceType), default=RecurrenceType.ONCE)
    recurrence_config = Column(JSON, nullable=True)  # Para custom patterns
    
    # Status
    is_active = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = relationship("User", back_populates="reminders")


class FinanceCategory(Base):
    __tablename__ = "finance_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(Enum(FinanceType), nullable=False)
    icon = Column(String, nullable=True)
    color = Column(String, nullable=True)
    
    # Relationships
    finances = relationship("Finance", back_populates="category")


class Finance(Base):
    __tablename__ = "finances"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("finance_categories.id"), nullable=True)
    
    # Finance details
    type = Column(Enum(FinanceType), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    
    # Timing
    transaction_date = Column(DateTime, nullable=False)
    
    # Recurrence (for recurring expenses/income)
    is_recurring = Column(Boolean, default=False)
    recurrence_type = Column(Enum(RecurrenceType), nullable=True)
    
    # Tags for better organization
    tags = Column(JSON, default=[])
    
    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = relationship("User", back_populates="finances")
    category = relationship("FinanceCategory", back_populates="finances")


class Meeting(Base):
    __tablename__ = "meetings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Meeting details
    title = Column(String, nullable=True)
    date = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    
    # Audio
    audio_url = Column(String, nullable=True)
    transcription = Column(Text, nullable=True)
    
    # AI Analysis
    summary = Column(Text, nullable=True)
    key_topics = Column(JSON, default=[])
    action_items = Column(JSON, default=[])
    participants = Column(JSON, default=[])
    decisions = Column(JSON, default=[])
    
    # Additional metadata
    sentiment = Column(String, nullable=True)
    keywords = Column(JSON, default=[])
    
    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = relationship("User", back_populates="meetings")


class ConversationMemory(Base):
    __tablename__ = "conversation_memory"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Memory content
    key = Column(String, nullable=False)
    value = Column(JSON, nullable=False)
    
    # Context
    context_window = Column(Integer, default=10)  # Last N messages
    
    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    accessed_at = Column(DateTime, default=utc_now)


class CustomContactGroup(Base):
    """Grupos customizados de contatos criados pelo usuário."""
    __tablename__ = "custom_contact_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String(100), nullable=False)  # Nome do grupo (ex: "Funcionários", "Família")
    slug = Column(String(100), nullable=False)  # Slug para busca (ex: "funcionarios", "familia")
    description = Column(Text, nullable=True)
    icon = Column(String(10), nullable=True)  # Emoji para o grupo
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = relationship("User", back_populates="contact_groups")
    contacts = relationship("Contact", back_populates="custom_group")


class Contact(Base):
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("custom_contact_groups.id"), nullable=True)
    
    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    group_name = Column(String(100), default="outros")  # Nome do grupo (flexível)
    notes = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = relationship("User", back_populates="contacts")
    custom_group = relationship("CustomContactGroup", back_populates="contacts")
    scheduled_messages = relationship("ScheduledMessage", back_populates="contact")


class ScheduledMessageStatus(enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledMessage(Base):
    """Mensagens agendadas para envio automático a contatos."""
    __tablename__ = "scheduled_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    
    # Destinatário (pode ser contato ou grupo)
    recipient_phone = Column(String, nullable=True)  # Telefone direto (se não for contato)
    recipient_name = Column(String, nullable=True)   # Nome do destinatário
    group_name = Column(String(100), nullable=True)  # Se for para um grupo inteiro
    
    # Mensagem
    message = Column(Text, nullable=False)
    
    # Agendamento
    scheduled_time = Column(DateTime, nullable=False)
    
    # Status
    status = Column(Enum(ScheduledMessageStatus), default=ScheduledMessageStatus.PENDING)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Recorrência (opcional)
    recurrence_type = Column(Enum(RecurrenceType), default=RecurrenceType.ONCE)
    
    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = relationship("User", back_populates="scheduled_messages")
    contact = relationship("Contact", back_populates="scheduled_messages")


class VerificationTokenType(enum.Enum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class VerificationToken(Base):
    """Token para verificação de email ou reset de senha."""
    __tablename__ = "verification_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(6), nullable=False)  # Código de 6 dígitos
    token_type = Column(Enum(VerificationTokenType), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    
    # Relationships
    user = relationship("User", back_populates="verification_tokens")


class PlanType(enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Plan(Base):
    """Planos de assinatura."""
    __tablename__ = "plans"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    type = Column(Enum(PlanType), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    price = Column(Float, default=0.0)
    features = Column(JSON, default={})
    limits = Column(JSON, default={})  # Limites de uso (mensagens, lembretes, etc)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")


class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"


class Subscription(Base):
    """Assinaturas de usuários."""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    starts_at = Column(DateTime, default=utc_now)
    expires_at = Column(DateTime, nullable=True)  # Null para plano FREE (sem expiração)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = relationship("User", back_populates="subscription")
    plan = relationship("Plan", back_populates="subscriptions")


class DocumentCategory(enum.Enum):
    """Categorias de documentos."""
    WORK = "work"
    PERSONAL = "personal"
    STUDY = "study"
    FINANCE = "finance"
    HEALTH = "health"
    LEGAL = "legal"
    OTHER = "other"


class Document(Base):
    """Documentos do usuário para RAG."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Informações do arquivo
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)  # Em bytes
    mime_type = Column(String(100), nullable=True)
    
    # Metadados
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(Enum(DocumentCategory), default=DocumentCategory.OTHER)
    tags = Column(JSON, default=[])
    
    # Conteúdo extraído para RAG
    content_text = Column(Text, nullable=True)  # Texto extraído do documento
    content_chunks = Column(JSON, default=[])  # Chunks para embedding
    embedding_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    
    # Controle de IA
    send_to_ai = Column(Boolean, default=False)  # Se deve ser usado como contexto para IA
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = relationship("User", back_populates="documents")