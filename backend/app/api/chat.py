import logging
import os
import tempfile
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dateutil import parser as date_parser
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai import MeetingAgent
from app.ai.graph_v3.migration import process_message as process_message_v3, GRAPH_VERSION
from app.api.deps import get_current_user, get_db
from app.config import settings
from app.models import (
    Finance,
    FinanceType,
    Meeting,
    Message,
    RecurrenceType,
    Reminder,
    User,
)
from app.utils.audio_processor import AudioProcessor

logger = logging.getLogger(__name__)

MEETING_DURATION_THRESHOLD = 60  # segundos - áudios maiores que isso são considerados reuniões
MEETING_WORD_THRESHOLD = 200  # palavras - transcrições maiores que isso são consideradas reuniões


def create_reminder_from_entities(
    db: Session, user_id: int, entities: dict, user_timezone: str = "America/Cuiaba"
) -> Reminder:
    """Cria um lembrete a partir das entidades extraídas pela IA."""
    reminder_data = entities.get("reminder", {})

    title = reminder_data.get("title", "Lembrete")
    description = reminder_data.get("description")
    scheduled_time_str = reminder_data.get("scheduled_time")
    remind_before = reminder_data.get("remind_before_minutes", 0)
    recurrence = reminder_data.get("recurrence_type", "once")

    from datetime import timedelta

    import pytz

    from app.utils.timezone_helper import get_current_time_for_user

    # Obter horário atual no timezone do usuário
    user_tz = pytz.timezone(user_timezone)
    current_time_user = get_current_time_for_user(user_timezone)

    if scheduled_time_str:
        try:
            scheduled_time = date_parser.parse(scheduled_time_str)
            # Se não tem data completa, usar a data de hoje
            if scheduled_time.year == 1900:  # dateutil usa 1900 quando não há ano
                scheduled_time = scheduled_time.replace(
                    year=current_time_user.year, month=current_time_user.month, day=current_time_user.day
                )
            # Localizar no timezone do usuário e converter para UTC
            if scheduled_time.tzinfo is None:
                scheduled_time = user_tz.localize(scheduled_time)
            scheduled_time = scheduled_time.astimezone(pytz.UTC)
        except:
            scheduled_time = datetime.now(pytz.UTC)
    else:
        scheduled_time = datetime.now(pytz.UTC)

    actual_reminder_time = scheduled_time
    if remind_before:
        actual_reminder_time = scheduled_time - timedelta(minutes=remind_before)

    recurrence_map = {
        "once": RecurrenceType.ONCE,
        "daily": RecurrenceType.DAILY,
        "weekly": RecurrenceType.WEEKLY,
        "weekdays": RecurrenceType.WEEKDAYS,
        "weekends": RecurrenceType.WEEKENDS,
        "monthly": RecurrenceType.MONTHLY,
        "yearly": RecurrenceType.YEARLY,
    }

    reminder = Reminder(
        user_id=user_id,
        title=title,
        description=description,
        scheduled_time=scheduled_time,
        remind_before_minutes=remind_before or 0,
        actual_reminder_time=actual_reminder_time,
        recurrence_type=recurrence_map.get(recurrence, RecurrenceType.ONCE),
        is_active=True,
        is_completed=False,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    logger.info(f"Lembrete criado: {reminder.id} - {reminder.title}")
    return reminder


def delete_finance_by_id(db: Session, user_id: int, finance_id: int) -> bool:
    """Deleta uma transação financeira pelo ID."""
    finance = db.query(Finance).filter(Finance.id == finance_id, Finance.user_id == user_id).first()

    if finance:
        db.delete(finance)
        db.commit()
        logger.info(f"Transação deletada: {finance_id}")
        return True
    return False


def delete_reminder_by_id(db: Session, user_id: int, reminder_id: int) -> bool:
    """Deleta um lembrete pelo ID."""
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == user_id).first()

    if reminder:
        db.delete(reminder)
        db.commit()
        logger.info(f"Lembrete deletado: {reminder_id}")
        return True
    return False


