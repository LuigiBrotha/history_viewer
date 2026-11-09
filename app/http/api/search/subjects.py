from typing import Annotated

from fastapi import APIRouter, Query
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.search.search_service import SearchOut, SearchService

MAX_QUERY_LENGTH = 200


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, search: Annotated[SearchService, Inject()]):
        self.search = search

    @router.get("/api/search", name="search_subjects")
    async def handle_request(self, q: Annotated[str, Query(max_length=MAX_QUERY_LENGTH)]) -> SearchOut:
        """The Onderwerpen whose text holds these words or words like them, best first."""
        return await self.search.search(q)
