import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models import Contact, CustomContactGroup
from app.schemas.contact import (
    ContactCreate,
    ContactGroupCreate,
    ContactGroupUpdate,
    ContactUpdate,
)

logger = logging.getLogger(__name__)


def normalize_group_name(name: str) -> str:
    """Normaliza nome do grupo para slug."""
    normalized = unicodedata.normalize("NFKD", name)
    normalized = normalized.encode("ASCII", "ignore").decode("ASCII")
    normalized = normalized.lower().strip()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_]", "", normalized)
    return normalized or "outros"


class ContactGroupService:
    """Serviço para gerenciamento de grupos de contatos."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, data: ContactGroupCreate) -> CustomContactGroup:
        """Cria um novo grupo de contatos."""
        slug = normalize_group_name(data.name)

        # Verificar se já existe
        existing = self.get_by_slug(user_id, slug)
        if existing:
            return existing

        group = CustomContactGroup(
            user_id=user_id,
            name=data.name,
            slug=slug,
            description=data.description,
            icon=data.icon,
        )
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        logger.info(f"Grupo criado: {group.name} para user {user_id}")
        return group

    def get_or_create(self, user_id: int, name: str) -> CustomContactGroup:
        """Busca ou cria um grupo pelo nome."""
        slug = normalize_group_name(name)
        existing = self.get_by_slug(user_id, slug)
        if existing:
            return existing

        return self.create(user_id, ContactGroupCreate(name=name))

    def get_by_id(self, user_id: int, group_id: int) -> Optional[CustomContactGroup]:
        """Busca grupo por ID."""
        return (
            self.db.query(CustomContactGroup)
            .filter(and_(CustomContactGroup.id == group_id, CustomContactGroup.user_id == user_id))
            .first()
        )

    def get_by_slug(self, user_id: int, slug: str) -> Optional[CustomContactGroup]:
        """Busca grupo por slug."""
        normalized_slug = normalize_group_name(slug)
        return (
            self.db.query(CustomContactGroup)
            .filter(
                and_(
                    CustomContactGroup.user_id == user_id,
                    CustomContactGroup.slug == normalized_slug,
                    CustomContactGroup.is_active == True,
                )
            )
            .first()
        )

    def list(self, user_id: int) -> List[Dict[str, Any]]:
        """Lista todos os grupos do usuário com contagem de contatos."""
        groups = (
            self.db.query(CustomContactGroup)
            .filter(and_(CustomContactGroup.user_id == user_id, CustomContactGroup.is_active == True))
            .order_by(CustomContactGroup.name.asc())
            .all()
        )

        result = []
        for g in groups:
            contact_count = (
                self.db.query(Contact)
                .filter(and_(Contact.user_id == user_id, Contact.group_name == g.slug, Contact.is_active == True))
                .count()
            )
            result.append({"id": g.id, "name": g.name, "slug": g.slug, "icon": g.icon, "contact_count": contact_count})
        return result

    def update(self, user_id: int, group_id: int, data: ContactGroupUpdate) -> Optional[CustomContactGroup]:
        """Atualiza um grupo."""
        group = self.get_by_id(user_id, group_id)
        if not group:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if "name" in update_data:
            update_data["slug"] = normalize_group_name(update_data["name"])

        for key, value in update_data.items():
            setattr(group, key, value)

        self.db.commit()
        self.db.refresh(group)
        return group

    def delete(self, user_id: int, group_id: int) -> bool:
        """Remove um grupo (soft delete)."""
        group = self.get_by_id(user_id, group_id)
        if not group:
            return False

        group.is_active = False
        self.db.commit()
        return True


class ContactService:
    """Serviço para gerenciamento de contatos."""

    def __init__(self, db: Session):
        self.db = db
        self.group_service = ContactGroupService(db)

    def create(self, user_id: int, data: ContactCreate) -> Contact:
        """Cria um novo contato."""
        group_name = normalize_group_name(data.group_name) if data.group_name else "outros"

        # Criar grupo se não existir
        self.group_service.get_or_create(user_id, group_name)

        contact = Contact(
            user_id=user_id,
            name=data.name,
            phone_number=data.phone_number,
            group_name=group_name,
            notes=data.notes,
        )
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        logger.info(f"Contato criado: {contact.name} no grupo {group_name} para user {user_id}")
        return contact

    def create_from_dict(self, user_id: int, data: Dict[str, Any]) -> Contact:
        """Cria contato a partir de dicionário (para uso da IA)."""
        phone_number = data["phone_number"]
        group_name = normalize_group_name(data.get("group_name") or data.get("group") or "outros")

        # Verificar se já existe contato com mesmo telefone
        existing = self.get_by_phone(user_id, phone_number)
        if existing:
            logger.info(f"Contato já existe: {existing.name} ({phone_number})")
            return existing

        # Criar grupo se não existir
        self.group_service.get_or_create(user_id, group_name)

        contact = Contact(
            user_id=user_id,
            name=data["name"],
            phone_number=phone_number,
            group_name=group_name,
            notes=data.get("notes"),
        )
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        logger.info(f"Contato criado: {contact.name} no grupo {group_name}")
        return contact

    def get_by_phone(self, user_id: int, phone_number: str) -> Optional[Contact]:
        """Busca contato por número de telefone."""
        # Normalizar telefone (remover caracteres não numéricos)
        normalized_phone = re.sub(r"[^\d]", "", phone_number)
        return (
            self.db.query(Contact)
            .filter(
                and_(
                    Contact.user_id == user_id,
                    func.regexp_replace(Contact.phone_number, "[^0-9]", "", "g") == normalized_phone,
                    Contact.is_active == True,
                )
            )
            .first()
        )

    def create_bulk(self, user_id: int, contacts_data: List[ContactCreate]) -> List[Contact]:
        """Cria múltiplos contatos de uma vez."""
        contacts = []
        for data in contacts_data:
            group_name = normalize_group_name(data.group_name) if data.group_name else "outros"
            self.group_service.get_or_create(user_id, group_name)

            contact = Contact(
                user_id=user_id,
                name=data.name,
                phone_number=data.phone_number,
                group_name=group_name,
                notes=data.notes,
            )
            contacts.append(contact)

        self.db.add_all(contacts)
        self.db.commit()
        for contact in contacts:
            self.db.refresh(contact)
        logger.info(f"{len(contacts)} contatos criados para user {user_id}")
        return contacts

    def get_by_id(self, user_id: int, contact_id: int) -> Optional[Contact]:
        """Busca contato por ID."""
        return self.db.query(Contact).filter(and_(Contact.id == contact_id, Contact.user_id == user_id)).first()

    def list(
        self,
        user_id: int,
        group_name: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Lista contatos com filtros e paginação."""
        query = self.db.query(Contact).filter(and_(Contact.user_id == user_id, Contact.is_active == True))

        if group_name:
            normalized = normalize_group_name(group_name)
            query = query.filter(Contact.group_name == normalized)

        if search:
            search_filter = f"%{search}%"
            query = query.filter(or_(Contact.name.ilike(search_filter), Contact.phone_number.ilike(search_filter)))

        total = query.count()
        pages = (total + limit - 1) // limit if limit > 0 else 1
        offset = (page - 1) * limit

        items = query.order_by(Contact.name.asc()).offset(offset).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1,
        }

    def get_by_group(self, user_id: int, group_name: str) -> List[Contact]:
        """Retorna todos os contatos de um grupo específico."""
        normalized = normalize_group_name(group_name)
        return (
            self.db.query(Contact)
            .filter(
                and_(
                    Contact.user_id == user_id,
                    Contact.group_name == normalized,
                    Contact.is_active == True,
                )
            )
            .order_by(Contact.name.asc())
            .all()
        )

    def get_groups_summary(self, user_id: int) -> List[Dict[str, Any]]:
        """Retorna contagem de contatos por grupo."""
        results = (
            self.db.query(Contact.group_name, func.count(Contact.id).label("count"))
            .filter(and_(Contact.user_id == user_id, Contact.is_active == True))
            .group_by(Contact.group_name)
            .all()
        )

        return [{"group_name": r.group_name, "count": r.count} for r in results]

    def update(self, user_id: int, contact_id: int, data: ContactUpdate) -> Optional[Contact]:
        """Atualiza um contato existente."""
        contact = self.get_by_id(user_id, contact_id)
        if not contact:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if "group_name" in update_data and update_data["group_name"]:
            update_data["group_name"] = normalize_group_name(update_data["group_name"])
            self.group_service.get_or_create(user_id, update_data["group_name"])

        for key, value in update_data.items():
            setattr(contact, key, value)

        self.db.commit()
        self.db.refresh(contact)
        logger.info(f"Contato atualizado: {contact.id}")
        return contact

    def delete(self, user_id: int, contact_id: int) -> bool:
        """Remove um contato (soft delete)."""
        contact = self.get_by_id(user_id, contact_id)
        if not contact:
            return False

        contact.is_active = False
        self.db.commit()
        logger.info(f"Contato desativado: {contact_id}")
        return True

    def delete_by_filters(self, user_id: int, filters: dict) -> dict:
        """
        Deleta contatos baseado em filtros flexíveis.
        
        Args:
            user_id: ID do usuário
            filters: Dict com filtros (id, nome)
        
        Returns:
            Dict com resultado da operação
        """
        deleted_count = 0
        deleted_items = []
        
        # Deletar por ID específico
        if filters.get("id"):
            contact = self.get_by_id(user_id, filters["id"])
            if contact:
                name = contact.name
                contact.is_active = False
                deleted_count += 1
                deleted_items.append(name)
        
        # Deletar por nome (busca parcial)
        elif filters.get("nome"):
            nome = filters["nome"].lower().strip()
            
            contacts = (
                self.db.query(Contact)
                .filter(
                    and_(
                        Contact.user_id == user_id,
                        Contact.is_active == True,
                        Contact.name.ilike(f"%{nome}%"),
                    )
                )
                .all()
            )
            
            for contact in contacts:
                deleted_items.append(contact.name)
                contact.is_active = False
                deleted_count += 1
        
        if deleted_count > 0:
            self.db.commit()
            logger.info(f"[CONTACT] Deletados {deleted_count} contatos: {deleted_items}")
        
        return {
            "deleted_count": deleted_count,
            "deleted_items": deleted_items,
        }

    def update_by_filters(self, user_id: int, filters: dict, updates: dict) -> dict:
        """
        Atualiza contato baseado em filtros.
        
        Args:
            user_id: ID do usuário
            filters: Dict com filtros para encontrar o contato
            updates: Dict com campos a atualizar
        
        Returns:
            Dict com resultado da operação
        """
        contact = None
        
        # Encontrar por ID
        if filters.get("id"):
            contact = self.get_by_id(user_id, filters["id"])
        
        # Encontrar por nome (último que bate)
        elif filters.get("nome"):
            nome = filters["nome"].lower().strip()
            contact = (
                self.db.query(Contact)
                .filter(
                    and_(
                        Contact.user_id == user_id,
                        Contact.is_active == True,
                        Contact.name.ilike(f"%{nome}%"),
                    )
                )
                .order_by(Contact.created_at.desc())
                .first()
            )
        
        if not contact:
            return {"success": False, "error": "Contato não encontrado"}
        
        old_name = contact.name
        
        # Aplicar atualizações
        if "name" in updates:
            contact.name = updates["name"]
        if "phone_number" in updates:
            contact.phone_number = updates["phone_number"]
        if "group_name" in updates:
            contact.group_name = normalize_group_name(updates["group_name"])
            self.group_service.get_or_create(user_id, contact.group_name)
        
        self.db.commit()
        self.db.refresh(contact)
        
        logger.info(f"[CONTACT] Atualizado: '{old_name}' -> '{contact.name}'")
        
        return {
            "success": True,
            "message": f"'{old_name}' atualizado",
        }

    def delete_permanent(self, user_id: int, contact_id: int) -> bool:
        """Remove permanentemente um contato."""
        contact = self.get_by_id(user_id, contact_id)
        if not contact:
            return False

        self.db.delete(contact)
        self.db.commit()
        logger.info(f"Contato removido permanentemente: {contact_id}")
        return True

    def search_by_name(self, user_id: int, name: str) -> List[Contact]:
        """Busca contatos por nome (para uso da IA)."""
        return (
            self.db.query(Contact)
            .filter(
                and_(
                    Contact.user_id == user_id,
                    Contact.name.ilike(f"%{name}%"),
                    Contact.is_active == True,
                )
            )
            .all()
        )

    def get_phone_numbers_by_group(self, user_id: int, group_name: str) -> List[str]:
        """Retorna lista de telefones de um grupo (para envio de mensagens)."""
        contacts = self.get_by_group(user_id, group_name)
        return [c.phone_number for c in contacts]

    def get_all_groups(self, user_id: int) -> List[str]:
        """Retorna lista de todos os grupos do usuário."""
        results = (
            self.db.query(Contact.group_name)
            .filter(and_(Contact.user_id == user_id, Contact.is_active == True))
            .distinct()
            .all()
        )
        return [r.group_name for r in results]
