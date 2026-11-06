from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.places.photon import PhotonClient, PhotonError
from app.services.storage.place_search_repository import PlaceSearchRepository

MAX_QUERY_LENGTH = 200


class PlaceOut(BaseModel):
    name: str
    sub: str
    lat: float
    lng: float
    bbox: list[float] | None = None


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()],
                 photon: Annotated[PhotonClient, Inject()]):
        self.session_factory = session_factory
        self.photon = photon

    @router.get("/api/places", name="places_search")
    async def search_places(self, q: str = "") -> list[PlaceOut]:
        query = q.strip().lower()
        if not query or len(query) > MAX_QUERY_LENGTH:
            raise HTTPException(status_code=422, detail="Geef een zoekterm van 1 tot 200 tekens.")
        async with self.session_factory() as session:
            repository = PlaceSearchRepository(session)
            results = await repository.get(query)
            if results is None:
                try:
                    results = await self.photon.search(query)
                except PhotonError:
                    raise HTTPException(status_code=503, detail="Plaatsen zoeken mislukt.")
                await repository.put(query, results)
        return [PlaceOut(**result) for result in results]
