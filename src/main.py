from fastapi import FastAPI

from src.database import Base, engine
from src.routers import places, projects

# Create all SQLite tables on startup if they do not already exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Travel Planner")

app.include_router(projects.router)
app.include_router(places.router)


@app.get("/")
def root():
    """Health-check / welcome endpoint."""
    return {"message": "Welcome to Travel Planner API"}