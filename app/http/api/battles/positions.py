
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup.integration.fastapi import WireupRoute

from app.http.loopback import require_loopback
from app.services.battles.known_battles import known_battle_titles
from app.services.storage.battle_position_repository import BattlePositionRepository


class BattlePositionIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class BattlePositionOut(BaseModel):
    title: str
    lat: float
    lng: float


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    @router.get("/api/battles/positions", name="battles_positions")
    async def list_positions(self) -> list[BattlePositionOut]:
        async with self.session_factory() as session:
            rows = await BattlePositionRepository(session).all()
        return [BattlePositionOut(title=title, lat=lat, lng=lng) for title, lat, lng in rows]

    @router.put("/api/battles/positions/{title:path}", name="battles_position_put",
                dependencies=[Depends(require_loopback)])
    async def put_position(self, request: Request, title: str, body: BattlePositionIn) -> BattlePositionOut:
        require_loopback(request)
        if title not in known_battle_titles():
            raise HTTPException(status_code=404, detail="Onbekende veldslag.")
        async with self.session_factory() as session:
            await BattlePositionRepository(session).put(title, body.lat, body.lng)
        return BattlePositionOut(title=title, lat=body.lat, lng=body.lng)

    @router.delete("/api/battles/positions/{title:path}", name="battles_position_delete", status_code=204,
                   dependencies=[Depends(require_loopback)])
    async def delete_position(self, request: Request, title: str) -> Response:
        require_loopback(request)
        async with self.session_factory() as session:
            await BattlePositionRepository(session).delete(title)
        return Response(status_code=204)
