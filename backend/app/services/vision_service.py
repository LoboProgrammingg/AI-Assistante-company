"""
Serviço de Visão Computacional usando Google Gemini.

Processa imagens para:
- Extratos bancários
- Notas fiscais
- Comprovantes de pagamento
- Prints de transações
"""

import base64
import logging
import tempfile
from typing import Any, Dict, Optional

import google.generativeai as genai
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class VisionService:
    """Serviço para análise de imagens com Gemini Vision."""

    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        # Usar modelo do config (gemini-2.5-flash suporta visão)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def download_image(self, url: str, auth: tuple = None) -> Optional[bytes]:
        """Baixa imagem de uma URL."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, auth=auth, follow_redirects=True)
                if response.status_code == 200:
                    return response.content
                logger.error(f"Erro ao baixar imagem: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Erro ao baixar imagem: {e}")
            return None

    async def analyze_image(self, image_data: bytes, user_context: str = "") -> Dict[str, Any]:
        """
        Analisa uma imagem e extrai informações relevantes.
        
        Args:
            image_data: Bytes da imagem
            user_context: Contexto adicional do usuário
            
        Returns:
            Dict com análise estruturada
        """
        try:
            # Salvar temporariamente para upload
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(image_data)
                temp_path = f.name

            # Upload para Gemini
            image_file = genai.upload_file(temp_path)

            # Prompt especializado para análise financeira
            prompt = f"""Analise esta imagem e extraia todas as informações relevantes.

{user_context}

TIPOS DE IMAGEM QUE VOCÊ PODE ENCONTRAR:
1. EXTRATO BANCÁRIO: Extraia transações, saldos, datas
2. NOTA FISCAL: Extraia valor total, itens, data, CNPJ
3. COMPROVANTE DE PAGAMENTO: Extraia valor, destinatário, data
4. PIX/TRANSFERÊNCIA: Extraia valor, nome do destinatário/remetente, data
5. CUPOM FISCAL: Extraia itens, valores, total
6. PRINT DE APP BANCÁRIO: Extraia saldo, transações visíveis
7. OUTROS: Descreva o que vê na imagem

RETORNE UM JSON ESTRUTURADO com os seguintes campos:
{{
    "tipo_imagem": "extrato|nota_fiscal|comprovante|pix|cupom|app_bancario|outro",
    "descricao": "Descrição breve do que a imagem mostra",
    "transacoes": [
        {{
            "tipo": "entrada|saida",
            "valor": 100.00,
            "descricao": "Descrição da transação",
            "data": "2026-01-22",
            "categoria_sugerida": "alimentacao|transporte|moradia|lazer|saude|educacao|trabalho|outros"
        }}
    ],
    "saldo_visivel": 1000.00,
    "total_entradas": 0.00,
    "total_saidas": 0.00,
    "observacoes": "Qualquer informação adicional relevante",
    "confianca": "alta|media|baixa"
}}

