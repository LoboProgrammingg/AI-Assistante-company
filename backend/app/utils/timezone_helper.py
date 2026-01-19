from datetime import datetime, timedelta, timezone
from typing import Optional
import pytz


def utc_now() -> datetime:
    """Retorna datetime atual em UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


def convert_to_user_timezone(
    dt: datetime,
    user_timezone: str = "America/Sao_Paulo"
) -> datetime:
    """
    Converte um datetime UTC para o timezone do usuário.
    
    Args:
        dt: Datetime em UTC
        user_timezone: Timezone do usuário
        
    Returns:
        Datetime no timezone do usuário
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    
    user_tz = pytz.timezone(user_timezone)
    return dt.astimezone(user_tz)


def convert_to_utc(
    dt: datetime,
    user_timezone: str = "America/Sao_Paulo"
) -> datetime:
    """
    Converte um datetime do timezone do usuário para UTC.
    
    Args:
        dt: Datetime no timezone do usuário
        user_timezone: Timezone do usuário
        
    Returns:
        Datetime em UTC
    """
    user_tz = pytz.timezone(user_timezone)
    
    if dt.tzinfo is None:
        dt = user_tz.localize(dt)
    
    return dt.astimezone(pytz.UTC)


def get_current_time_for_user(user_timezone: str = "America/Sao_Paulo") -> datetime:
    """
    Retorna o horário atual no timezone do usuário.
    
    Args:
        user_timezone: Timezone do usuário
        
    Returns:
        Datetime atual no timezone do usuário
    """
    now_utc = datetime.now(pytz.UTC)
    return convert_to_user_timezone(now_utc, user_timezone)


def format_time_for_user(
    dt: datetime,
    user_timezone: str = "America/Sao_Paulo",
    format_str: str = "%H:%M"
) -> str:
    """
    Formata um datetime para exibição ao usuário.
    
    Args:
        dt: Datetime a formatar
        user_timezone: Timezone do usuário
        format_str: Formato de saída
        
    Returns:
        String formatada
    """
    user_dt = convert_to_user_timezone(dt, user_timezone)
    return user_dt.strftime(format_str)


def format_date_for_user(
    dt: datetime,
    user_timezone: str = "America/Sao_Paulo",
    format_str: str = "%d/%m/%Y"
) -> str:
    """
    Formata uma data para exibição ao usuário.
    
    Args:
        dt: Datetime a formatar
        user_timezone: Timezone do usuário
        format_str: Formato de saída
        
    Returns:
        String formatada
    """
    user_dt = convert_to_user_timezone(dt, user_timezone)
    return user_dt.strftime(format_str)


def parse_natural_datetime(
    text: str,
    user_timezone: str = "America/Sao_Paulo",
    reference_time: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Interpreta referências de tempo em linguagem natural.
    
    Args:
        text: Texto com referência temporal
        user_timezone: Timezone do usuário
        reference_time: Tempo de referência (padrão: agora)
        
    Returns:
        Datetime interpretado ou None
    """
    if reference_time is None:
        reference_time = get_current_time_for_user(user_timezone)
    
    text_lower = text.lower().strip()
    
    if "amanhã" in text_lower or "amanha" in text_lower:
        return reference_time + timedelta(days=1)
    
    if "hoje" in text_lower:
        return reference_time
    
    if "próxima semana" in text_lower or "proxima semana" in text_lower:
        return reference_time + timedelta(weeks=1)
    
    if "próximo mês" in text_lower or "proximo mes" in text_lower:
        return reference_time + timedelta(days=30)
    
    return None


def is_valid_timezone(timezone_str: str) -> bool:
    """
    Verifica se um timezone é válido.
    
    Args:
        timezone_str: String do timezone
        
    Returns:
        True se válido, False caso contrário
    """
    try:
        pytz.timezone(timezone_str)
        return True
    except pytz.UnknownTimeZoneError:
        return False


def get_brazil_timezones() -> list:
    """Retorna lista de timezones do Brasil."""
    return [
        "America/Sao_Paulo",
        "America/Rio_Branco",
        "America/Manaus",
        "America/Cuiaba",
        "America/Fortaleza",
        "America/Recife",
        "America/Bahia",
        "America/Belem",
        "America/Noronha",
    ]
