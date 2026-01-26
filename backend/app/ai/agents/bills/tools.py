"""
Bills Tools - Ferramentas específicas do agente de faturas.

Estas tools são EXCLUSIVAS do BillsAgent.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class InvoiceData:
    """Dados extraídos de uma fatura."""
    vendor: str = ""
    amount: float = 0.0
    due_date: Optional[str] = None
    invoice_number: str = ""
    installment: Optional[str] = None  # "2/12" = parcela 2 de 12
    category: str = "Outros"
    barcode: Optional[str] = None
    confidence: float = 0.0
    raw_text: str = ""


def extract_invoice_data(text: str, source: str = "ocr") -> Dict[str, Any]:
    """
    Extrai dados de fatura de texto (OCR ou email).
    
    Args:
        text: Texto extraído do documento
        source: Origem do texto ("ocr", "pdf", "email")
    
    Returns:
        Dicionário com dados extraídos
    """
    logger.info(f"[BILLS] Extraindo dados de {source}, {len(text)} chars")
    
    result = {
        "vendor": "",
        "amount": 0.0,
        "due_date": None,
        "invoice_number": "",
        "installment": None,
        "category": "Outros",
        "barcode": None,
        "confidence": 0.0,
        "items": [],
    }
    
    text_lower = text.lower()
    
    # 1. Extrair valor total
    result["amount"], amount_confidence = _extract_amount(text)
    
    # 2. Extrair data de vencimento
    result["due_date"], date_confidence = _extract_due_date(text)
    
    # 3. Extrair fornecedor/empresa
    result["vendor"] = _extract_vendor(text)
    
    # 4. Extrair número da fatura
    result["invoice_number"] = _extract_invoice_number(text)
    
    # 5. Extrair parcela
    result["installment"] = _extract_installment(text)
    
    # 6. Extrair código de barras
    result["barcode"] = _extract_barcode(text)
    
    # 7. Detectar categoria
    result["category"] = _detect_category(text_lower, result["vendor"])
    
    # Calcular confidence geral
    confidences = [amount_confidence, date_confidence]
    if result["vendor"]:
        confidences.append(0.8)
    result["confidence"] = sum(confidences) / len(confidences) if confidences else 0.3
    
    logger.info(
        f"[BILLS] Extraído: {result['vendor']} | "
        f"R$ {result['amount']:.2f} | "
        f"Venc: {result['due_date']} | "
        f"Conf: {result['confidence']:.0%}"
    )
    
    return result


def _extract_amount(text: str) -> tuple[float, float]:
    """Extrai valor monetário do texto."""
    patterns = [
        r"total[:\s]+r?\$?\s*([\d.,]+)",
        r"valor[:\s]+r?\$?\s*([\d.,]+)",
        r"r\$\s*([\d.,]+)",
        r"valor\s+a\s+pagar[:\s]+r?\$?\s*([\d.,]+)",
        r"total\s+geral[:\s]+r?\$?\s*([\d.,]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try:
                value_str = match.group(1).replace(".", "").replace(",", ".")
                value = float(value_str)
                if 0.01 <= value <= 1000000:  # Sanidade
                    return value, 0.9
            except ValueError:
                continue
    
    # Fallback: procurar qualquer valor monetário
    all_values = re.findall(r"r?\$\s*([\d.,]+)", text.lower())
    if all_values:
        try:
            values = []
            for v in all_values:
                v_clean = v.replace(".", "").replace(",", ".")
                values.append(float(v_clean))
            # Pegar o maior valor como total
            max_value = max(v for v in values if 0.01 <= v <= 1000000)
            return max_value, 0.6
        except (ValueError, StopIteration):
            pass
    
    return 0.0, 0.0


def _extract_due_date(text: str) -> tuple[Optional[str], float]:
    """Extrai data de vencimento."""
    patterns = [
        r"vencimento[:\s]+([\d]{1,2}[/.-][\d]{1,2}[/.-][\d]{2,4})",
        r"venc[:\s]+([\d]{1,2}[/.-][\d]{1,2}[/.-][\d]{2,4})",
        r"data\s+de\s+vencimento[:\s]+([\d]{1,2}[/.-][\d]{1,2}[/.-][\d]{2,4})",
        r"pagar\s+at[ée][:\s]+([\d]{1,2}[/.-][\d]{1,2}[/.-][\d]{2,4})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            date_str = match.group(1)
            normalized = _normalize_date(date_str)
            if normalized:
                return normalized, 0.9
    
    # Fallback: procurar qualquer data
    date_pattern = r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})"
    dates = re.findall(date_pattern, text)
    if dates:
        normalized = _normalize_date(dates[0])
        if normalized:
            return normalized, 0.5
    
    return None, 0.0


def _normalize_date(date_str: str) -> Optional[str]:
    """Normaliza data para YYYY-MM-DD."""
    date_str = date_str.replace("-", "/").replace(".", "/")
    parts = date_str.split("/")
    
    if len(parts) != 3:
        return None
    
    try:
        day, month, year = parts
        day = int(day)
        month = int(month)
        year = int(year)
        
        if year < 100:
            year += 2000
        
        if not (1 <= day <= 31 and 1 <= month <= 12 and 2020 <= year <= 2030):
            return None
        
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
        return None


def _extract_vendor(text: str) -> str:
    """Extrai nome do fornecedor/empresa."""
    # Padrões comuns de empresas brasileiras
    vendors = {
        "netflix": "Netflix",
        "spotify": "Spotify",
        "amazon": "Amazon",
        "uber": "Uber",
        "ifood": "iFood",
        "nubank": "Nubank",
        "itau": "Itaú",
        "bradesco": "Bradesco",
        "santander": "Santander",
        "vivo": "Vivo",
        "claro": "Claro",
        "tim": "TIM",
        "oi": "Oi",
        "enel": "Enel",
        "cemig": "Cemig",
        "sabesp": "Sabesp",
        "copasa": "Copasa",
        "energisa": "Energisa",
        "cpfl": "CPFL",
        "light": "Light",
        "net": "Net/Claro",
        "sky": "Sky",
    }
    
    text_lower = text.lower()
    for key, name in vendors.items():
        if key in text_lower:
            return name
    
    # Tentar extrair CNPJ e nome da empresa
    cnpj_pattern = r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})"
    if re.search(cnpj_pattern, text):
        # Procurar nome antes do CNPJ
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if re.search(cnpj_pattern, line) and i > 0:
                prev_line = lines[i-1].strip()
                if prev_line and len(prev_line) < 50:
                    return prev_line.title()
    
    return ""


def _extract_invoice_number(text: str) -> str:
    """Extrai número da fatura/nota."""
    patterns = [
        r"n[úu]mero[:\s]*([\d]+)",
        r"nota[:\s]*([\d]+)",
        r"fatura[:\s]*([\d]+)",
        r"nf[:\s]*([\d]+)",
        r"n[°o][:\s]*([\d]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1)
    
    return ""


def _extract_installment(text: str) -> Optional[str]:
    """Extrai informação de parcela."""
    patterns = [
        r"parcela[:\s]*(\d+)\s*(?:de|/)\s*(\d+)",
        r"(\d+)\s*/\s*(\d+)\s*parcela",
        r"(\d+)x",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            groups = match.groups()
            if len(groups) == 2:
                return f"{groups[0]}/{groups[1]}"
            elif len(groups) == 1:
                return f"1/{groups[0]}"
    
    return None


def _extract_barcode(text: str) -> Optional[str]:
    """Extrai código de barras."""
    # Boleto bancário: 47 ou 48 dígitos
    barcode_pattern = r"(\d{5}\.\d{5}\s*\d{5}\.\d{6}\s*\d{5}\.\d{6}\s*\d\s*\d{14})"
    match = re.search(barcode_pattern, text)
    if match:
        return match.group(1).replace(" ", "").replace(".", "")
    
    # Código de barras numérico simples
    numeric_pattern = r"(\d{44,48})"
    match = re.search(numeric_pattern, text.replace(" ", ""))
    if match:
        code = match.group(1)
        if len(code) in [44, 47, 48]:
            return code
    
    return None


def _detect_category(text_lower: str, vendor: str) -> str:
    """Detecta categoria da fatura."""
    categories = {
        "Energia": ["energia", "luz", "enel", "cemig", "cpfl", "light", "energisa", "kwh"],
        "Água": ["água", "agua", "sabesp", "copasa", "saneamento"],
        "Internet/TV": ["internet", "banda larga", "net", "claro tv", "sky", "vivo fibra"],
        "Telefone": ["telefone", "celular", "móvel", "vivo", "claro", "tim", "oi"],
        "Streaming": ["netflix", "spotify", "disney", "hbo", "prime video", "youtube"],
        "Alimentação": ["ifood", "rappi", "uber eats", "restaurante", "mercado"],
        "Transporte": ["uber", "99", "cabify", "combustível", "estacionamento"],
        "Saúde": ["farmácia", "drogaria", "hospital", "clínica", "plano de saúde"],
        "Educação": ["escola", "faculdade", "curso", "mensalidade"],
        "Moradia": ["aluguel", "condomínio", "iptu", "seguro residencial"],
        "Cartão": ["cartão", "fatura do cartão", "nubank", "inter", "c6"],
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text_lower or keyword in vendor.lower():
                return category
    
    return "Outros"


def create_financial_reminder(
    db: Any,
    user_id: int,
    invoice_data: Dict[str, Any],
    auto_create: bool = False,
) -> Dict[str, Any]:
    """
    Cria lembrete financeiro a partir dos dados da fatura.
    
    Args:
        db: Sessão do banco
        user_id: ID do usuário
        invoice_data: Dados extraídos da fatura
        auto_create: Se True, cria automaticamente; se False, apenas sugere
    
    Returns:
        Resultado da operação
    """
    from app.services.reminder_service import ReminderService
    
    vendor = invoice_data.get("vendor", "Fatura")
    amount = invoice_data.get("amount", 0)
    due_date = invoice_data.get("due_date")
    category = invoice_data.get("category", "Contas")
    
    title = f"💰 Pagar {vendor}"
    if amount > 0:
        title += f" - R$ {amount:,.2f}"
    
    description = f"Categoria: {category}"
    if invoice_data.get("installment"):
        description += f"\nParcela: {invoice_data['installment']}"
    if invoice_data.get("barcode"):
        description += f"\nCódigo: {invoice_data['barcode'][:20]}..."
    
    reminder_data = {
        "title": title,
        "description": description,
        "scheduled_time": due_date,
        "category": "financial",
    }
    
    if not auto_create:
        return {
            "action": "suggest_reminder",
            "reminder": reminder_data,
            "message": f"Criar lembrete para pagar {vendor} em {due_date}?",
            "requires_confirmation": True,
        }
    
    try:
        service = ReminderService(db)
        service.create_from_entities(user_id, reminder_data)
        
        return {
            "action": "created_reminder",
            "reminder": reminder_data,
            "success": True,
            "message": f"✅ Lembrete criado: {title}",
        }
    except Exception as e:
        logger.error(f"[BILLS] Erro ao criar lembrete: {e}")
        return {
            "action": "error",
            "success": False,
            "error": str(e),
        }
