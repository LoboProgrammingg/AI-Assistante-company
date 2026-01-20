"""
Constantes para o agente de lembretes.
"""

import re
from typing import Dict, List


class ReminderConstants:
    """Constantes utilizadas pelo ReminderAgent."""

    # Tipos de recorrência disponíveis
    RECURRENCE_TYPES: List[str] = [
        "once",  # Único
        "daily",  # Diário
        "weekdays",  # Segunda a sexta
        "weekends",  # Sábado e domingo
        "weekly",  # Semanal
        "monthly",  # Mensal
        "yearly",  # Anual
    ]

    # Mapeamento de opções numéricas para minutos de antecedência
    TIME_OPTIONS: Dict[str, int] = {
        "1": 0,  # Na hora
        "2": 5,  # 5 minutos
        "3": 15,  # 15 minutos
        "4": 30,  # 30 minutos
        "5": 60,  # 1 hora
    }

    # Keywords para identificar pedidos de deleção
    DELETE_KEYWORDS: List[str] = [
        "cancele",
        "cancela",
        "cancelar",
        "delete",
        "deletar",
        "remova",
        "remover",
        "apague",
        "apagar",
        "exclua",
        "excluir",
    ]

    # Keywords para identificar respostas sobre tempo
    TIME_KEYWORDS: List[str] = ["min", "minuto", "hora", "hr", "agora", "na hora", "antes", "exato", "momento", "sim"]

    @classmethod
    def is_delete_request(cls, message: str) -> bool:
        """
        Verifica se a mensagem é um pedido de deleção.

        Args:
            message: Mensagem do usuário
        """
        message_lower = message.lower()
        return any(kw in message_lower for kw in cls.DELETE_KEYWORDS)

    @classmethod
    def is_time_response(cls, message: str) -> bool:
        """
        Verifica se a mensagem é uma resposta sobre tempo de antecedência.

        Args:
            message: Mensagem do usuário
        """
        message_lower = message.lower().strip()

        # Opções numéricas do menu (1-5)
        if message_lower in ["1", "2", "3", "4", "5"]:
            return True

        # Palavras-chave de tempo
        if any(kw in message_lower for kw in cls.TIME_KEYWORDS):
            return True

        # Número seguido de letra (ex: "30m", "1h")
        if re.match(r"^\d+\s*[mh]", message_lower):
            return True

        # Apenas número (ex: "30", "15")
        if message_lower.isdigit():
            return True

        return False

    @classmethod
    def parse_remind_time(cls, message: str) -> int:
        """
        Extrai minutos de antecedência da mensagem.

        Args:
            message: Resposta do usuário sobre tempo

        Returns:
            Minutos de antecedência
        """
        message_lower = message.lower().strip()

        # Se é apenas um número de 1-5, usar o mapa de opções
        if message_lower in cls.TIME_OPTIONS:
            return cls.TIME_OPTIONS[message_lower]

        # "na hora" ou "0" = sem antecedência
        if "na hora" in message_lower or message_lower == "0":
            return 0

        # Extrair número da mensagem
        numbers = re.findall(r"(\d+)", message_lower)
        if not numbers:
            return 15  # Default: 15 minutos

        value = int(numbers[0])

        # Verificar se é hora
        if "hora" in message_lower or "hr" in message_lower:
            return value * 60

        # Se só tem "h" após o número, também é hora (ex: "1h", "2h")
        if re.search(r"\d+\s*h\b", message_lower):
            return value * 60

        # Qualquer outro valor numérico = minutos
        return value

    @classmethod
    def format_remind_time(cls, minutes: int) -> str:
        """
        Formata minutos em texto legível.

        Args:
            minutes: Minutos de antecedência

        Returns:
            Texto formatado
        """
        if minutes >= 60:
            hours = minutes // 60
            return f"{hours} hora" if hours == 1 else f"{hours} horas"
        elif minutes > 0:
            return f"{minutes} minutos"
        else:
            return "no horário exato"
