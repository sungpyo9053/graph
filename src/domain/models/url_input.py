from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from src.domain.models.discovery import SearchQuery
from src.services.discovery.query_plan import infer_lane_from_query


class VerifiedUrlEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    title: str
    source_type: str
    discovered_via_query: str
    published_at: datetime | None = None


class VerifiedUrlInput(BaseModel):
    label: str
    market: str = Field(default="KR", min_length=2, max_length=2)
    language: str = Field(default="ko", min_length=2, max_length=5)
    verified_by: str
    verified_at: datetime
    urls: list[VerifiedUrlEntry] = Field(min_length=10, max_length=30)

    @model_validator(mode="after")
    def validates_raw_urls(self) -> VerifiedUrlInput:
        if len({str(item.url) for item in self.urls}) != len(self.urls):
            raise ValueError("verified URL input contains duplicate URLs")
        return self

    def query_plan(self) -> list[SearchQuery]:
        queries: dict[str, SearchQuery] = {}
        for index, item in enumerate(self.urls, start=1):
            key = item.discovered_via_query.strip()
            if key not in queries:
                queries[key] = SearchQuery(
                    query=item.discovered_via_query,
                    theme=f"raw-query-{index}",
                    lane=infer_lane_from_query(item.discovered_via_query),
                )
        return list(queries.values())
