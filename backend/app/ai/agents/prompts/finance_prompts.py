"""
Prompts para o agente de finanças.
"""


class FinancePrompts:
    """Prompts utilizados pelo FinanceAgent."""

    SYSTEM_PROMPT = """Você é um assistente especializado em finanças pessoais.

Suas responsabilidades:
1. Registrar gastos e receitas
2. Categorizar transações automaticamente usando as categorias definidas
3. Gerar resumos financeiros
4. Identificar padrões de gastos
5. Responder perguntas sobre histórico financeiro (inclusive por categoria)

CATEGORIAS DE DESPESA (use EXATAMENTE estes nomes):
- Moradia: aluguel, prestação da casa, impostos (IPTU), condomínio, manutenção
- Contas: eletricidade, água, gás, telefone, internet, TV a cabo
- Alimentação: supermercado, restaurantes, lanchonetes, delivery, padaria
- Transporte: combustível, Uber/99, ônibus/metrô, manutenção veículo, pedágio, estacionamento
- Saúde: consultas médicas, remédios, plano de saúde, academia, dentista
- Educação: mensalidades, cursos, livros, materiais didáticos
- Lazer: cinema, shows, viagens, streaming (Netflix/Spotify), hobbies
- Vestuário: roupas, calçados, acessórios
- Dívidas: cartão de crédito, empréstimos, financiamentos
- Investimentos: aportes em fundos, poupança, ações
- Serviços Financeiros: taxas bancárias, tarifas, anuidades
- Outros: despesas diversas não categorizadas

CATEGORIAS DE RECEITA:
- Salário
- Freelance
- Investimentos
- Vendas
- Outros

Regras:
- SEMPRE use uma das categorias listadas acima (exatamente como escrito)
- Sempre confirme o valor e categoria registrados
- Para consultas por categoria, filtre APENAS transações daquela categoria
- Use R$ para valores em reais
- Quando perguntarem "quanto gastei com X", filtre pela categoria correspondente"""

    @staticmethod
    def get_intent_prompt(message: str) -> str:
        """Gera prompt para classificar intenção financeira."""
        return f"""
Analise a mensagem do usuário sobre finanças.

MENSAGEM: "{message}"

Determine a intenção:
1. "register" - registrar nova transação
2. "query" - consultar histórico/resumo
3. "delete" - cancelar/remover/deletar transação
4. "clarify" - precisa de mais informações

Retorne APENAS JSON:
{{
    "intent": "register|query|delete|clarify",
    "sub_intent": "descrição específica"
}}
"""

    @staticmethod
    def get_extraction_prompt(context: str, current_date: str, current_year: int, current_month: int, message: str) -> str:
        """
        Gera prompt para extração de transações.
        
        Args:
            context: Contexto formatado do usuário
            current_date: Data atual formatada
            current_year: Ano atual
            current_month: Mês atual
            message: Mensagem do usuário
        """
        return f"""
Extraia TODAS as transações financeiras mencionadas na mensagem.
O usuário pode mencionar múltiplos gastos e/ou receitas de uma só vez.

CONTEXTO:
{context}
Data atual: {current_date} (Ano: {current_year}, Mês: {current_month})

MENSAGEM: "{message}"

REGRAS PARA DATA:
- Se mencionar "ontem": use a data de ontem
- Se mencionar "dia X" ou "todo dia X": use dia X do mês atual (ou mês anterior se X > dia atual)
- Se mencionar "semana passada": use 7 dias atrás
- Se mencionar data específica (ex: 05/01): use essa data
- Se NÃO mencionar data: use a data atual
- Receitas recorrentes (salário, aluguel) que "caem" em um dia específico: use esse dia

IMPORTANTE: Identifique CADA transação separadamente. Exemplos:
- "gastei 80 no café e 150 de gasolina" = 2 despesas
- "gastei 50 no almoço e recebi 300 de venda" = 1 despesa + 1 receita
- "paguei luz 200, água 80 e internet 100" = 3 despesas

Retorne APENAS JSON com uma LISTA de transações:
{{
    "transactions": [
        {{
            "type": "expense|income",
            "amount": número (apenas o valor, sem R$),
            "description": "descrição da transação",
            "category": "categoria mais apropriada",
            "transaction_date": "YYYY-MM-DD",
            "is_recurring": true/false,
            "recurrence_day": dia do mês se for recorrente,
            "tags": ["tag1", "tag2"],
            "confidence": 0.0 a 1.0
        }}
    ]
}}

Se houver apenas UMA transação, retorne lista com 1 item.
Se não conseguir identificar nenhuma transação válida, retorne lista vazia.
"""

    @staticmethod
    def get_delete_identification_prompt(message: str, transactions_text: str) -> str:
        """Gera prompt para identificar transação a deletar."""
        return f"""
Identifique qual transação o usuário quer deletar.

MENSAGEM DO USUÁRIO: "{message}"

TRANSAÇÕES RECENTES:
{transactions_text}

Retorne APENAS JSON:
{{
    "transaction_id": número ou null se não identificar,
    "description_match": "descrição da transação identificada"
}}
"""

    # Templates de resposta
    TEMPLATES = {
        "single_transaction": (
            "✅ *{type_text} registrado!*\n\n"
            "💰 R$ {amount:.2f}\n"
            "📝 {description}\n"
            "📁 Categoria: {category}\n"
            "📅 Data: {date}"
        ),
        "multiple_transactions_header": "✅ *{count} transações registradas!*\n",
        "expense_line": "{i}. 📉 Gasto: R$ {amount:.2f} - {description} ({category})",
        "income_line": "{i}. 📈 Receita: R$ {amount:.2f} - {description} ({category})",
        "totals": (
            "\n💸 Total gastos: R$ {total_expenses:.2f}\n"
            "💰 Total receitas: R$ {total_income:.2f}"
        ),
        "query_no_results": "📊 Você não tem transações registradas para {period}.",
        "query_no_category": "📊 Você não tem gastos com **{category}** {period}.",
        "delete_confirm": "🗑️ Transação encontrada: *{desc}* - R$ {amount:.2f}\n\nConfirma a exclusão? (sim/não)",
        "clarification_needed": "Poderia me dar mais detalhes? Você quer registrar um gasto/receita ou consultar seu histórico?",
    }
