# Travel Planner API

A FastAPI-based RESTful API for planning trips. Projects group places of interest sourced from the [Art Institute of Chicago API](https://api.artic.edu/docs/). When every place in a project has been visited, the project is automatically marked as completed.

---

## Project Structure

```
travel_planner/
├── src/
│   ├── database.py       # SQLAlchemy engine, session factory, and get_db dependency
│   ├── main.py           # Application entry point; table creation on startup
│   ├── models.py         # SQLAlchemy ORM models (TravelProject, ProjectPlace)
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── services.py       # External API integration (place ID validation)
│   └── routers/
│       ├── projects.py   # Project endpoints
│       └── places.py     # Place endpoints
├── tests/
│   └── test_main.py      # Automated pytest suite (14 tests)
├── Dockerfile
├── docker-compose.yaml
├── pytest.ini
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Run with Docker Compose

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`. The `--reload` flag is enabled inside the container, so any code change synced via the volume mount restarts the server automatically — no rebuild required.

To stop the application:

```bash
docker-compose down
```

---

## API Documentation

FastAPI generates interactive documentation automatically. Once the application is running, open either of the following in your browser:

| Interface | URL |
|-----------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Welcome / health check |
| `POST` | `/projects/` | Create a new project (with optional nested places) |
| `GET` | `/projects/` | List all projects |
| `GET` | `/projects/{project_id}` | Get a project by ID |
| `PUT` | `/projects/{project_id}` | Update project fields |
| `DELETE` | `/projects/{project_id}` | Delete a project (blocked if any place is visited) |
| `POST` | `/projects/{project_id}/places/` | Add a place to a project |
| `GET` | `/projects/{project_id}/places/` | List places for a project |
| `GET` | `/places/{place_id}` | Get a place by ID |
| `PUT` | `/places/{place_id}` | Update place notes or visited status |

---

## Example cURL Requests

### Create a project

```bash
curl -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chicago Art Trip",
    "description": "Exploring the Art Institute of Chicago",
    "start_date": "2026-07-01"
  }'
```

### Create a project with nested places

Each `external_id` must correspond to a valid artwork ID in the Art Institute of Chicago API. At most 10 places can be supplied at creation time.

```bash
curl -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chicago Art Trip",
    "start_date": "2026-07-01",
    "places": [
      {"external_id": "27992", "notes": "A Sunday on La Grande Jatte"},
      {"external_id": "28560", "notes": "American Gothic"}
    ]
  }'
```

### Add a place to an existing project

```bash
curl -X POST http://localhost:8000/projects/1/places/ \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "27992",
    "notes": "A Sunday on La Grande Jatte"
  }'
```

### Mark a place as visited

When all places in a project are visited, `is_completed` on the parent project is automatically set to `true`.

```bash
curl -X PUT http://localhost:8000/places/1 \
  -H "Content-Type: application/json" \
  -d '{"is_visited": true}'
```

### Update project details

```bash
curl -X PUT http://localhost:8000/projects/1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chicago Art Trip 2026",
    "description": "Updated itinerary"
  }'
```

### Delete a project

Returns `400 Bad Request` if any associated place has `is_visited: true`.

```bash
curl -X DELETE http://localhost:8000/projects/1
```

---

## Automated Testing

The test suite lives in `tests/test_main.py` and covers all core business rules. Tests run against an isolated **in-memory SQLite database** — the production `travel.db` file is never touched. Calls to the external Art Institute of Chicago API are mocked, so the suite runs fully offline and completes in under a second.

### Run inside Docker (recommended)

Make sure the container is running (`docker-compose up -d`), then:

```bash
docker-compose exec web pytest
```

For quieter output:

```bash
docker-compose exec web pytest -q
```

For verbose output showing each test name:

```bash
docker-compose exec web pytest -v
```

### Run locally

```bash
pip install -r requirements.txt
pytest
```

### What is tested

| # | Test class | Scenario |
|---|-----------|----------|
| 1 | `TestCreateProject` | Project is created with correct fields; appears in list; accepts nested places at creation time |
| 2 | `TestDuplicateExternalId` | Duplicate `external_id` within a project is rejected; same ID is allowed across different projects |
| 3 | `TestMaxPlacesLimit` | Exactly 10 places are accepted; the 11th is rejected with HTTP 400 |
| 4 | `TestProjectAutoCompletion` | Project flips to `is_completed=true` only after the last place is marked visited |
| 5 | `TestDeleteProjectWithVisitedPlace` | Deletion is blocked when any place is visited; succeeds otherwise |

---

## Business Rules

- A project can have at most **10 places**.
- Each `external_id` must be unique within a project and must resolve to an existing artwork in the Art Institute of Chicago API.
- A project with at least one visited place **cannot be deleted**.
- When the last unvisited place in a project is marked as visited, the project's `is_completed` field is automatically set to `true`.