Se não conseguir identificar valores específicos, use null.
Se a imagem não for relacionada a finanças, retorne tipo_imagem="outro" com descrição.
RETORNE APENAS O JSON, sem markdown ou explicações."""

            result = self.model.generate_content([prompt, image_file])
            
            # Limpar arquivo temporário
            import os
            os.unlink(temp_path)

            # Parsear resposta
            response_text = result.text.strip()
            
            # Remover marcadores de código se presentes
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            import json
            try:
                analysis = json.loads(response_text)
                logger.info(f"[VISION] Imagem analisada: {analysis.get('tipo_imagem')} ({analysis.get('confianca')})")
                return {
                    "success": True,
                    "analysis": analysis
                }
            except json.JSONDecodeError:
                # Se não conseguiu parsear JSON, retorna descrição textual
                logger.warning("[VISION] Resposta não é JSON válido, retornando texto")
                return {
                    "success": True,
                    "analysis": {
                        "tipo_imagem": "outro",
                        "descricao": response_text,
                        "transacoes": [],
                        "confianca": "baixa"
                    }
                }

        except Exception as e:
            logger.error(f"[VISION] Erro ao analisar imagem: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def analyze_financial_image(self, image_data: bytes, user_name: str = "", db=None, user_id: int = None) -> str:
        """
        Analisa imagem financeira, registra transações automaticamente e retorna resposta.
        
        Args:
            image_data: Bytes da imagem
            user_name: Nome do usuário para personalização
            db: Sessão do banco para registrar transações
            user_id: ID do usuário para registrar transações
            
        Returns:
            Resposta humanizada sobre a imagem
        """
        user_context = f"O usuário se chama {user_name}." if user_name else ""
        result = await self.analyze_image(image_data, user_context)
        
        if not result.get("success"):
            return "Desculpe, não consegui analisar a imagem. Pode tentar enviar novamente?"
        
        analysis = result.get("analysis", {})
        tipo = analysis.get("tipo_imagem", "outro")
        transacoes = analysis.get("transacoes", [])
        
        # Nome curto do usuário (primeiro nome)
        primeiro_nome = user_name.split()[0] if user_name else ""
        
        if tipo == "outro":
            descricao = analysis.get("descricao", "")
            return f"📷 {descricao}" if descricao else "📷 Imagem analisada!"
        
        # Registrar transações automaticamente se tiver db e user_id
        registradas = []
        if transacoes and db and user_id:
            registradas = await self._registrar_transacoes(db, user_id, transacoes)
        
        # Resposta simplificada
        parts = []
        
        # Emoji e tipo
        tipo_emoji = {"extrato": "📊", "nota_fiscal": "🧾", "comprovante": "✅", "pix": "💸", "cupom": "🛒", "app_bancario": "📱"}
        emoji = tipo_emoji.get(tipo, "📷")
        
        if registradas:
            # Transações foram registradas automaticamente
            if len(registradas) == 1:
                t = registradas[0]
                tipo_str = "receita" if t["type"] == "income" else "gasto"
                parts.append(f"{emoji} {primeiro_nome}, registrei seu {tipo_str}:")
                parts.append(f"� *R$ {t['amount']:.2f}* - {t['description']}")
            else:
                parts.append(f"{emoji} {primeiro_nome}, registrei {len(registradas)} transações:")
                for t in registradas[:3]:
                    tipo_emoji_t = "📥" if t["type"] == "income" else "📤"
                    parts.append(f"{tipo_emoji_t} R$ {t['amount']:.2f} - {t['description']}")
                if len(registradas) > 3:
                    parts.append(f"... e mais {len(registradas) - 3}")
        elif transacoes:
            # Transações identificadas mas não registradas (sem db)
            if len(transacoes) == 1:
                t = transacoes[0]
                valor = t.get("valor", 0)
                desc = t.get("descricao", "Transação")
                parts.append(f"{emoji} Identifiquei: *R$ {valor:.2f}* - {desc}")
            else:
                parts.append(f"{emoji} Identifiquei {len(transacoes)} transações")
                for t in transacoes[:3]:
                    valor = t.get("valor", 0)
                    desc = t.get("descricao", "")
                    parts.append(f"• R$ {valor:.2f} - {desc}")
        else:
            parts.append(f"{emoji} Imagem analisada, mas não encontrei transações para registrar.")
        
        return "\n".join(parts)

    async def _registrar_transacoes(self, db, user_id: int, transacoes: list) -> list:
        """Registra transações no banco de dados."""
        from app.services.finance_service import FinanceService
        from app.schemas.finance import FinanceCreate, FinanceTypeEnum
        from datetime import date
        
        registradas = []
        finance_service = FinanceService(db)
        
        for t in transacoes:
            try:
                descricao = t.get("descricao", "Transação da imagem")
                tipo = FinanceTypeEnum.EXPENSE if t.get("tipo") == "saida" else FinanceTypeEnum.INCOME
                
                # Criar schema de transação
                finance_data = FinanceCreate(
                    type=tipo,
                    amount=t.get("valor", 0),
                    description=descricao,
                    transaction_date=date.today(),
                )
                
                # Registrar transação
                finance = finance_service.create(user_id=user_id, data=finance_data)
                
                if finance:
                    registradas.append({
                        "type": finance.type,
                        "amount": finance.amount,
                        "description": finance.description,
                    })
                    logger.info(f"[VISION] Transação registrada: R${finance.amount} - {finance.description}")
            except Exception as e:
                logger.error(f"[VISION] Erro ao registrar transação: {e}")
        
        return registradas

    def _inferir_categoria(self, descricao: str) -> str:
        """Infere categoria baseada na descrição."""
        descricao_lower = descricao.lower()
        
        if any(x in descricao_lower for x in ["uber", "99", "taxi", "combustivel", "gasolina", "posto"]):
            return "Transporte"
        elif any(x in descricao_lower for x in ["mercado", "supermercado", "açougue", "padaria", "restaurante", "ifood", "comida"]):
            return "Alimentação"
        elif any(x in descricao_lower for x in ["aluguel", "condominio", "agua", "luz", "energia", "internet"]):
            return "Moradia"
        elif any(x in descricao_lower for x in ["farmacia", "hospital", "medico", "saude", "plano"]):
            return "Saúde"
        elif any(x in descricao_lower for x in ["salario", "freelance", "projeto", "pagamento recebido"]):
            return "Trabalho"
        elif any(x in descricao_lower for x in ["netflix", "spotify", "cinema", "lazer", "diversao"]):
            return "Lazer"
        else:
            return "Outros"

    def format_transactions_for_registration(self, analysis: Dict[str, Any]) -> list:
        """
        Formata transações da análise para registro no sistema.
        
        Returns:
            Lista de transações prontas para registrar
        """
        transacoes = analysis.get("transacoes", [])
        formatted = []
        
        for t in transacoes:
            formatted.append({
                "type": "expense" if t.get("tipo") == "saida" else "income",
                "amount": t.get("valor", 0),
                "description": t.get("descricao", "Transação da imagem"),
                "category": t.get("categoria_sugerida", "outros"),
                "date": t.get("data"),
            })
        
        return formatted


# Singleton
_vision_service: VisionService = None


def get_vision_service() -> VisionService:
    """Retorna instância singleton do serviço de visão."""
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService()
    return _vision_service
