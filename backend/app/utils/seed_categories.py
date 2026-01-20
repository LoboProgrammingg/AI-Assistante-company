"""
Script para popular as categorias de finanças no banco de dados.
Execute: python -m app.utils.seed_categories
"""

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import FinanceCategory, FinanceType

EXPENSE_CATEGORIES = [
    {"name": "Moradia", "icon": "🏠", "color": "#6366f1"},
    {"name": "Contas", "icon": "📄", "color": "#8b5cf6"},
    {"name": "Alimentação", "icon": "🍽️", "color": "#f59e0b"},
    {"name": "Transporte", "icon": "🚗", "color": "#3b82f6"},
    {"name": "Saúde", "icon": "🏥", "color": "#ef4444"},
    {"name": "Educação", "icon": "📚", "color": "#10b981"},
    {"name": "Lazer", "icon": "🎬", "color": "#ec4899"},
    {"name": "Vestuário", "icon": "👕", "color": "#f97316"},
    {"name": "Dívidas", "icon": "💳", "color": "#dc2626"},
    {"name": "Investimentos", "icon": "📈", "color": "#22c55e"},
    {"name": "Serviços Financeiros", "icon": "🏦", "color": "#64748b"},
    {"name": "Outros", "icon": "📦", "color": "#94a3b8"},
]

INCOME_CATEGORIES = [
    {"name": "Salário", "icon": "💰", "color": "#22c55e"},
    {"name": "Freelance", "icon": "💼", "color": "#3b82f6"},
    {"name": "Investimentos Receita", "icon": "📈", "color": "#10b981"},
    {"name": "Vendas", "icon": "🛒", "color": "#f59e0b"},
    {"name": "Outros Receita", "icon": "💵", "color": "#94a3b8"},
]


def seed_categories(db: Session):
    """Popula as categorias no banco de dados."""

    # Categorias de despesa
    for cat_data in EXPENSE_CATEGORIES:
        existing = (
            db.query(FinanceCategory)
            .filter(FinanceCategory.name == cat_data["name"], FinanceCategory.type == FinanceType.EXPENSE)
            .first()
        )

        if not existing:
            category = FinanceCategory(
                name=cat_data["name"], type=FinanceType.EXPENSE, icon=cat_data["icon"], color=cat_data["color"]
            )
            db.add(category)
            print(f"✅ Categoria criada: {cat_data['name']} (Despesa)")
        else:
            print(f"⏭️ Categoria já existe: {cat_data['name']} (Despesa)")

    # Categorias de receita
    for cat_data in INCOME_CATEGORIES:
        existing = (
            db.query(FinanceCategory)
            .filter(FinanceCategory.name == cat_data["name"], FinanceCategory.type == FinanceType.INCOME)
            .first()
        )

        if not existing:
            category = FinanceCategory(
                name=cat_data["name"], type=FinanceType.INCOME, icon=cat_data["icon"], color=cat_data["color"]
            )
            db.add(category)
            print(f"✅ Categoria criada: {cat_data['name']} (Receita)")
        else:
            print(f"⏭️ Categoria já existe: {cat_data['name']} (Receita)")

    db.commit()
    print("\n🎉 Categorias populadas com sucesso!")


def get_category_by_name(db: Session, name: str, finance_type: FinanceType) -> FinanceCategory:
    """Busca categoria pelo nome (case-insensitive)."""
    category = (
        db.query(FinanceCategory)
        .filter(FinanceCategory.name.ilike(f"%{name}%"), FinanceCategory.type == finance_type)
        .first()
    )

    if not category:
        # Fallback para "Outros"
        category = (
            db.query(FinanceCategory)
            .filter(FinanceCategory.name.ilike("%outros%"), FinanceCategory.type == finance_type)
            .first()
        )

    return category


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_categories(db)
    finally:
        db.close()
