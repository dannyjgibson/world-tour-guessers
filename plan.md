Grand Tour Guessers — Project Plan
A fantasy cycling league app for UCI World Tour grand tours (Giro d'Italia, Tour de France, Vuelta a España). A commissioner creates a league, configures scoring, and invites friends. Players predict stage results, jersey winners, and answer prop bets. The app pulls actual results from procyclingstats and scores automatically.
Previously managed entirely in spreadsheets. This app exists to automate the scoring and make the game more fun.

1. Domain Model
There are five core entities and four scoring dimensions.
Core Entities
User — A player or commissioner. Identified by display name only. No passwords, no OAuth. Trust model: these are friends sharing invite codes. A user can be in multiple leagues.
Tour — A single edition of a grand tour (e.g., "Giro d'Italia 2026"). Contains a reference to its procyclingstats URL slug for scraping. Has many Stages and many Riders (via a join table).
Stage — One day of racing within a tour. Has a stage number, date, and a PCS slug for result scraping. Stages contain the actual results once imported. After a stage finishes, the commissioner classifies its type (sprint, reduced sprint, breakaway, TT, GC) — this classification is what player stage-type predictions are scored against.
Rider — A professional cyclist. Riders persist across tours (Pogačar exists once, not once per tour). A many-to-many join table (TourRider) tracks which riders started a given tour, their team at that time, and their status (active, abandoned, DSQ, finished). Abandon tracking matters for prop bets.
League — The central organizing unit. A league binds a group of users to a specific tour with a specific scoring configuration. The user who creates it is the commissioner. Other users join via an invite code (random URL-safe token, generated on creation). A league has one ScoringConfig, many PropBetDefinitions, and many player predictions.
Scoring Dimensions
These are the four ways players earn points. All are configurable per league via the ScoringConfig.
1. Stage Picks — Before each stage, players make two predictions:

Stage winner: Pick the rider who will win the stage.
Stage type: Predict what kind of race it will be. Options: sprint, reduced_sprint, breakaway, tt, gc.

These are scored independently — you can nail the type but miss the winner, or vice versa. The commissioner's ScoringConfig defines point values for each.
Example config:
json{
  "stage_winner": 25,
  "stage_type": 10
}
Stage type classification is an open design question. After a stage finishes, someone needs to determine what type of race it actually was. Two approaches:

Commissioner classifies manually — a dropdown in the UI after each stage. Simple, reliable, subjective.
Auto-classify from PCS data — analyze the results (winning margin, number of finishers in the group, profile, etc.) to infer the type. More work to build, but removes a daily chore for the commissioner.

For v1, start with commissioner classification. Auto-classification is a nice Phase 5+ feature — we'd need to study historic results to define the heuristics (e.g., a sprint is when the top 20 finish within X seconds of each other; a breakaway is when the winner's gap to the peloton is > Y minutes).
2. Pre-Tour Predictions — Before the tour starts, each player submits 6 picks:

GC podium (3 picks, ordered): Predicted 1st, 2nd, 3rd in general classification.
Sprint jersey (1 pick): Predicted winner of the points classification.
KOM jersey (1 pick): Predicted winner of the mountains classification.
Youth jersey (1 pick): Predicted winner of the best young rider classification.

All 6 are scored at tour end against the final standings. The commissioner's ScoringConfig defines point values.
Example config:
json{
  "gc_exact_1st": 50,
  "gc_exact_2nd": 35,
  "gc_exact_3rd": 25,
  "gc_on_podium": 10,
  "sprint_jersey": 30,
  "kom_jersey": 30,
  "youth_jersey": 20
}
The gc_on_podium key is a bonus for picking a rider who finishes top 3 but not in the exact position you predicted — commissioner's choice whether to include it.
3. Running Bonus — This is what makes the game interesting during the tour, not just at the end. After each stage, four checks are made against the current jersey holders:

Yellow (GC leader): Does your GC #1 pick (predicted winner) hold it?
Green (sprint): Does your sprint jersey pick hold it?
Polka dots (KOM): Does your KOM jersey pick hold it?
White (youth): Does your youth jersey pick hold it?

