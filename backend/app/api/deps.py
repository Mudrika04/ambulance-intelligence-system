"""Shared singletons for the API layer."""
from __future__ import annotations

from ..core.config import get_config
from ..database.repository import SQLiteRepository
from ..services.events import EventBus
from ..services.experiments import ExperimentRunner
from ..services.pipeline import Pipeline

_bus = EventBus()
_repo = SQLiteRepository()
_pipeline: Pipeline | None = None
_experiments: ExperimentRunner | None = None


def get_bus() -> EventBus:
    return _bus


def get_repo() -> SQLiteRepository:
    return _repo


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline(get_config(), _bus, _repo)
    return _pipeline


def get_experiments() -> ExperimentRunner:
    global _experiments
    if _experiments is None:
        _experiments = ExperimentRunner(get_config(), _repo)
    return _experiments
