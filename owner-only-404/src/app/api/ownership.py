"""
Ownership dependency: a resource that is missing and one that belongs to someone else are indistinguishable (404).
Declare as `item=Depends(authorize_item)` on any route with an {item_id} path parameter.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app._stubs import get_current_user
from app._stubs import get_db


async def _owned(item_id: str, user: dict, db: AsyncSession):
    from app._stubs import Item
    item = (await db.execute(
        select(Item).where(Item.id == item_id, Item.user_id == user["user_id"])
    )).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    return item


async def authorize_item(
    request: Request, item_id: str,
    user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await _owned(item_id, user, db)
