from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import ProjectPlace, TravelProject
from src.schemas import PlaceCreate, PlaceResponse, PlaceUpdate
from src.services import validate_external_place_id

router = APIRouter(tags=["places"])

MAX_PLACES_PER_PROJECT = 10


@router.post("/projects/{project_id}/places/", response_model=PlaceResponse, status_code=201)
async def add_place(
    project_id: int, payload: PlaceCreate, db: Session = Depends(get_db)
):
    project = db.get(TravelProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    if len(project.places) >= MAX_PLACES_PER_PROJECT:
        raise HTTPException(
            status_code=400,
            detail=f"A project cannot have more than {MAX_PLACES_PER_PROJECT} places.",
        )

    # Prevent adding the same external place twice within the same project
    existing_ids = {p.external_id for p in project.places}
    if payload.external_id in existing_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Place with external_id '{payload.external_id}' already exists in this project.",
        )

    await validate_external_place_id(payload.external_id)

    place = ProjectPlace(
        project_id=project_id,
        external_id=payload.external_id,
        notes=payload.notes,
        is_visited=payload.is_visited,
    )
    db.add(place)
    db.commit()
    db.refresh(place)
    return place


@router.get("/projects/{project_id}/places/", response_model=List[PlaceResponse])
def list_places(project_id: int, db: Session = Depends(get_db)):
    project = db.get(TravelProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project.places


@router.get("/places/{place_id}", response_model=PlaceResponse)
def get_place(place_id: int, db: Session = Depends(get_db)):
    place = db.get(ProjectPlace, place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found.")
    return place


@router.put("/places/{place_id}", response_model=PlaceResponse)
def update_place(place_id: int, payload: PlaceUpdate, db: Session = Depends(get_db)):
    place = db.get(ProjectPlace, place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(place, field, value)

    # When a place is marked as visited, check whether the whole project is now complete.
    # A project is considered complete when every one of its places has been visited.
    if update_data.get("is_visited") is True:
        project = db.get(TravelProject, place.project_id)
        if project and all(p.is_visited for p in project.places):
            project.is_completed = True

    db.commit()
    db.refresh(place)
    return place