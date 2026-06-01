"""
Comprehensive test suite for the Travel Planner API.

All tests use an isolated in-memory SQLite database and mock the external
Art Institute of Chicago API (api.artic.edu) so no network access is required.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, patch

from src.database import Base, get_db
from src.main import app

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

# StaticPool ensures all sessions share a single connection, which is required
# for in-memory SQLite: each new connection would otherwise see an empty DB.
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


def _override_get_db():
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db():
    """Create all tables before each test and drop them after for full isolation."""
    Base.metadata.create_all(bind=_test_engine)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture(autouse=True)
def mock_external_api():
    """Stub out validate_external_place_id so tests never hit api.artic.edu."""
    _mock = AsyncMock(return_value=True)
    with patch("src.routers.places.validate_external_place_id", _mock), \
         patch("src.routers.projects.validate_external_place_id", _mock):
        yield _mock


@pytest_asyncio.fixture
async def client():
    """Async HTTP client wired directly to the FastAPI ASGI app (no real server)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_project(client: AsyncClient, name: str = "Test Trip", **kwargs) -> dict:
    payload = {"name": name, **kwargs}
    r = await client.post("/projects/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def _add_place(client: AsyncClient, project_id: int, external_id: str, **kwargs):
    payload = {"external_id": external_id, **kwargs}
    return await client.post(f"/projects/{project_id}/places/", json=payload)


# ---------------------------------------------------------------------------
# 1. Creating a travel project
# ---------------------------------------------------------------------------

class TestCreateProject:
    async def test_returns_201_with_correct_fields(self, client):
        r = await client.post(
            "/projects/",
            json={"name": "Paris Trip", "description": "City of Lights tour"},
        )

        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Paris Trip"
        assert data["description"] == "City of Lights tour"
        assert data["is_completed"] is False
        assert data["places"] == []
        assert "id" in data

    async def test_project_appears_in_list(self, client):
        await _create_project(client, name="Rome Trip")

        r = await client.get("/projects/")
        assert r.status_code == 200
        assert any(p["name"] == "Rome Trip" for p in r.json())

    async def test_project_with_initial_nested_places(self, client):
        r = await client.post(
            "/projects/",
            json={
                "name": "Amsterdam Trip",
                "places": [{"external_id": "artwork-1"}, {"external_id": "artwork-2"}],
            },
        )

        assert r.status_code == 201
        assert len(r.json()["places"]) == 2


# ---------------------------------------------------------------------------
# 2. Preventing duplicate external_id within the same project
# ---------------------------------------------------------------------------

class TestDuplicateExternalId:
    async def test_adding_duplicate_place_returns_400(self, client):
        project = await _create_project(client)
        project_id = project["id"]

        r = await _add_place(client, project_id, "artwork-99")
        assert r.status_code == 201

        r = await _add_place(client, project_id, "artwork-99")
        assert r.status_code == 400
        assert "artwork-99" in r.json()["detail"]

    async def test_same_external_id_allowed_across_different_projects(self, client):
        p1 = await _create_project(client, name="Trip A")
        p2 = await _create_project(client, name="Trip B")

        r1 = await _add_place(client, p1["id"], "artwork-shared")
        r2 = await _add_place(client, p2["id"], "artwork-shared")

        assert r1.status_code == 201
        assert r2.status_code == 201

    async def test_duplicate_in_initial_places_list_returns_400(self, client):
        r = await client.post(
            "/projects/",
            json={
                "name": "Trip",
                "places": [
                    {"external_id": "artwork-dup"},
                    {"external_id": "artwork-dup"},
                ],
            },
        )

        assert r.status_code == 400
        assert "artwork-dup" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Enforcing the maximum limit of 10 places
# ---------------------------------------------------------------------------

class TestMaxPlacesLimit:
    async def test_exactly_ten_places_accepted(self, client):
        project = await _create_project(client)
        project_id = project["id"]

        for i in range(10):
            r = await _add_place(client, project_id, f"artwork-{i}")
            assert r.status_code == 201, f"Expected 201 on place {i}, got {r.status_code}"

    async def test_eleventh_place_returns_400(self, client):
        project = await _create_project(client)
        project_id = project["id"]

        for i in range(10):
            await _add_place(client, project_id, f"artwork-{i}")

        r = await _add_place(client, project_id, "artwork-overflow")
        assert r.status_code == 400
        assert "10" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Automatic completion when all places are marked as visited
# ---------------------------------------------------------------------------

class TestProjectAutoCompletion:
    async def test_project_completes_when_all_places_visited(self, client):
        project = await _create_project(client)
        project_id = project["id"]

        r1 = await _add_place(client, project_id, "artwork-A")
        r2 = await _add_place(client, project_id, "artwork-B")
        place1_id = r1.json()["id"]
        place2_id = r2.json()["id"]

        # Visit first place — project should still be incomplete
        await client.put(f"/places/{place1_id}", json={"is_visited": True})
        r = await client.get(f"/projects/{project_id}")
        assert r.json()["is_completed"] is False

        # Visit second (last) place — project must flip to completed
        await client.put(f"/places/{place2_id}", json={"is_visited": True})
        r = await client.get(f"/projects/{project_id}")
        assert r.json()["is_completed"] is True

    async def test_single_place_project_completes_on_visit(self, client):
        project = await _create_project(client)
        project_id = project["id"]

        r = await _add_place(client, project_id, "artwork-solo")
        place_id = r.json()["id"]

        await client.put(f"/places/{place_id}", json={"is_visited": True})

        r = await client.get(f"/projects/{project_id}")
        assert r.json()["is_completed"] is True

    async def test_project_without_places_stays_incomplete(self, client):
        project = await _create_project(client)

        r = await client.get(f"/projects/{project['id']}")
        assert r.json()["is_completed"] is False


# ---------------------------------------------------------------------------
# 5. Preventing project deletion if any place is visited
# ---------------------------------------------------------------------------

class TestDeleteProjectWithVisitedPlace:
    async def test_delete_blocked_when_place_is_visited(self, client):
        project = await _create_project(client)
        project_id = project["id"]

        r = await _add_place(client, project_id, "artwork-1")
        place_id = r.json()["id"]

        await client.put(f"/places/{place_id}", json={"is_visited": True})

        r = await client.delete(f"/projects/{project_id}")
        assert r.status_code == 400
        assert "visited" in r.json()["detail"].lower()

    async def test_delete_succeeds_when_no_place_visited(self, client):
        project = await _create_project(client)
        project_id = project["id"]

        await _add_place(client, project_id, "artwork-1")

        r = await client.delete(f"/projects/{project_id}")
        assert r.status_code == 204

        r = await client.get(f"/projects/{project_id}")
        assert r.status_code == 404

    async def test_delete_empty_project_succeeds(self, client):
        project = await _create_project(client)

        r = await client.delete(f"/projects/{project['id']}")
        assert r.status_code == 204