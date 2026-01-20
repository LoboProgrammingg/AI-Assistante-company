"""
Constantes para o agente de finanças.
Categorias, keywords e mapeamentos centralizados.
"""
from typing import Dict, List, Optional


class FinanceConstants:
    """Constantes utilizadas pelo FinanceAgent."""

    # Mapeamento de categorias de despesa com palavras-chave para identificação automática
    EXPENSE_CATEGORIES: Dict[str, List[str]] = {
        "Moradia": [
            "aluguel", "prestação", "casa", "apartamento", "condomínio", 
            "iptu", "manutenção casa", "reforma"
        ],
        "Contas": [
            "luz", "água", "gás", "energia", "telefone", "internet", 
            "tv cabo", "celular", "conta"
        ],
        "Alimentação": [
            "almoço", "jantar", "café", "lanche", "restaurante", "supermercado", 
            "mercado", "padaria", "delivery", "ifood", "comida", "pizza", "hamburguer"
        ],
        "Transporte": [
            "uber", "99", "taxi", "combustível", "gasolina", "álcool", 
            "ônibus", "metrô", "passagem", "pedágio", "estacionamento"
        ],
        "Saúde": [
            "médico", "remédio", "farmácia", "consulta", "exame", 
            "plano de saúde", "dentista", "hospital", "academia"
        ],
        "Educação": [
            "curso", "escola", "faculdade", "universidade", "livro", 
            "apostila", "mensalidade", "material escolar"
        ],
        "Lazer": [
            "cinema", "show", "teatro", "viagem", "hotel", "netflix", 
            "spotify", "streaming", "jogo", "hobby", "festa", "bar"
        ],
        "Vestuário": [
            "roupa", "calçado", "sapato", "tênis", "camisa", "calça", 
            "vestido", "acessório", "bolsa", "relógio"
        ],
        "Dívidas": [
            "cartão", "empréstimo", "financiamento", "parcela", 
            "fatura", "juros", "dívida"
        ],
        "Investimentos": [
            "investimento", "poupança", "ação", "fundo", "tesouro", "cdb", "reserva"
        ],
        "Serviços Financeiros": [
            "tarifa", "taxa bancária", "anuidade", "ted", "pix", "transferência"
        ],
        "Outros": []
    }

    # Categorias de receita
    INCOME_CATEGORIES: Dict[str, List[str]] = {
        "Salário": ["salário", "pagamento", "holerite", "contracheque"],
        "Freelance": ["freelance", "freela", "serviço", "trabalho extra", "bico"],
        "Investimentos": ["dividendo", "rendimento", "juros", "lucro"],
        "Vendas": ["venda", "vendi", "vendido"],
        "Outros": []
    }

    # Mapeamento de palavras-chave para detecção de categoria em mensagens
    CATEGORY_KEYWORDS: Dict[str, List[str]] = {
        "alimentação": ["alimentação", "alimentacao", "comida", "alimento", "refeição", "refeicao"],
        "moradia": ["moradia", "casa", "aluguel", "apartamento"],
        "contas": ["contas", "conta de luz", "conta de água", "utilidades"],
        "transporte": ["transporte", "uber", "combustível", "gasolina", "ônibus"],
        "saúde": ["saúde", "saude", "médico", "remédio", "farmácia", "academia"],
        "educação": ["educação", "educacao", "curso", "escola", "faculdade"],
        "lazer": ["lazer", "entretenimento", "diversão", "cinema", "viagem"],
        "vestuário": ["vestuário", "vestuario", "roupa", "roupas", "calçado"],
        "dívidas": ["dívidas", "dividas", "dívida", "divida", "cartão", "empréstimo"],
        "investimentos": ["investimento", "investimentos", "poupança", "ação"],
        "serviços financeiros": ["serviços financeiros", "taxa", "tarifa bancária"],
    }

    @classmethod
    def detect_category_in_message(cls, message: str) -> Optional[str]:
        """
        Detecta se a mensagem menciona uma categoria específica.
        
        Args:
            message: Mensagem do usuário
            
        Returns:
            Nome da categoria ou None
        """
        message_lower = message.lower()
        
        for category, keywords in cls.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return category.title()
        return None

    @classmethod
    def get_all_expense_categories(cls) -> List[str]:
        """Retorna lista de todas as categorias de despesa."""
        return list(cls.EXPENSE_CATEGORIES.keys())

    @classmethod
    def get_all_income_categories(cls) -> List[str]:
        """Retorna lista de todas as categorias de receita."""
        return list(cls.INCOME_CATEGORIES.keys())
