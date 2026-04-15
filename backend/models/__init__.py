"""ORM models. Importing this package registers every table on ``Base``."""
from backend.models.league import (
    League,
    LeagueMembership,
    PropBetDefinition,
    ScoringConfig,
)
from backend.models.prediction import (
    PreTourPrediction,
    PropBetAnswer,
    StagePrediction,
)
from backend.models.score import PropBetScore, Score
from backend.models.tour import Rider, Stage, StageResult, Tour, TourRider
from backend.models.user import User

__all__ = [
    "League",
    "LeagueMembership",
    "PropBetDefinition",
    "PreTourPrediction",
    "PropBetAnswer",
    "PropBetScore",
    "Rider",
    "Score",
    "ScoringConfig",
    "Stage",
    "StagePrediction",
    "StageResult",
    "Tour",
    "TourRider",
    "User",
]
