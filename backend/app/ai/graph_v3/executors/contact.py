"""
Contact Executor - Execução de ações de contatos.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

logger = logging.getLogger(__name__)


class ContactExecutor:
    """Executor de ações de contatos."""
    
    @staticmethod
    def create(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Cria contato."""
        from app.services.contact_service import ContactService
        
        try:
            service = ContactService(db)
            
            contact_data = {
                "name": params.get("nome", params.get("name", "")),
                "phone_number": params.get("telefone", params.get("phone", "")),
                "group_name": params.get("grupo", params.get("group", "")),
            }
            
            service.create_from_dict(user_id, contact_data)
            
            name = contact_data["name"]
            group = contact_data.get("group_name", "")
            
            template = f"👤 Contato *{name}* salvo"
            if group:
                template += f" no grupo _{group}_"
            template += "!"
            
            return ExecutionResult(success=True, action_type="create_contact", data={"contact": contact_data}, response_template=template)
        except Exception as e:
            logger.error(f"Erro ao criar contato: {e}")
            return ExecutionResult(success=False, action_type="create_contact", error=str(e))
    
    @staticmethod
    def list_all(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Lista contatos."""
        from app.services.contact_service import ContactService
        
        try:
            service = ContactService(db)
            
            group = params.get("grupo", params.get("group"))
            search = params.get("busca", params.get("search"))
            
            result = service.list(user_id, group_name=group, search=search, limit=20)
            contacts = result.get("items", [])
            
            if not contacts:
                template = "📭 Nenhum contato encontrado."
            else:
                lines = ["👥 *Seus contatos:*\n"]
                for c in contacts[:20]:
                    group_text = f" ({c.group_name})" if c.group_name else ""
                    lines.append(f"• {c.name}{group_text}")
                template = "\n".join(lines)
            
            return ExecutionResult(
                success=True,
                action_type="list_contacts",
                data={"contacts": [{"name": c.name, "phone": c.phone_number} for c in contacts]},
                response_template=template,
            )
        except Exception as e:
            logger.error(f"Erro ao listar contatos: {e}")
            return ExecutionResult(success=False, action_type="list_contacts", error=str(e))
    
    @staticmethod
    def delete(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Deleta contato."""
        from app.services.contact_service import ContactService
        
        try:
            service = ContactService(db)
            result = service.delete_by_filters(user_id, {"nome": params.get("nome", "")})
            count = result.get("deleted_count", 0)
            
            template = "🗑️ Contato deletado!" if count > 0 else "❌ Contato não encontrado."
            return ExecutionResult(success=count > 0, action_type="delete_contact", data=result, response_template=template)
        except Exception as e:
            return ExecutionResult(success=False, action_type="delete_contact", error=str(e))
    
    @staticmethod
    def update(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Atualiza contato."""
        from app.services.contact_service import ContactService
        
        try:
            service = ContactService(db)
            filters = {"nome": params.get("nome_busca", "")}
            updates = {}
            if params.get("novo_nome"): updates["name"] = params["novo_nome"]
            if params.get("novo_telefone"): updates["phone_number"] = params["novo_telefone"]
            if params.get("novo_grupo"): updates["group_name"] = params["novo_grupo"]
            
            result = service.update_by_filters(user_id, filters, updates)
            
            if result.get("success"):
                return ExecutionResult(success=True, action_type="update_contact", data=result, response_template="✏️ Contato atualizado!")
            return ExecutionResult(success=False, action_type="update_contact", error="Contato não encontrado")
        except Exception as e:
            return ExecutionResult(success=False, action_type="update_contact", error=str(e))
