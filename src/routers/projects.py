from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import ProjectPlace, TravelProject
from src.schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from src.services import validate_external_place_id

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    # Validate nested places before touching the database
    if payload.places:
        seen_ids: set[str] = set()
        for place in payload.places:
            if place.external_id in seen_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Duplicate external_id '{place.external_id}' in request.",
                )
            seen_ids.add(place.external_id)
            await validate_external_place_id(place.external_id)

    project = TravelProject(
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
        is_completed=payload.is_completed,
    )
    db.add(project)
    db.flush()  # populate project.id before creating child rows

    if payload.places:
        for place in payload.places:
            db.add(
                ProjectPlace(
                    project_id=project.id,
                    external_id=place.external_id,
                    notes=place.notes,
                    is_visited=place.is_visited,
                )
            )

    db.commit()
    db.refresh(project)
    return project


@router.get("/", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(TravelProject).all()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(TravelProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)
):
    project = db.get(TravelProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    # Apply only the fields that were explicitly supplied in the request body
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(TravelProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    # Prevent deletion when the traveller has already visited at least one place
    if any(place.is_visited for place in project.places):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a project that has visited places.",
        )

    db.delete(project)
    db.commit()