import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import require_specialist
from app.models.users import User
from app.models.references import DictionaryEntry, BrandWhitelist, ChecklistRule

router = APIRouter(prefix="/references", tags=["references"])


class DictEntryCreate(BaseModel):
    term: str
    category: str = "general"


class BrandCreate(BaseModel):
    brand_name: str


class RuleUpdate(BaseModel):
    is_active: bool | None = None
    description: str | None = None


@router.get("/dictionary")
async def list_dictionary(search: str = "", db: AsyncSession = Depends(get_db), _: User = Depends(require_specialist)):
    q = select(DictionaryEntry)
    if search:
        q = q.where(DictionaryEntry.term.ilike(f"%{search}%"))
    result = await db.execute(q.order_by(DictionaryEntry.term))
    return [{"id": str(e.id), "term": e.term, "category": e.category} for e in result.scalars().all()]


@router.post("/dictionary", status_code=201)
async def add_dictionary(data: DictEntryCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_specialist)):
    entry = DictionaryEntry(term=data.term, category=data.category, added_by=current_user.id)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"id": str(entry.id), "term": entry.term, "category": entry.category}


@router.delete("/dictionary/{entry_id}", status_code=204)
async def delete_dictionary(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_specialist)):
    result = await db.execute(select(DictionaryEntry).where(DictionaryEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Термин не найден")
    await db.delete(entry)
    await db.commit()


@router.get("/brands")
async def list_brands(db: AsyncSession = Depends(get_db), _: User = Depends(require_specialist)):
    result = await db.execute(select(BrandWhitelist).order_by(BrandWhitelist.brand_name))
    return [{"id": str(b.id), "brand_name": b.brand_name} for b in result.scalars().all()]


@router.post("/brands", status_code=201)
async def add_brand(data: BrandCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_specialist)):
    brand = BrandWhitelist(brand_name=data.brand_name, added_by=current_user.id)
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return {"id": str(brand.id), "brand_name": brand.brand_name}


@router.delete("/brands/{brand_id}", status_code=204)
async def delete_brand(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_specialist)):
    result = await db.execute(select(BrandWhitelist).where(BrandWhitelist.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(404, "Бренд не найден")
    await db.delete(brand)
    await db.commit()


@router.get("/checklist")
async def get_checklist(category: str = "", db: AsyncSession = Depends(get_db), _: User = Depends(require_specialist)):
    q = select(ChecklistRule)
    if category:
        q = q.where((ChecklistRule.category == category) | (ChecklistRule.category == "all"))
    result = await db.execute(q.order_by(ChecklistRule.category, ChecklistRule.rule_key))
    return [{"id": str(r.id), "rule_key": r.rule_key, "description": r.description, "category": r.category, "is_active": r.is_active} for r in result.scalars().all()]


@router.put("/checklist/{rule_id}")
async def update_rule(rule_id: uuid.UUID, data: RuleUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_specialist)):
    from datetime import datetime, timezone
    result = await db.execute(select(ChecklistRule).where(ChecklistRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Правило не найдено")
    if data.is_active is not None:
        rule.is_active = data.is_active
    if data.description:
        rule.description = data.description
    rule.updated_by = current_user.id
    rule.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": str(rule.id), "rule_key": rule.rule_key, "is_active": rule.is_active}
