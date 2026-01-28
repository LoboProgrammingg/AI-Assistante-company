"""
Finance Executor - Execução de ações financeiras.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

logger = logging.getLogger(__name__)


class FinanceExecutor:
    """Executor de ações financeiras."""

    @staticmethod
    def create(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Cria transação financeira."""
        from app.services.finance_service import FinanceService

        logger.info(f"[FINANCE] 📥 CREATE recebeu params: {params}")

        try:
            service = FinanceService(db)

            # Verificar se é uma lista de transações (do CognitiveNode)
            if "transactions" in params:
                items = params["transactions"]
                if not isinstance(items, list):
                    items = [items]
                
                logger.info(f"[FINANCE] 📋 Processando {len(items)} transações")
                
                created = []
                for item in items:
                    # Normalizar campos PT/EN
                    finance_data = {
                        "amount": item.get("valor", item.get("amount", 0)),
                        "description": item.get("descricao", item.get("description", "")),
                        "category": item.get("categoria", item.get("category", "Outros")),
                        "type": item.get("tipo", item.get("type", "expense")),
                        "date": item.get("data", item.get("date")),
                    }
                    logger.info(f"[FINANCE] 💳 Item normalizado: {finance_data}")
                    
                    # Validar amount > 0
                    if finance_data["amount"] <= 0:
                        logger.warning(f"[FINANCE] Valor inválido: {finance_data['amount']}")
                        continue
                    
                    service.create_from_entities(user_id, finance_data)
                    created.append(finance_data)
                
                if not created:
                    return ExecutionResult(
                        success=False,
                        action_type="create_finance",
                        error="Nenhuma transação válida para criar (valor deve ser > 0)"
                    )
                
                # Template para múltiplas transações
                if len(created) == 1:
                    data = created[0]
                    template = f"✅ {'Gasto' if data['type'] == 'expense' else 'Receita'} registrado: *{data['description']}* - R$ {data['amount']:.2f}"
                else:
                    total = sum(t["amount"] for t in created)
                    template = f"✅ {len(created)} transações criadas - Total: R$ {total:.2f}"
                
                return ExecutionResult(
                    success=True,
                    action_type="create_finance",
                    data={"finances": created},
                    response_template=template,
                )
            
            # Single transaction (fallback) - entities vêm direto do CognitiveNode
            logger.info(f"[FINANCE] 📝 Single transaction mode")
            
            finance_data = {
                "amount": params.get("valor", params.get("amount", 0)),
                "description": params.get("descricao", params.get("description", "")),
                "category": params.get("categoria", params.get("category", "Outros")),
                "type": params.get("tipo", params.get("type", "expense")),
                "date": params.get("data", params.get("date")),
            }
            
            logger.info(f"[FINANCE] 💳 Dados normalizados: type={finance_data['type']} | amount={finance_data['amount']} | desc={finance_data['description']}")
            
            # Validar amount > 0
            if finance_data["amount"] <= 0:
                logger.warning(f"[FINANCE] ❌ Valor inválido: {finance_data['amount']}")
                return ExecutionResult(
                    success=False,
                    action_type="create_finance",
                    error="Valor deve ser maior que 0"
                )

            service.create_from_entities(user_id, finance_data)
            
            logger.info(f"[FINANCE] ✅ Transação criada com sucesso: {finance_data}")

            amount = finance_data["amount"]
            desc = finance_data["description"]
            tipo = "Gasto" if finance_data["type"] == "expense" else "Receita"

            template = f"✅ {tipo} registrado: *{desc}* - R$ {amount:.2f}"
            logger.info(f"[FINANCE] 📤 Template: {template}")

            return ExecutionResult(
                success=True,
                action_type="create_finance",
                data={"finance": finance_data},
                response_template=template,
            )
        except Exception as e:
            logger.error(f"Erro ao criar transação: {e}")
            return ExecutionResult(success=False, action_type="create_finance", error=str(e))

    @staticmethod
    def query(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """
        Consulta finanças e retorna dados completos para o ResponderNode.

        Não gera template fixo - deixa o LLM gerar resposta inteligente
        baseada nos dados reais e na pergunta do usuário.
        """
        from app.services.finance_service import FinanceService

        try:
            service = FinanceService(db)

            periodo = params.get("periodo", "mes")
            ano = params.get("ano")
            busca = params.get("busca")
            limite = params.get("limite")
            ordenacao = params.get("ordenacao")
            tipo_filtro = params.get("tipo_filtro")

            # Sempre buscar resumo do período atual
            summary = service.get_summary_by_period(user_id, periodo, ano, busca)

            # Query de top N transações
            if limite or ordenacao:
                top_data = service.get_top_transactions(
                    user_id=user_id,
                    limit=int(limite) if limite else 5,
                    tipo=tipo_filtro or "expense",
                    periodo=periodo,
                    ordenacao=ordenacao or "maior",
                )
                # Combinar dados para contexto rico
                combined_data = {
                    "transactions": top_data.get("transactions", []),
                    "total": top_data.get("total", 0),
                    "query": top_data.get("query", {}),
                    "summary": summary.get("summary", {}),
                    "by_category": summary.get("by_category", []),
                    "period": top_data.get("period", {}),
                }

                logger.info(f"[FINANCE] Top {limite or 5} transações encontradas")

                # Não usar template - deixar ResponderNode gerar resposta inteligente
                return ExecutionResult(
                    success=True,
                    action_type="query_finance",
                    data=combined_data,
                    response_template=None,  # IMPORTANTE: deixar LLM gerar
                )

            # Query de busca por termo
            if busca:
                search_data = service.get_summary_by_period(user_id, periodo, ano, busca)
                logger.info(f"[FINANCE] Busca por '{busca}': {len(search_data.get('transactions', []))} resultados")

                return ExecutionResult(
                    success=True,
                    action_type="query_finance",
                    data=search_data,
                    response_template=None,
                )

            # Query de resumo geral
            logger.info(f"[FINANCE] Resumo do período '{periodo}'")

            return ExecutionResult(
                success=True,
                action_type="query_finance",
                data=summary,
                response_template=None,  # Deixar LLM analisar e responder
            )

        except Exception as e:
            logger.error(f"Erro ao consultar finanças: {e}")
            return ExecutionResult(success=False, action_type="query_finance", error=str(e))

    @staticmethod
    def _format_summary(summary: Dict, periodo: str) -> str:
        """Formata resumo financeiro."""
        s = summary.get("summary", {})

        # Compatibilidade: service retorna 'total_expenses' (plural)
        total_expense = s.get("total_expenses", s.get("total_expense", 0))
        total_income = s.get("total_income", 0)
        balance = s.get("balance", 0)
        count = s.get("count", 0)

        # Calcular count a partir de by_category se não vier direto
        if count == 0:
            by_category = summary.get("by_category", [])
            count = sum(cat.get("transactions_count", 0) for cat in by_category)

        # Se ainda não tem count mas tem valores, inferir que há transações
        if count == 0 and (total_expense > 0 or total_income > 0):
            count = 1  # Pelo menos 1

        periodo_text = {
            "hoje": "de hoje",
            "semana": "da semana",
            "mes": "do mês",
            "ano": "do ano",
            "tudo": "totais",
        }.get(periodo, f"de {periodo}")

        if count == 0:
            return f"📊 Nenhuma transação encontrada {periodo_text}."

        emoji = "🟢" if balance >= 0 else "🔴"
        return f"""📊 *Resumo financeiro {periodo_text}*

💸 Gastos: R$ {total_expense:,.2f}
💰 Receitas: R$ {total_income:,.2f}
{emoji} Saldo: R$ {balance:,.2f}

_{count} transação(ões)_"""

    @staticmethod
    def _format_top_transactions(data: Dict) -> str:
        """Formata top N transações."""
        transactions = data.get("transactions", [])
        query = data.get("query", {})
        total = data.get("total", 0)

        limite = query.get("limit", 5)
        tipo = query.get("tipo", "expense")
        ordenacao = query.get("ordenacao", "maior")

        if not transactions:
            tipo_text = "gastos" if tipo == "expense" else "receitas" if tipo == "income" else "transações"
            return f"📊 Nenhum(a) {tipo_text} encontrado(a) no período."

        # Título
        tipo_text = "gastos" if tipo == "expense" else "receitas" if tipo == "income" else "transações"
        ord_text = "maiores" if ordenacao == "maior" else "menores"
        lines = [f"📊 *Top {len(transactions)} {ord_text} {tipo_text}:*\n"]

        # Listar transações
        for i, t in enumerate(transactions, 1):
            emoji = "🔴" if t.get("type") == "expense" else "🟢"
            amount = t.get("amount", 0)
            desc = t.get("description", "Sem descrição")[:35]
            cat = t.get("category", "")
            date_str = t.get("date", "")[:10]

            lines.append(f"{i}. {emoji} *R$ {amount:,.2f}*")
            lines.append(f"   _{desc}_")
            if cat:
                lines.append(f"   📁 {cat} | 📅 {date_str}")
            else:
                lines.append(f"   📅 {date_str}")

        # Total
        lines.append(f"\n💰 *Total:* R$ {total:,.2f}")

        return "\n".join(lines)

    @staticmethod
    def _format_filtered_transactions(data: Dict, busca: str) -> str:
        """Formata transações filtradas por busca."""
        transactions = data.get("transactions", [])
        s = data.get("summary", {})

        count = len(transactions)
        total_expenses = s.get("total_expenses", 0)
        total_income = s.get("total_income", 0)

        if count == 0:
            return f"🔍 Nenhuma transação encontrada com *{busca}*."

        # Listar até 5 transações
        lines = [f"🔍 *Transações com '{busca}':*\n"]

        for t in transactions[:5]:
            emoji = "🟢" if t.get("type") == "income" else "🔴"
            amount = t.get("amount", 0)
            desc = t.get("description", "")[:30]
            date_str = t.get("date", "")[:10]
            lines.append(f"{emoji} R$ {amount:.2f} - {desc} ({date_str})")

        if count > 5:
            lines.append(f"\n_... e mais {count - 5} transação(ões)_")

        # Totais
        if total_expenses > 0 or total_income > 0:
            lines.append(f"\n💸 *Total gastos:* R$ {total_expenses:,.2f}")
            if total_income > 0:
                lines.append(f"💰 *Total receitas:* R$ {total_income:,.2f}")

        return "\n".join(lines)

    @staticmethod
    def delete(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Deleta transação financeira."""
        from app.services.finance_service import FinanceService

        try:
            service = FinanceService(db)
            result = service.delete_by_filters(user_id, params)

            count = result.get("deleted_count", 0)
            items = result.get("deleted_items", [])

            if count > 0:
                template = f"🗑️ Deletado: {', '.join(items[:3])}"
                if count > 3:
                    template += f" (+{count - 3})"
            else:
                template = "❌ Nenhuma transação encontrada."

            return ExecutionResult(
                success=count > 0, action_type="delete_finance", data=result, response_template=template
            )
        except Exception as e:
            return ExecutionResult(success=False, action_type="delete_finance", error=str(e))

    @staticmethod
    def update(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Atualiza transação financeira."""
        from app.services.finance_service import FinanceService

        logger.info(f"[FINANCE] 📝 UPDATE recebeu params: {params}")

        try:
            service = FinanceService(db)

            # Construir filtros de busca
            filters = {}
            
            # Busca por ID (mais preciso)
            if params.get("id") or params.get("finance_id"):
                filters["id"] = params.get("id", params.get("finance_id"))
            
            # Busca por descrição (termo de busca)
            elif params.get("descricao_busca") or params.get("busca") or params.get("descricao"):
                filters["descricao"] = params.get("descricao_busca", params.get("busca", params.get("descricao", "")))
            
            # Busca por original_message (extrair termos relevantes)
            elif params.get("original_message"):
                # Extrair possíveis termos de busca da mensagem original
                msg = params["original_message"].lower()
                # Palavras-chave comuns para ignorar
                ignore = ["altere", "mude", "corrija", "atualize", "o", "a", "de", "para", "mim", "que", "foi", "era", "deveria", "ser", "mas", "como", "voce", "você", "registrou"]
                words = [w for w in msg.split() if w not in ignore and len(w) > 2]
                if words:
                    filters["descricao"] = " ".join(words[:3])  # Primeiras 3 palavras relevantes
                    logger.info(f"[FINANCE] 🔍 Extraído termo de busca: '{filters['descricao']}'")
                else:
                    filters["ultima"] = True
                    logger.info(f"[FINANCE] 🔍 Usando última transação")
            
            # Fallback: última transação
            else:
                filters["ultima"] = True
                logger.info(f"[FINANCE] 🔍 Fallback: usando última transação")

            logger.info(f"[FINANCE] 🔍 Filtros de busca: {filters}")

            # Construir updates
            updates = {}

            if params.get("novo_valor") or params.get("amount"):
                updates["amount"] = params.get("novo_valor", params.get("amount"))
            if params.get("nova_descricao") or params.get("description"):
                updates["description"] = params.get("nova_descricao", params.get("description"))
            if params.get("novo_tipo") or params.get("type") or params.get("tipo"):
                updates["type"] = params.get("novo_tipo", params.get("type", params.get("tipo")))
            if params.get("nova_categoria") or params.get("category") or params.get("categoria"):
                updates["category"] = params.get("nova_categoria", params.get("category", params.get("categoria")))

            logger.info(f"[FINANCE] ✏️ Updates a aplicar: {updates}")

            if not updates:
                logger.warning(f"[FINANCE] ⚠️ Nenhum update especificado")
                return ExecutionResult(
                    success=False,
                    action_type="update_finance",
                    data={},
                    response_template="❌ Nenhuma alteração especificada. Diga o que deseja mudar (valor, tipo, descrição).",
                )

            result = service.update_by_filters(user_id, filters, updates)

            logger.info(f"[FINANCE] 📤 Resultado update: {result}")

            if result.get("success"):
                old_data = result.get("old", {})
                old_desc = old_data.get("description", "Transação")
                new_info = []
                if updates.get("type"):
                    tipo_label = "Receita" if updates["type"] == "income" else "Gasto"
                    new_info.append(f"tipo → {tipo_label}")
                if updates.get("amount"):
                    new_info.append(f"valor → R$ {updates['amount']:.2f}")
                if updates.get("description"):
                    new_info.append(f"descrição → {updates['description']}")
                
                changes = ", ".join(new_info) if new_info else "atualizado"
                template = f"✏️ *{old_desc}* atualizado: {changes}"
            else:
                template = f"❌ {result.get('error', 'Transação não encontrada')}"

            return ExecutionResult(
                success=result.get("success", False),
                action_type="update_finance",
                data=result,
                response_template=template,
            )
        except Exception as e:
            logger.error(f"[FINANCE] ❌ Erro no update: {e}", exc_info=True)
            return ExecutionResult(success=False, action_type="update_finance", error=str(e))
