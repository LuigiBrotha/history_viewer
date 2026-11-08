import json
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.storage.models import BattleHints


class PlaceHintOut(BaseModel):
    name: str
    lat: float
    lng: float
    kind: str


class BattleHintsOut(BaseModel):
    hints: list[PlaceHintOut]


class RequestHandler:
    """The Plaatshints of one Veldslag, asked for when it is selected; none is an empty list."""

    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/battles/hints/{title:path}", name="battles_hints")
    async def handle_request(self, title: str) -> BattleHintsOut:
        async with self.session_factory() as session:
            found = await session.scalar(select(BattleHints.hints_json).where(BattleHints.battle == title))
        return BattleHintsOut(hints=[PlaceHintOut(**hint) for hint in json.loads(found or "[]")])
