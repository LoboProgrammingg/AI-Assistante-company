"""
Validador de dados para IRIS.
Previne alucinações verificando dados contra fontes reais.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado de uma validação."""

    is_valid: bool
    field: str
    message: str
    corrected_value: Any = None


class DataValidator:
    """
    Validador de dados extraídos pelo LLM.

    Previne alucinações verificando:
    - Datas e horários válidos
    - Valores financeiros razoáveis
    - Dados existentes no banco
    - Formatos esperados
    """

    # Limites razoáveis para valores financeiros
    MAX_TRANSACTION_AMOUNT = 1_000_000  # R$ 1 milhão
    MIN_TRANSACTION_AMOUNT = 0.01

    # Limites de datas
    MAX_FUTURE_DAYS = 365 * 2  # 2 anos no futuro
    MAX_PAST_DAYS = 365 * 5  # 5 anos no passado

    def __init__(self, db=None):
        self.db = db

    def validate_finance_data(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Valida dados financeiros extraídos."""
        results = []

        # Validar amount
        amount = data.get("amount")
        if amount is not None:
            result = self._validate_amount(amount)
            if not result.is_valid:
                results.append(result)

        # Validar categoria
        category = data.get("category")
        if category:
            result = self._validate_category(category)
            if not result.is_valid:
                results.append(result)

        # Validar tipo
        trans_type = data.get("type")
        if trans_type:
            result = self._validate_transaction_type(trans_type)
            if not result.is_valid:
                results.append(result)

        return results

    def validate_reminder_data(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Valida dados de lembrete extraídos."""
        results = []

        # Validar scheduled_time
        scheduled_time = data.get("scheduled_time")
        if scheduled_time:
            result = self._validate_datetime(scheduled_time, "scheduled_time")
            if not result.is_valid:
                results.append(result)

        # Validar title
        title = data.get("title")
        if title:
            result = self._validate_text_field(title, "title", max_length=200)
            if not result.is_valid:
                results.append(result)

        return results

    def validate_meeting_data(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Valida dados de reunião extraídos."""
        results = []

        # Validar scheduled_time
        scheduled_time = data.get("scheduled_time")
        if scheduled_time:
            result = self._validate_datetime(scheduled_time, "scheduled_time")
            if not result.is_valid:
                results.append(result)

        # Validar participants
        participants = data.get("participants", [])
        if participants and isinstance(participants, list):
            for i, p in enumerate(participants):
                if isinstance(p, str) and len(p) > 100:
                    results.append(
                        ValidationResult(
                            is_valid=False, field=f"participants[{i}]", message="Nome de participante muito longo"
                        )
                    )

        return results

    def validate_contact_data(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Valida dados de contato extraídos."""
        results = []

        # Validar telefone
        phone = data.get("phone")
        if phone:
            result = self._validate_phone(phone)
            if not result.is_valid:
                results.append(result)

        # Validar email
        email = data.get("email")
        if email:
            result = self._validate_email(email)
            if not result.is_valid:
                results.append(result)

        # Validar nome
        name = data.get("name")
        if name:
            result = self._validate_text_field(name, "name", max_length=100)
            if not result.is_valid:
                results.append(result)

        return results

    def _validate_amount(self, amount: Any) -> ValidationResult:
        """Valida valor monetário."""
        try:
            value = float(amount)

            if value < self.MIN_TRANSACTION_AMOUNT:
                return ValidationResult(
                    is_valid=False,
                    field="amount",
                    message=f"Valor muito baixo: {value}",
                    corrected_value=self.MIN_TRANSACTION_AMOUNT,
                )

            if value > self.MAX_TRANSACTION_AMOUNT:
                return ValidationResult(
                    is_valid=False,
                    field="amount",
                    message=f"Valor suspeitamente alto: {value}. Confirme o valor.",
                )

            return ValidationResult(is_valid=True, field="amount", message="OK")

        except (ValueError, TypeError):
            return ValidationResult(is_valid=False, field="amount", message=f"Valor inválido: {amount}")

    def _validate_category(self, category: str) -> ValidationResult:
        """Valida categoria financeira."""
        valid_categories = {
            "Alimentação",
            "Transporte",
            "Moradia",
            "Saúde",
            "Educação",
            "Lazer",
            "Vestuário",
            "Tecnologia",
            "Serviços",
            "Outros",
            "Salário",
            "Freelance",
            "Investimentos",
            "Vendas",
            "Outros Receitas",
        }

        # Normalizar para comparação
        category_normalized = category.strip().title()

        if category_normalized not in valid_categories:
            # Tentar encontrar categoria similar
            for valid in valid_categories:
                if category_normalized.lower() in valid.lower():
                    return ValidationResult(
                        is_valid=True, field="category", message="Categoria corrigida", corrected_value=valid
                    )

            return ValidationResult(
                is_valid=False,
                field="category",
                message=f"Categoria desconhecida: {category}",
                corrected_value="Outros",
            )

        return ValidationResult(is_valid=True, field="category", message="OK")

    def _validate_transaction_type(self, trans_type: str) -> ValidationResult:
        """Valida tipo de transação."""
        valid_types = {"expense", "income", "despesa", "receita"}

        if trans_type.lower() not in valid_types:
            return ValidationResult(
                is_valid=False, field="type", message=f"Tipo inválido: {trans_type}", corrected_value="expense"
            )

        return ValidationResult(is_valid=True, field="type", message="OK")

    def _validate_datetime(self, dt_value: Any, field: str) -> ValidationResult:
        """Valida data/hora."""
        now = datetime.now()

        try:
            if isinstance(dt_value, str):
                # Tentar múltiplos formatos
                formats = [
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%d/%m/%Y %H:%M",
                    "%d/%m/%Y",
                ]

                parsed = None
                for fmt in formats:
                    try:
                        parsed = datetime.strptime(dt_value, fmt)
                        break
                    except ValueError:
                        continue

                if not parsed:
                    return ValidationResult(
                        is_valid=False, field=field, message=f"Formato de data inválido: {dt_value}"
                    )

                dt_value = parsed

            elif isinstance(dt_value, datetime):
                pass
            else:
                return ValidationResult(is_valid=False, field=field, message=f"Tipo de data inválido: {type(dt_value)}")

            # Verificar limites
            min_date = now - timedelta(days=self.MAX_PAST_DAYS)
            max_date = now + timedelta(days=self.MAX_FUTURE_DAYS)

            if dt_value < min_date:
                return ValidationResult(is_valid=False, field=field, message=f"Data muito antiga: {dt_value}")

            if dt_value > max_date:
                return ValidationResult(is_valid=False, field=field, message=f"Data muito no futuro: {dt_value}")

            return ValidationResult(is_valid=True, field=field, message="OK")

        except Exception as e:
            return ValidationResult(is_valid=False, field=field, message=f"Erro ao validar data: {e}")

    def _validate_phone(self, phone: str) -> ValidationResult:
        """Valida número de telefone."""
        # Remover formatação
        clean = re.sub(r"[^\d+]", "", phone)

        if len(clean) < 8:
            return ValidationResult(is_valid=False, field="phone", message="Telefone muito curto")

        if len(clean) > 15:
            return ValidationResult(is_valid=False, field="phone", message="Telefone muito longo")

        return ValidationResult(is_valid=True, field="phone", message="OK")

    def _validate_email(self, email: str) -> ValidationResult:
        """Valida email."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if not re.match(pattern, email):
            return ValidationResult(is_valid=False, field="email", message="Formato de email inválido")

        return ValidationResult(is_valid=True, field="email", message="OK")

    def _validate_text_field(self, text: str, field: str, max_length: int = 500) -> ValidationResult:
        """Valida campo de texto genérico."""
        if len(text) > max_length:
            return ValidationResult(
                is_valid=False,
                field=field,
                message=f"Texto muito longo ({len(text)} > {max_length})",
                corrected_value=text[:max_length],
            )

        return ValidationResult(is_valid=True, field=field, message="OK")

    def validate_against_db(self, entity_type: str, data: Dict[str, Any], user_id: int) -> List[ValidationResult]:
        """
        Valida dados contra o banco para evitar alucinações.

        Verifica se IDs referenciados existem, etc.
        """
        if not self.db:
            return []

        results = []

        # Verificar referências a IDs existentes
        if "reminder_id" in data:
            result = self._check_reminder_exists(data["reminder_id"], user_id)
            if not result.is_valid:
                results.append(result)

        if "transaction_id" in data:
            result = self._check_transaction_exists(data["transaction_id"], user_id)
            if not result.is_valid:
                results.append(result)

        return results

    def _check_reminder_exists(self, reminder_id: int, user_id: int) -> ValidationResult:
        """Verifica se lembrete existe."""
        try:
            from app.models import Reminder

            exists = self.db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == user_id).first()

            if not exists:
                return ValidationResult(
                    is_valid=False, field="reminder_id", message=f"Lembrete #{reminder_id} não encontrado"
                )

            return ValidationResult(is_valid=True, field="reminder_id", message="OK")
        except Exception as e:
            logger.error(f"Erro ao verificar lembrete: {e}")
            return ValidationResult(is_valid=True, field="reminder_id", message="Não verificado")

    def _check_transaction_exists(self, transaction_id: int, user_id: int) -> ValidationResult:
        """Verifica se transação existe."""
        try:
            from app.models import FinancialTransaction

            exists = (
                self.db.query(FinancialTransaction)
                .filter(FinancialTransaction.id == transaction_id, FinancialTransaction.user_id == user_id)
                .first()
            )

            if not exists:
                return ValidationResult(
                    is_valid=False, field="transaction_id", message=f"Transação #{transaction_id} não encontrada"
                )

            return ValidationResult(is_valid=True, field="transaction_id", message="OK")
        except Exception as e:
            logger.error(f"Erro ao verificar transação: {e}")
            return ValidationResult(is_valid=True, field="transaction_id", message="Não verificado")


def validate_entities(
    entity_type: str, data: Dict[str, Any], db=None, user_id: int = None
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Função utilitária para validar entidades extraídas.

    Returns:
        Tuple[bool, List[str], Dict[str, Any]]: (is_valid, errors, corrected_data)
    """
    validator = DataValidator(db)
    errors = []
    corrected_data = data.copy()

    # Validar por tipo
    validators = {
        "finance": validator.validate_finance_data,
        "reminder": validator.validate_reminder_data,
        "meeting": validator.validate_meeting_data,
        "contact": validator.validate_contact_data,
    }

    validate_fn = validators.get(entity_type)
    if validate_fn:
        results = validate_fn(data)

        for result in results:
            if not result.is_valid:
                errors.append(result.message)
                if result.corrected_value is not None:
                    corrected_data[result.field] = result.corrected_value

    # Validar contra banco se possível
    if db and user_id:
        db_results = validator.validate_against_db(entity_type, data, user_id)
        for result in db_results:
            if not result.is_valid:
                errors.append(result.message)

    is_valid = len(errors) == 0
    return is_valid, errors, corrected_data
