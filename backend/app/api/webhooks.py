"""
Webhook endpoints para integração com WhatsApp via Twilio.
Inclui rate limiting e sanitização de inputs.
"""

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from twilio.rest import Client

from app.ai.graph_v3.core import IRISGraphV3
from app.ai.graph_v3.migration import GRAPH_VERSION
from app.ai.graph_v3.migration import process_message as process_message_v3
from app.config import settings
from app.core.input_sanitizer import InputSanitizer
from app.core.rate_limiter import RateLimiter
from app.database import get_db
from app.models import Message, User

logger = logging.getLogger(__name__)

# Inicializar módulos de segurança
rate_limiter = RateLimiter()
input_sanitizer = InputSanitizer()


async def transcribe_audio_from_url(audio_url: str, content_type: str = "audio/ogg") -> str:
    """
    Baixa e transcreve áudio do Twilio usando Google Gemini.

    Args:
        audio_url: URL do áudio no Twilio
        content_type: Tipo MIME do áudio (ex: audio/ogg, audio/mpeg)

    Returns:
        Texto transcrito ou None se falhar
    """
    import os
    import tempfile

    import google.generativeai as genai
    import httpx

    try:
        # Autenticação para baixar do Twilio
        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        # Determinar extensão baseado no content_type
        ext_map = {
            "audio/ogg": ".ogg",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/amr": ".amr",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
        }
        extension = ext_map.get(content_type, ".ogg")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(audio_url, auth=auth, follow_redirects=True)

            if response.status_code != 200:
                logger.error(f"Erro ao baixar áudio: {response.status_code}")
                return None

            # Salvar temporariamente com extensão correta
            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as f:
                f.write(response.content)
                temp_path = f.name

        logger.info(f"Áudio salvo em {temp_path} ({len(response.content)} bytes)")

        # Configurar Gemini
        genai.configure(api_key=settings.GOOGLE_API_KEY)

        # Upload do arquivo para o Gemini com mime_type explícito
        audio_file = genai.upload_file(temp_path, mime_type=content_type)

        # Transcrever
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        result = model.generate_content(
            [
                "Transcreva o áudio a seguir para texto em português brasileiro. Retorne APENAS o texto transcrito, sem formatação adicional, sem aspas, sem explicações.",
                audio_file,
            ]
        )

        # Limpar arquivo temporário
        os.unlink(temp_path)

        transcribed = result.text.strip() if result.text else None
        logger.info(f"Transcrição: {transcribed}")
        return transcribed

    except Exception as e:
        logger.error(f"Erro ao transcrever áudio: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None


router = APIRouter(prefix="/webhook", tags=["webhooks"])

# Twilio client (singleton)
twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

# AI Agent v3 (singleton para melhor performance)
_ai_agent_v3: IRISGraphV3 = None


def get_ai_agent() -> IRISGraphV3:
    """Retorna instância singleton do agente de IA (Graph v3)."""
    global _ai_agent_v3
    if _ai_agent_v3 is None:
        _ai_agent_v3 = IRISGraphV3(api_key=settings.GOOGLE_API_KEY)
    return _ai_agent_v3


def normalize_phone_number(phone: str) -> str:
    """
    Normaliza número de telefone para comparação.
    Remove prefixos e garante formato consistente.

    Exemplos:
        whatsapp:+5565992540370 -> 5565992540370
        +5565992540370 -> 5565992540370
        5565992540370 -> 5565992540370
        65992540370 -> 5565992540370 (adiciona 55 se faltar)
    """
    # Remover prefixos e caracteres especiais
    clean = phone.replace("whatsapp:", "").replace("+", "").replace(" ", "").replace("-", "").strip()

    # Se o número tem 10-11 dígitos (sem código do país), adicionar 55
    if len(clean) == 10 or len(clean) == 11:
        clean = "55" + clean

    return clean


def normalize_phone_with_9(phone: str) -> list:
    """
    Gera variações do número com e sem o 9 adicional.
    No Brasil, números de celular podem ter ou não o 9 extra após o DDD.

    Exemplos:
        5565992540370 -> ['5565992540370', '556592540370']
        556592540370 -> ['556592540370', '5565992540370']
    """
    variations = [phone]

    if len(phone) >= 12 and phone.startswith("55"):
        ddd = phone[2:4]  # Ex: 65
        rest = phone[4:]  # Ex: 992540370 ou 92540370

        # Se tem 9 dígitos após DDD (com o 9 extra), criar versão sem
        if len(rest) == 9 and rest.startswith("9"):
            without_9 = "55" + ddd + rest[1:]  # Remove o 9 extra
            variations.append(without_9)
        # Se tem 8 dígitos após DDD (sem o 9 extra), criar versão com
        elif len(rest) == 8:
            with_9 = "55" + ddd + "9" + rest  # Adiciona o 9 extra
            variations.append(with_9)

    return variations


def phones_match(phone1: str, phone2: str) -> bool:
    """
    Compara dois números de telefone de forma flexível.
    Considera variações com e sem o 9 extra do Brasil.

    Args:
        phone1: Primeiro número normalizado
        phone2: Segundo número normalizado

    Returns:
        True se os números correspondem
    """
    # Gerar todas as variações de ambos os números
    variations1 = normalize_phone_with_9(phone1)
    variations2 = normalize_phone_with_9(phone2)

    # Verificar se alguma variação corresponde
    for v1 in variations1:
        for v2 in variations2:
            if v1 == v2:
                return True

    return False


def get_verified_user(db: Session, phone_number: str) -> User | None:
    """
    Busca usuário VERIFICADO pelo número de telefone.
    Apenas usuários com email verificado podem interagir com a IA.

    Args:
        db: Sessão do banco de dados
        phone_number: Número do WhatsApp (formato: whatsapp:+5511999999999)

    Returns:
        User se encontrado e verificado, None caso contrário
    """
    # Normalizar número recebido do WhatsApp
    clean_number = normalize_phone_number(phone_number)
    logger.info(f"Buscando usuário para número normalizado: {clean_number} (original: {phone_number})")

    # Buscar todos usuários verificados e ativos
    users = db.query(User).filter(User.is_verified == True, User.is_active == True, User.phone_number.isnot(None)).all()

    # Comparar números usando correspondência flexível
    for user in users:
        user_phone_normalized = normalize_phone_number(user.phone_number or "")
        logger.debug(f"Comparando: {user_phone_normalized} vs {clean_number}")
        if phones_match(user_phone_normalized, clean_number):
            logger.info(f"Usuário encontrado: {user.name} (id={user.id})")
            return user

    logger.warning(f"Nenhum usuário verificado encontrado para: {clean_number}")
    return None


def update_user_interaction(db: Session, user: User, profile_name: str = None):
    """
    Atualiza informações do usuário após interação.

    Args:
        db: Sessão do banco de dados
        user: Usuário a ser atualizado
        profile_name: Nome do perfil do WhatsApp (enviado pelo Twilio)
    """
    from datetime import datetime, timezone

    # Atualizar nome se recebemos um ProfileName e o nome atual é genérico
    if profile_name and (not user.name or user.name.startswith("WhatsApp ") or user.name.startswith("Usuário ")):
        user.name = profile_name
        logger.info(f"Nome do usuário atualizado: {profile_name}")

    # Atualizar última interação
    user.last_interaction = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)


