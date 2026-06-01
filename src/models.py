from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.database import Base


class TravelProject(Base):
    """Represents a travel project created by the user."""

    __tablename__ = "travel_projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    # Indicates whether the trip has been completed
    is_completed = Column(Boolean, default=False, nullable=False)

    # All places belonging to this project; deleted when the project is deleted
    places = relationship("ProjectPlace", back_populates="project", cascade="all, delete-orphan")


class ProjectPlace(Base):
    """Represents a place associated with a travel project."""

    __tablename__ = "project_places"

    id = Column(Integer, primary_key=True, index=True)
    # Reference to the parent travel project
    project_id = Column(Integer, ForeignKey("travel_projects.id"), nullable=False)
    # External identifier for the place (e.g. from a places API)
    external_id = Column(String, nullable=False)
    notes = Column(String, nullable=True)
    # Indicates whether the user has already visited this place
    is_visited = Column(Boolean, default=False, nullable=False)

    # Back-reference to the parent project
    project = relationship("TravelProject", back_populates="places")