def create_finance_from_entities(
    db: Session, user_id: int, entities: dict, timezone: str = "America/Sao_Paulo"
) -> Finance:
    """Cria uma transação financeira a partir das entidades extraídas pela IA."""
    from app.models import FinanceCategory
    from app.utils.timezone_helper import get_current_time_for_user

    finance_data = entities.get("finance", {})

    finance_type = finance_data.get("type", "expense")
    amount = finance_data.get("amount", 0)
    description = finance_data.get("description", "")
    category_name = finance_data.get("category", "Outros")
    finance_data.get("transaction_date")
    is_recurring = finance_data.get("is_recurring", False)
    tags = finance_data.get("tags", [])

    # Usar apenas a DATA (sem hora) do timezone do usuário
    current_time = get_current_time_for_user(timezone)
    transaction_date = current_time.date()

    # Buscar categoria pelo nome
    fin_type = FinanceType.EXPENSE if finance_type == "expense" else FinanceType.INCOME
    category = (
        db.query(FinanceCategory)
        .filter(FinanceCategory.name.ilike(f"%{category_name}%"), FinanceCategory.type == fin_type)
        .first()
    )

    # Fallback para "Outros" se não encontrar
    if not category:
        category = (
            db.query(FinanceCategory)
            .filter(FinanceCategory.name.ilike("%outros%"), FinanceCategory.type == fin_type)
            .first()
        )

    logger.info(
        f"Data da transação: {transaction_date.strftime('%d/%m/%Y')}, Categoria: {category.name if category else 'N/A'}"
    )

    finance = Finance(
        user_id=user_id,
        type=fin_type,
        amount=float(amount) if amount else 0,
        description=description,
        category_id=category.id if category else None,
        transaction_date=transaction_date,
        is_recurring=is_recurring,
        tags=tags,
    )
    db.add(finance)
    db.commit()
    db.refresh(finance)
    logger.info(
        f"Transação criada: {finance.id} - R${finance.amount} - {category.name if category else 'Sem categoria'}"
    )
    return finance


router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    intent: str
    entities: dict
    next_action: str


def save_message(
    db: Session,
    user_id: int,
    content: str,
    direction: str,
    intent: str = None,
    entities: dict = None,
    ai_response: str = None,
) -> Message:
    """Salva mensagem no banco de dados."""
    message = Message(
        user_id=user_id,
        message_type="text",
        content=content,
        direction=direction,
        wa_message_id=f"web_{uuid.uuid4().hex[:16]}",
        intent=intent,
        entities=entities,
        ai_response=ai_response,
        created_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc) if direction == "incoming" else None,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.post("/message", response_model=ChatResponse)
