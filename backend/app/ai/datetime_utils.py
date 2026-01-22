"""
Utilitários de data/hora para o sistema IRIS.

Centraliza todas as funções relacionadas a timezone e formatação de data/hora.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

# Timezone padrão: Cuiabá-MT (UTC-4)
TIMEZONE_DEFAULT = ZoneInfo("America/Cuiaba")


def get_current_datetime() -> datetime:
    """Retorna data/hora atual no timezone de Cuiabá-MT."""
    return datetime.now(TIMEZONE_DEFAULT)


def get_datetime_context() -> str:
    """Retorna string formatada com data/hora atual para contexto da IA."""
    now = get_current_datetime()
    dias_semana = [
        "segunda-feira",
        "terça-feira",
        "quarta-feira",
        "quinta-feira",
        "sexta-feira",
        "sábado",
        "domingo",
    ]
    meses = [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ]

    dia_semana = dias_semana[now.weekday()]
    mes = meses[now.month - 1]

    return f"Hoje é {dia_semana}, {now.day} de {mes} de {now.year}. Horário atual: {now.strftime('%H:%M')} (Cuiabá-MT)."