Only the GC #1 pick counts for yellow — not the 2nd or 3rd podium picks. This makes the GC winner prediction more valuable than the podium picks, since it earns running points throughout the tour.
Example scenario:

User 1 picks: GC top 3 = Pogačar, Vingegaard, Evenepoel. KOM = Carapaz.
User 2 picks: GC top 3 = Vingegaard, Pogačar, Evenepoel. KOM = Sivakov.
After stage 1: Pogačar in yellow, Carapaz in polka dots.
User 1: +1 (their GC #1 Pogačar is in yellow) + 1 (their KOM pick Carapaz is in polka dots) = 2 points.
User 2: +0 (their GC #1 Vingegaard is NOT in yellow) + 0 (their KOM pick Sivakov is NOT in polka dots) = 0 points.

Example config:
json{
  "yellow_jersey_per_stage": 3,
  "green_jersey_per_stage": 2,
  "polka_dot_jersey_per_stage": 2,
  "white_jersey_per_stage": 1
}
The data needed per stage is: who holds each of the four jerseys after this stage? PCS provides this in the stage results / GC standings.
4. Prop Bets — The creative, freeform dimension. The commissioner invents questions before or during the tour. Players submit open-text answers. Crucially, props are NOT auto-scored. The commissioner reads everyone's answers and manually awards points per player per prop at their discretion.
This is the right design because props are inherently creative and subjective. "GC Country — which country will have the best 3 GC riders, scored XC style" can't be auto-graded against a single correct answer. The commissioner needs to look at the final GC standings, calculate XC-style scores per country, and then award points based on how close each player's answer was.
Each PropBetDefinition has:

A question (free text)
A max point value (so players know the stakes)

Each player submits:

An open text answer

The commissioner awards:

A point value per player per prop (0 up to max, or whatever they decide)

Real examples from a previous league:

"Fighting Spirit (Combative)" — pick the rider who wins the combativity award
"GC Country — which country will have the best 3 GC riders? Scored XC style."
"Highest non-UCI WorldTeam GC rider"
"Roglic Crash Out?" — yes/no style, but still commissioner-judged

The PropBetScore table stores: prop_bet_id, user_id, points_awarded (set by commissioner). This is a separate table from the auto-scored Score table because it follows a different flow (manual entry, not engine-calculated).
The ScoringConfig Design
Scoring rules are data, not code. The ScoringConfig is a one-to-one relationship on League containing three JSON columns: stage_scoring, gc_scoring (includes all jersey final scoring), and running_bonus (per-stage bonus for all 4 jerseys). The scoring engine reads these dicts at evaluation time and interprets the keys.
Prop bet scoring is NOT part of ScoringConfig — it's manually awarded by the commissioner per player per prop.
This means:

Different leagues for the same tour can have totally different scoring.
The commissioner can tweak values and re-run scoring without code changes.
New scoring categories can be added by adding keys to the JSON — no migrations needed.
The engine should treat unknown keys gracefully (ignore them, log a warning).
Props remain fully flexible since the commissioner judges them by hand.

Score Storage
There are two score tables because the scoring flows are fundamentally different:
Score (auto-calculated) — One row per player per stage per league. Contains stage pick points, running bonus points, and a JSON breakdown showing exactly how the score was calculated. Created by the scoring engine. Idempotent: re-running the engine for a stage overwrites previous scores.
PropBetScore (commissioner-awarded) — One row per player per prop bet. Contains the points the commissioner manually awarded after reading the player's answer. Created via the commissioner's prop scoring endpoint.
The leaderboard aggregates both tables: SUM(Score.total) + SUM(PropBetScore.points) per player.
Tour-final scoring (GC podium + jersey predictions vs final standings) happens once at tour end. It could go in either table — it's auto-calculated but only runs once. For simplicity, store it as a Score row tied to the final stage, with the relevant point fields populated.
The breakdown JSON on Score is critical for trust. Players will ask "why did I get X points?" and the breakdown answers that without the commissioner having to explain.

2. Data Flow
Setup Phase (before tour starts)
Commissioner creates Tour (with PCS slug)
  → Imports stages from PCS
  → Imports startlist (riders) from PCS
  → Creates League (with ScoringConfig)
  → Defines prop bets
  → Shares invite code with friends

Players join via invite code
  → Submit 6 pre-tour picks:
      GC podium (1st, 2nd, 3rd), sprint jersey, KOM jersey, youth jersey
  → Answer prop bets that are available pre-tour (open text)
During Tour (per stage)
Before stage: Players submit picks (winning rider + stage type)

Stage happens in real life

After stage:
  → Commissioner (or automated job) imports stage results from PCS
  → This includes: finishing order + current holders of all 4 jerseys
  → Commissioner classifies the stage type (sprint, reduced sprint, breakaway, TT, GC)
  → Commissioner triggers score calculation for that stage
  → Scoring engine evaluates: winner picks, type picks, running bonus (4 jersey checks)
  → Score rows created/updated
  → Leaderboard reflects new totals
  → Commissioner can manually score any prop bets whose outcome is now known
Tour End
Final stage results imported
  → Commissioner triggers final scoring:
      GC podium predictions vs final GC standings
      Sprint/KOM/youth jersey predictions vs final jersey winners
  → Commissioner scores remaining prop bets
  → Final leaderboard is the complete result
PCS Integration Boundary
The procyclingstats scraper is isolated behind a service layer (pcs_client.py). It returns plain dicts, not ORM objects. The API layer transforms those dicts into database records. This means:

If PCS breaks, the commissioner can manually create/update StageResult rows via the API (add a manual result entry endpoint).
The scraper never writes to the DB directly.
We can swap to a different data source without touching the domain logic.


3. Technical Stack

Language: Python 3.11+
Web framework: FastAPI
ORM: SQLAlchemy 2.0 (declarative mapped_column style)
Migrations: Alembic
Database: SQLite for development, Postgres-ready (SQLAlchemy abstracts this)
Race data: procyclingstats Python library (pip installable, scrapes PCS website)
Validation: Pydantic v2 (FastAPI's native validation layer)
HTTP client: httpx (for any direct HTTP needs beyond the PCS library)
Testing: pytest
Linting: ruff
Frontend: TBD — API-first, so any frontend can plug in. Likely React or simple HTML+htmx later.


4. API Surface
All endpoints are JSON REST. Auth is deferred — user identity is passed as a query parameter (user_id) for now.
Users
POST   /users                          — Create a user (display_name, email)
GET    /users                          — List users
GET    /users/{id}                     — Get a user
Tours
POST   /tours                          — Create a tour (name, year, pcs_slug)
GET    /tours                          — List all tours
GET    /tours/{id}                     — Get tour with stages
POST   /tours/{id}/import-stages       — Scrape stages from PCS
POST   /tours/{id}/import-riders       — Scrape startlist from PCS
GET    /tours/{id}/riders              — List riders in the tour
POST   /tours/{id}/stages/{stage_id}/import-results — Scrape a stage's results from PCS
Leagues
POST   /leagues                        — Create league (name, tour_id, scoring config)
                                         Query param: commissioner_id
                                         Generates invite code automatically
GET    /leagues/{id}                   — Get league details
POST   /leagues/{invite_code}/join     — Join a league via invite code
                                         Query param: user_id
PUT    /leagues/{id}/scoring-config    — Update scoring configuration
POST   /leagues/{id}/prop-bets         — Add a prop bet (question, max_points)
GET    /leagues/{id}/prop-bets         — List prop bets with player answers
POST   /leagues/{id}/prop-bets/{pb_id}/score — Commissioner awards points per player
                                         Body: [{"user_id": 1, "points": 15}, ...]
Predictions
POST   /leagues/{id}/predictions/stage         — Submit stage picks (stage_id, rider_id, stage_type)
POST   /leagues/{id}/predictions/pre-tour      — Submit all 6 pre-tour picks:
                                                 gc_1st, gc_2nd, gc_3rd (rider IDs)
                                                 sprint_jersey, kom_jersey, youth_jersey (rider IDs)
POST   /leagues/{id}/predictions/prop-bet      — Submit a prop bet answer (prop_bet_id, answer: open text)
GET    /leagues/{id}/predictions/stage/{stage_id} — View your stage picks
GET    /leagues/{id}/predictions/pre-tour      — View your pre-tour picks
GET    /leagues/{id}/predictions/prop-bets     — View your prop bet answers
All prediction endpoints accept user_id as query param. All are upserts — submitting again replaces the previous pick.
Scoring
POST   /leagues/{id}/score-stage/{stage_id}    — Auto-score stage picks + running bonus (4 jersey checks)
                                                 Requires: results imported, stage type classified
POST   /leagues/{id}/score-tour-final          — Auto-score all pre-tour predictions:
                                                 GC podium + sprint/KOM/youth jerseys vs final standings
POST   /leagues/{id}/stages/{stage_id}/classify — Commissioner sets the actual stage type
GET    /leagues/{id}/leaderboard               — Aggregated standings (auto-scored + prop points)
GET    /leagues/{id}/scores/{stage_id}         — Per-stage score breakdown for all players
GET    /leagues/{id}/scores/{stage_id}/{user_id} — Detailed breakdown for one player

5. Project Structure
grand-tour-guessers/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, mounts all routers
│   ├── config.py            # pydantic-settings, reads from .env
│   ├── database.py          # SQLAlchemy engine, session factory, Base
│   ├── models/
│   │   ├── __init__.py      # Imports all models (for Alembic discovery)
│   │   ├── user.py
│   │   ├── league.py        # League, LeagueMembership, ScoringConfig, PropBetDefinition
│   │   ├── tour.py          # Tour, Stage, Rider, TourRider, StageResult
│   │   ├── prediction.py    # StagePrediction, PreTourPrediction, PropBetAnswer
│   │   └── score.py         # Score (auto-calculated) + PropBetScore (commissioner-awarded)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── users.py
│   │   ├── tours.py
│   │   ├── leagues.py
│   │   ├── predictions.py
│   │   └── scoring.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pcs_client.py    # procyclingstats wrapper, returns plain dicts
│   │   └── scoring_engine.py # Pure functions: predictions + results + config → scores
│   └── schemas/
│       ├── __init__.py      # All Pydantic models (request/response)
├── tests/
│   ├── test_scoring_engine.py  # Unit tests for scoring logic (no DB needed)
│   ├── test_api_tours.py
│   ├── test_api_leagues.py
│   ├── test_api_predictions.py
│   └── conftest.py             # Shared fixtures (test DB, test client)
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── pyproject.toml
├── README.md
└── PLAN.md                  # This file

6. Implementation Phases
Phase 1: Foundation
Set up the repo, models, database, and migrations. No business logic yet — just the skeleton.

 Initialize repo with pyproject.toml, .gitignore, README
 Create config.py (pydantic-settings, DATABASE_URL)
 Create database.py (engine, session, Base, get_db dependency)
 Create all ORM models (user, tour, league, prediction, score)
 Set up Alembic, generate initial migration
 Create main.py FastAPI app (just healthcheck endpoint)
 Verify: alembic upgrade head creates all tables, uvicorn starts

Phase 2: Tour Data Pipeline
Get real race data flowing from PCS into the database.

 Implement pcs_client.py (fetch_tour_stages, fetch_startlist, fetch_stage_results, fetch_gc_standings)
 Implement tours API (create tour, import stages, import riders, import results)
 Test against a real past tour (e.g., 2024 Tour de France) to validate PCS scraping
 Implement manual result entry endpoint (fallback if PCS breaks)

Phase 3: Leagues and Predictions
Let commissioners create leagues and players submit picks.

 Implement users API (create, list)
 Implement leagues API (create with scoring config, join via invite code)
 Implement prop bet CRUD (create, list, view answers)
 Implement commissioner prop bet scoring endpoint (award points per player per prop)
 Implement prediction submission (stage winner + type, pre-tour 6 picks, prop bet answers)
 Implement prediction retrieval (view your own picks)

Phase 4: Scoring Engine
The core business logic — pure functions that turn predictions + results into scores.

 Implement score_stage_picks (winner prediction vs actual winner, type prediction vs classified type)
 Implement score_running_bonus (4 jersey checks: GC #1 vs yellow, sprint pick vs green, KOM pick vs polka dots, youth pick vs white)
 Implement score_tour_final (GC podium predictions vs final GC top 3, each jersey pick vs final jersey winner)
 Implement leaderboard aggregation (auto-scored points + commissioner-awarded prop points)
 Write unit tests for all scoring functions with known inputs/outputs
 Implement scoring API (trigger calculation, stage type classification, view breakdowns, leaderboard)
 Implement stage type classification endpoint for commissioner

Phase 5: Polish and Playtest
Get it actually usable for the next grand tour.

 Add prediction deadline enforcement (stage start time, tour start time)
 Add a "rescore all stages" endpoint for when scoring config changes
 Seed script: load a past tour's data for demo/testing
 Error handling and input validation hardening
 API docs cleanup (FastAPI auto-generates from type hints, but descriptions matter)

Phase 6: Frontend (future)

 Decide on frontend approach (React SPA, htmx, or even just a CLI)
 Leaderboard view
 Prediction submission forms
 Stage results view
 Commissioner admin panel


7. Key Design Decisions
Scoring rules as JSON, not tables. Every commissioner's system is slightly different. Encoding rules as JSON on the ScoringConfig means we never need a migration to support a new scoring category. The engine interprets keys it recognizes and ignores the rest.
Scoring engine is stateless and pure. It takes dicts in, returns dicts out. No database access, no side effects. This makes it trivially testable and means the API layer owns all data loading and persistence.
Scores are derived and idempotent. They can always be recalculated from predictions + results + config. We store them for query performance, but they're never the source of truth.
PCS scraper is isolated. It returns plain dicts. The API layer handles all ORM operations. If PCS breaks, we add a manual entry endpoint — no changes to scoring logic.
No auth for v1. Users are identified by display name. League access is controlled by invite code. This is a friends-only game and we trust the players. Real auth can be layered on later without changing the domain model.
Upsert-style predictions. Submitting a pick for a stage/GC slot/prop that already has a pick replaces it. This avoids "did I already submit?" confusion and simplifies the UI.
Props are commissioner-scored, not auto-scored. The commissioner's creativity in designing props means they can't all be reduced to "match a single correct answer." Instead, the commissioner reads everyone's answers and awards points manually. This keeps the prop system maximally flexible at the cost of a small manual step for the commissioner.

8. Dependencies
# Core
fastapi>=0.110
uvicorn[standard]>=0.27
sqlalchemy>=2.0
alembic>=1.13
pydantic>=2.0
pydantic-settings>=2.0
procyclingstats>=0.1
httpx>=0.27

# Dev
pytest>=8.0
pytest-asyncio>=0.23
ruff>=0.3

9. Open Questions / Future Considerations

Stage type auto-classification: Can we infer sprint/breakaway/GC from PCS result data? Would need to analyze: time gaps between groups, number of riders in the front group, stage profile. Could study a few past tours to build heuristics. Nice Phase 5+ feature — start with commissioner manual classification.
GC podium scoring granularity: The config supports both "exact position" (e.g., you predicted Pogačar 1st and he wins) and "on podium anywhere" bonus (you predicted him 3rd but he wins — still worth something). Commissioner decides via config keys. Should the engine default to one or both?
Prop bet partial credit: Commissioner currently awards a flat point value per player per prop. Could add support for a points scale (e.g., 0/5/10/15) to make partial credit easier. UI concern more than data model concern.
Live scoring: Currently commissioner-triggered. Could automate with a periodic job that checks PCS for new results. Nice-to-have, not MVP.
Multi-tour leagues: Some groups play across all three grand tours in a season. Could add a "season" concept that aggregates across tours. Defer.
Trading / transfers: Some fantasy formats let you swap riders mid-tour. Out of scope for v1.
