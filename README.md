# Grand Tour Guessers

A fantasy cycling league app for UCI World Tour grand tours (Giro d'Italia,
Tour de France, Vuelta a España). A commissioner creates a league, configures
scoring, and invites friends. Players predict stage results, jersey winners,
and answer prop bets. The app pulls actual results from procyclingstats and
scores automatically.

See [plan.md](plan.md) for the full design document.

## Quickstart

```bash
# Install
pip install -e ".[dev]"

# Initialize DB
alembic upgrade head

# Run
uvicorn backend.main:app --reload

# Test
pytest
```

The API is JSON REST. Interactive docs are available at `/docs` once the
server is running.

## Configuration

Copy `.env.example` to `.env` and tweak as needed. For local development the
defaults point at a SQLite file (`gtg.db`). Postgres is supported via
`DATABASE_URL` (SQLAlchemy handles the driver).

## Layout

```
backend/
  main.py              FastAPI app, mounts routers
  config.py            pydantic-settings
  database.py          SQLAlchemy engine + session factory
  models/              ORM models
  api/                 FastAPI routers
  services/            pcs_client, scoring_engine
  schemas/             Pydantic request/response models
alembic/               Migrations
tests/                 pytest suite
```
