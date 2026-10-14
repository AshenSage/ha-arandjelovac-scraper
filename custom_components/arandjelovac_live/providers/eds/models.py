"""EDS data is deliberately not a universal event/article model."""
from dataclasses import dataclass
from typing import TypedDict


class Outage(TypedDict):
    date: str
    start: str
    end: str
    start_at: str
    end_at: str
    area: str
    municipality: str
    municipality_original: str
    branch: str
    source_url: str


class Page(TypedDict):
    date: str
    url: str
    rows: int
    matched_rows: int
    outages: list[Outage]


@dataclass(frozen=True)
class EDSSnapshot:
    pages: tuple[Page, ...]
