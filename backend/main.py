"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI

from backend.api import leagues, predictions, scoring, tours, users

app = FastAPI(
    title="Grand Tour Guessers",
    description="A fantasy cycling league app for UCI World Tour grand tours.",
    version="0.1.0",
)


@app.get("/healthz", tags=["meta"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(users.router)
app.include_router(tours.router)
app.include_router(leagues.router)
app.include_router(predictions.router)
app.include_router(scoring.router)
app.include_router(scoring.tour_final_router)
