from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Place schemas
# ---------------------------------------------------------------------------

class PlaceCreate(BaseModel):
    external_id: str
    notes: Optional[str] = None
    is_visited: bool = False


class PlaceUpdate(BaseModel):
    external_id: Optional[str] = None
    notes: Optional[str] = None
    is_visited: Optional[bool] = None


class PlaceResponse(BaseModel):
    id: int
    project_id: int
    external_id: str
    notes: Optional[str]
    is_visited: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    is_completed: bool = False
    # Nested places are optional; at most 10 can be supplied at creation time
    places: Optional[List[PlaceCreate]] = Field(default=None, max_length=10)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    is_completed: Optional[bool] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    start_date: Optional[date]
    is_completed: bool
    places: List[PlaceResponse] = []

    model_config = {"from_attributes": True}