async def send_message(
    data: ChatRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Processa mensagem do usuário via chat e retorna resposta do AI.
    """
    if not data.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mensagem não pode estar vazia")

    try:
        save_message(db=db, user_id=current_user.id, content=data.message, direction="incoming")

        # Usa camada de migração (v2 ou v3 via env IRIS_GRAPH_VERSION)
        logger.info(f"[CHAT] Processando com Graph {GRAPH_VERSION}")
        result = await process_message_v3(
            user_id=current_user.id,
            session_id=current_user.session_id or str(current_user.id),
            message=data.message,
            context={"user_name": current_user.name},
            db=db,
        )

        save_message(
            db=db,
            user_id=current_user.id,
            content=result["response"],
            direction="outgoing",
            intent=result["intent"],
            entities=result["entities"],
            ai_response=result["response"],
        )

        return ChatResponse(
            response=result["response"],
            intent=result.get("intent", "general"),
            entities=result.get("entities", {}),
            next_action=result.get("next_action", ""),
        )
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao processar mensagem: {str(e)}"
        )


class AudioResponse(BaseModel):
    response: str
    intent: str
    entities: dict
    next_action: str
    transcription: str
    is_meeting: bool
    meeting_id: Optional[int] = None


def is_meeting_audio(transcription: str, file_size: int) -> bool:
    """Determina se o áudio é uma reunião baseado no tamanho e conteúdo."""
    word_count = len(transcription.split())

    logger.info(f"Análise de áudio: {word_count} palavras, {file_size} bytes")

    # Se tem muitas palavras, provavelmente é uma reunião
    if word_count > MEETING_WORD_THRESHOLD:
        logger.info(f"Detectado como reunião: muitas palavras ({word_count} > {MEETING_WORD_THRESHOLD})")
        return True

    # Verificar palavras-chave de reunião
    meeting_keywords = [
        "reunião",
        "meeting",
        "participantes",
        "pauta",
        "agenda",
        "ata",
        "decisão",
        "ação",
        "próximos passos",
        "discussão",
        "apresentação",
        "projeto",
        "equipe",
        "time",
        "sprint",
        "finalizar",
        "integração",
        "desenvolvimento",
        "funcionalidade",
    ]

    transcription_lower = transcription.lower()
    keyword_count = sum(1 for kw in meeting_keywords if kw in transcription_lower)

    logger.info(f"Palavras-chave de reunião encontradas: {keyword_count}")

    # Se tem várias palavras-chave de reunião (reduzido de 3 para 2)
    if keyword_count >= 2:
        logger.info(f"Detectado como reunião: palavras-chave ({keyword_count} >= 2)")
        return True

    # Se tem mais de 100 palavras e pelo menos 1 palavra-chave, considerar reunião
    if word_count > 100 and keyword_count >= 1:
        logger.info(f"Detectado como reunião: 100+ palavras com palavra-chave")
        return True

    logger.info("Não detectado como reunião, processando como comando")
    return False


async def process_meeting_audio(db: Session, user_id: int, transcription: str, user_name: str) -> tuple[str, int]:
    """Processa áudio como reunião e cria registro."""
    meeting_agent = MeetingAgent()

    # Processar com o agente de reuniões
    result = await meeting_agent.process(
        message=transcription, context={"user_name": user_name, "is_transcription": True}
    )

    entities = result.get("entities", {})
    meeting_data = entities.get("meeting", {})

    # Criar registro de reunião
    meeting = Meeting(
        user_id=user_id,
        title=meeting_data.get("title", "Reunião sem título"),
        transcription=transcription,
        summary=meeting_data.get("summary", ""),
        key_topics=meeting_data.get("key_topics", []),
        action_items=meeting_data.get("action_items", []),
        decisions=meeting_data.get("decisions", []),
        participants=meeting_data.get("participants", []),
        duration_minutes=meeting_data.get("duration_minutes", 0),
        date=datetime.now(timezone.utc),
    )

    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    logger.info(f"Reunião criada: {meeting.id} - {meeting.title}")

    return result.get("response", "Reunião processada com sucesso!"), meeting.id


@router.post("/audio", response_model=AudioResponse)
async def send_audio(
    audio: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Processa áudio enviado pelo usuário.
    - Áudios curtos: processados como comandos normais (lembretes, finanças)
    - Áudios longos/reuniões: transcritos e resumidos como reunião
    """
    try:
        # Validar tipo de arquivo
        allowed_types = ["audio/mpeg", "audio/wav", "audio/ogg", "audio/webm", "audio/mp4", "audio/m4a", "audio/x-m4a"]
        content_type = audio.content_type or ""
        filename = audio.filename or "audio.webm"

        is_valid = content_type in allowed_types or any(
            filename.lower().endswith(ext) for ext in [".mp3", ".wav", ".ogg", ".webm", ".m4a", ".opus"]
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Formato de áudio não suportado: {content_type}"
            )

        # Salvar arquivo temporário
        suffix = Path(filename).suffix or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            # Transcrever áudio
            processor = AudioProcessor(settings.GOOGLE_API_KEY)
            transcription = await processor.transcribe_audio(tmp_path)

            if not transcription:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Não foi possível transcrever o áudio"
                )

            logger.info(f"Áudio transcrito: {len(transcription)} caracteres")

            # Salvar mensagem incoming
            save_message(
                db=db, user_id=current_user.id, content=f"[Áudio] {transcription[:200]}...", direction="incoming"
            )

            # Determinar se é reunião ou comando simples
            is_meeting = is_meeting_audio(transcription, len(content))

            if is_meeting:
                # Processar como reunião
                response, meeting_id = await process_meeting_audio(
                    db=db, user_id=current_user.id, transcription=transcription, user_name=current_user.name or ""
                )

                save_message(
                    db=db,
                    user_id=current_user.id,
                    content=response,
                    direction="outgoing",
                    intent="meeting",
                    ai_response=response,
                )

                return AudioResponse(
                    response=response,
                    intent="meeting",
                    entities={"meeting_id": meeting_id},
                    next_action="create_meeting",
                    transcription=transcription,
                    is_meeting=True,
                    meeting_id=meeting_id,
                )
            else:
                # Processar como comando normal (usa camada de migração v2/v3)
                result = await process_message_v3(
                    user_id=current_user.id,
                    session_id=current_user.session_id or str(current_user.id),
                    message=transcription,
                    context={"user_name": current_user.name},
                    db=db,
                )

                save_message(
                    db=db,
                    user_id=current_user.id,
                    content=result["response"],
                    direction="outgoing",
                    intent=result["intent"],
                    entities=result["entities"],
                    ai_response=result["response"],
                )

                return AudioResponse(
                    response=result["response"],
                    intent=result["intent"],
                    entities=result["entities"],
                    next_action=result["next_action"],
                    transcription=transcription,
                    is_meeting=False,
                )

        finally:
            # Limpar arquivo temporário
            if tmp_path.exists():
                os.unlink(tmp_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar áudio: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao processar áudio: {str(e)}"
        )