def save_whatsapp_message(db: Session, user_id: int, content: str, direction: str, ai_response: str = None):
    """Salva mensagem do WhatsApp no banco."""
    message = Message(user_id=user_id, content=content, direction=direction, ai_response=ai_response)
    db.add(message)
    db.commit()
    return message


def split_message(text: str, max_length: int = 1500) -> list:
    """
    Divide mensagem longa em partes menores respeitando limite do WhatsApp.
    
    Tenta dividir em quebras de linha ou espaços para não cortar palavras.
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current = text
    
    while len(current) > max_length:
        # Tentar dividir em quebra de linha dupla (parágrafo)
        split_pos = current.rfind("\n\n", 0, max_length)
        
        # Se não encontrou, tentar quebra de linha simples
        if split_pos == -1:
            split_pos = current.rfind("\n", 0, max_length)
        
        # Se não encontrou, tentar espaço
        if split_pos == -1:
            split_pos = current.rfind(" ", 0, max_length)
        
        # Último recurso: cortar no limite
        if split_pos == -1:
            split_pos = max_length
        
        parts.append(current[:split_pos].strip())
        current = current[split_pos:].strip()
    
    if current:
        parts.append(current)
    
    return parts


def send_whatsapp_message(to: str, body: str):
    """Envia mensagem via WhatsApp usando Twilio."""
    try:
        # Garantir formato correto
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"

        from_number = settings.TWILIO_WHATSAPP_NUMBER
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        # Dividir mensagem se exceder limite do WhatsApp (1600 chars)
        parts = split_message(body, max_length=1500)
        
        message_sids = []
        for i, part in enumerate(parts):
            if len(parts) > 1:
                # Adicionar indicador de parte se houver múltiplas
                part_indicator = f"({i+1}/{len(parts)})\n" if i > 0 else ""
                part = part_indicator + part
            
            message = twilio_client.messages.create(body=part, from_=from_number, to=to)
            message_sids.append(message.sid)
            logger.info(f"Mensagem {i+1}/{len(parts)} enviada para {to}: {message.sid}")
        
        return message_sids[0] if message_sids else None
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem WhatsApp: {e}")
        raise


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
    From: str = Form(...),
    Body: str = Form(""),
    MessageSid: str = Form(None),
    NumMedia: str = Form("0"),
    ProfileName: str = Form(None),
    WaId: str = Form(None),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    """
    Webhook para receber mensagens do WhatsApp via Twilio.

    O Twilio envia um POST com os seguintes campos:
    - From: número do remetente (formato: whatsapp:+5511999999999)
    - Body: conteúdo da mensagem (vazio se for só áudio)
    - MessageSid: ID único da mensagem
    - NumMedia: quantidade de arquivos de mídia
    - ProfileName: nome do perfil do WhatsApp do usuário
    - WaId: ID do WhatsApp do usuário (número sem formatação)
    - MediaUrl0: URL do arquivo de mídia (se houver)
    - MediaContentType0: Tipo do arquivo (audio/ogg, image/jpeg, etc.)
    """
    try:
        # Buscar usuário VERIFICADO pelo número de telefone
        user = get_verified_user(db, From)

        # === RATE LIMITING ===
        if user:
            allowed, rate_message = rate_limiter.check(user.id)
            if not allowed:
                logger.warning(f"Rate limit excedido para user_id={user.id}")
                send_whatsapp_message(From, f"⏳ {rate_message}")
                return Response(
                    content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml"
                )

        if not user:
            # Número não cadastrado ou não verificado - enviar mensagem informativa
            logger.warning(f"Número não autorizado tentou acessar: {From}")
            send_whatsapp_message(
                From,
                "⚠️ *Número não autorizado*\n\n"
                "Para usar o WhatsApp AI Assistant, você precisa:\n\n"
                "1️⃣ Criar uma conta em nosso site\n"
                "2️⃣ Verificar seu email\n"
                "3️⃣ Cadastrar este número de WhatsApp\n\n"
                "Acesse: https://seu-dominio.com/register",
            )
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml"
            )

        # Atualizar informações do usuário
        update_user_interaction(db, user, profile_name=ProfileName)

        message_text = Body
        is_audio = False

        # === INPUT SANITIZATION ===
        if message_text:
            message_text = input_sanitizer.sanitize_message(message_text)
            if not input_sanitizer.is_safe(Body):
                logger.warning(f"Input suspeito detectado de user_id={user.id}")

        # Verificar se é mídia (áudio ou imagem)
        num_media = int(NumMedia) if NumMedia else 0
        is_image = False
        image_analysis = None

        if num_media > 0 and MediaContentType0:
            # ÁUDIO
            if MediaContentType0.startswith("audio/"):
                is_audio = True
                logger.info(f"Áudio recebido de {ProfileName or From}: {MediaUrl0}")

                # Transcrever áudio passando o content_type
                message_text = await transcribe_audio_from_url(MediaUrl0, MediaContentType0)
                if not message_text:
                    send_whatsapp_message(
                        From, "Desculpe, não consegui entender o áudio. Pode repetir ou enviar por texto?"
                    )
                    return Response(
                        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                        media_type="application/xml",
                    )
                # Sanitizar transcrição de áudio também
                message_text = input_sanitizer.sanitize_message(message_text)
                logger.info(f"Áudio transcrito: {message_text}")

            # IMAGEM
            elif MediaContentType0.startswith("image/"):
                is_image = True
                logger.info(f"📸 Imagem recebida de {ProfileName or From}: {MediaUrl0}")

                from app.services.vision_service import get_vision_service

                vision_service = get_vision_service()

                # Baixar imagem do Twilio (requer autenticação)
                auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                image_data = await vision_service.download_image(MediaUrl0, auth)

                if not image_data:
                    send_whatsapp_message(From, "Desculpe, não consegui baixar a imagem. Pode enviar novamente?")
                    return Response(
                        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                        media_type="application/xml",
                    )

                # Analisar imagem e registrar transações automaticamente
                response_text = await vision_service.analyze_financial_image(
                    image_data, user_name=user.name, db=db, user_id=user.id
                )

                # Salvar e enviar resposta da imagem
                save_whatsapp_message(db, user.id, f"[IMAGEM: {MediaContentType0}]", "incoming")
                save_whatsapp_message(db, user.id, response_text, "outgoing", ai_response=response_text)
                send_whatsapp_message(From, response_text)

                return Response(
                    content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml"
                )

        logger.info(f"Mensagem recebida de {ProfileName or From}: {message_text}")

        # Salvar mensagem recebida
        save_whatsapp_message(db, user.id, message_text, "incoming")

        # Debug: log do user_id sendo usado
        logger.info(f"Processando para user_id={user.id}, telefone={user.phone_number}")

        # Enviar indicador "digitando..." antes de processar
        if MessageSid:
            from app.services.whatsapp_service import WhatsAppService

            whatsapp_service = WhatsAppService(
                account_sid=settings.TWILIO_ACCOUNT_SID,
                auth_token=settings.TWILIO_AUTH_TOKEN,
                whatsapp_number=settings.TWILIO_WHATSAPP_NUMBER,
            )
            whatsapp_service.send_typing_indicator(MessageSid)

        # Processar com a IA (usando camada de migração v2/v3)
        # Env: IRIS_GRAPH_VERSION = "v2" | "v3"
        logger.info(f"[WEBHOOK] Processando com Graph {GRAPH_VERSION}")
        result = await process_message_v3(
            user_id=user.id,
            session_id=user.session_id,
            message=message_text,
            context={
                "user_name": user.name,
                "timezone": user.timezone or "America/Sao_Paulo",
                "source": "whatsapp",
                "phone_number": user.phone_number,
                "is_audio": is_audio,
            },
            db=db,
        )

        response_text = result.get("response", "Desculpe, não consegui processar sua mensagem.")
        next_action = result.get("next_action", "")
        entities = result.get("entities", {})

        # NOTA: O salvamento de entidades (finanças, lembretes, contatos, etc.)
        # é feito diretamente no graph_v2.py no _response_formatter_node.
        # NÃO duplicar salvamento aqui para evitar registros duplicados.

        # Salvar resposta
        save_whatsapp_message(db, user.id, response_text, "outgoing", ai_response=response_text)

        # Enviar resposta via WhatsApp
        send_whatsapp_message(From, response_text)

        # Retornar TwiML vazio (resposta já enviada via API)
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml"
        )

    except Exception as e:
        logger.error(f"[WEBHOOK] ❌ Erro crítico: {e}")
        import traceback

        logger.error(traceback.format_exc())

        # Enviar resposta de fallback para o usuário (nunca deixar sem resposta)
        try:
            fallback_message = (
                "Desculpe, tive um probleminha técnico agora. 😅\n"
                "Pode repetir o que você disse? Já estou me recuperando!"
            )

            # Tentar enviar mensagem de fallback via Twilio
            if "From" in dir() and From:
                send_whatsapp_message(From, fallback_message)
                logger.info(f"[WEBHOOK] Mensagem de fallback enviada para {From}")
        except Exception as fallback_error:
            logger.error(f"[WEBHOOK] Falha ao enviar fallback: {fallback_error}")

        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml"
        )


@router.get("/whatsapp")
async def whatsapp_webhook_verify():
    """Endpoint de verificação para o Twilio."""
    return {"status": "ok", "message": "WhatsApp webhook is active"}


@router.post("/whatsapp/status")
async def whatsapp_status_callback(
    MessageSid: str = Form(None),
    MessageStatus: str = Form(None),
    To: str = Form(None),
):
    """Callback para status de entrega das mensagens."""
    logger.info(f"Status update - SID: {MessageSid}, Status: {MessageStatus}, To: {To}")
    return {"status": "received"}
