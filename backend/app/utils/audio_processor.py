import logging
from pathlib import Path
from typing import Optional

import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Processador de áudio para transcrição usando Gemini."""

    def __init__(self, api_key: str):
        """
        Inicializa o processador de áudio.

        Args:
            api_key: API Key do Google Gemini
        """
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def transcribe_audio(self, audio_path: Path) -> Optional[str]:
        """
        Transcreve um arquivo de áudio para texto.

        Args:
            audio_path: Caminho para o arquivo de áudio

        Returns:
            Transcrição do áudio ou None em caso de erro
        """
        try:
            if not self.validate_audio(audio_path):
                logger.error(f"Áudio inválido: {audio_path}")
                return None

            with open(audio_path, "rb") as f:
                audio_data = f.read()

            mime_type = self._get_mime_type(audio_path)

            response = self.model.generate_content(
                [
                    "Transcreva este áudio em português brasileiro. "
                    "Retorne apenas a transcrição, sem comentários adicionais:",
                    {"mime_type": mime_type, "data": audio_data},
                ]
            )

            transcription = response.text.strip()
            logger.info(f"Áudio transcrito com sucesso: {len(transcription)} caracteres")
            return transcription

        except Exception as e:
            logger.error(f"Erro na transcrição do áudio: {e}")
            return None

    def validate_audio(self, audio_path: Path) -> bool:
        """
        Valida formato e tamanho do arquivo de áudio.

        Args:
            audio_path: Caminho para o arquivo

        Returns:
            True se válido, False caso contrário
        """
        if not audio_path.exists():
            logger.error(f"Arquivo não encontrado: {audio_path}")
            return False

        suffix = audio_path.suffix.lower()
        if suffix not in settings.SUPPORTED_AUDIO_FORMATS:
            logger.error(f"Formato não suportado: {suffix}")
            return False

        size_mb = audio_path.stat().st_size / (1024 * 1024)
        if size_mb > settings.MAX_AUDIO_SIZE_MB:
            logger.error(f"Arquivo muito grande: {size_mb:.2f}MB (max: {settings.MAX_AUDIO_SIZE_MB}MB)")
            return False

        return True

    def _get_mime_type(self, audio_path: Path) -> str:
        """Retorna o MIME type baseado na extensão do arquivo."""
        mime_types = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".m4a": "audio/mp4",
            ".opus": "audio/opus",
        }
        return mime_types.get(audio_path.suffix.lower(), "audio/ogg")
