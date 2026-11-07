from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from random import Random
from typing import Callable, Sequence


@dataclass(frozen=True)
class ClassMetrics:
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class ClassificationMetrics:
    labels: tuple[str, ...]
    per_class: dict[str, ClassMetrics]
    macro_f1: float
    accuracy: float
    confusion: dict[str, dict[str, int]]


@dataclass(frozen=True)
class CalibrationMetrics:
    ece: float
    brier: float
    bin_counts: tuple[int, ...]


@dataclass(frozen=True)
class RiskCoveragePoint:
    coverage: float
    risk: float
    threshold: float


@dataclass(frozen=True)
class BootstrapInterval:
    estimate: float
    lower: float
    upper: float
    resamples: int


@dataclass(frozen=True)
class IsotonicCalibrator:
    x: tuple[float, ...]
    y: tuple[float, ...]

    def predict(self, values: Sequence[float]) -> list[float]:
        if not self.x:
            raise ValueError("An isotonic calibrator has no fitted observations")
        if any(not isfinite(value) or value < 0 or value > 1 for value in values):
            raise ValueError("Calibration scores must be finite probabilities in [0, 1]")
        return [
            max(0.0, min(1.0, self.y[next(index for index, boundary in enumerate(self.x) if value <= boundary)]))
            if value <= self.x[-1]
            else self.y[-1]
            for value in values
        ]


def _require_equal_length(*values: Sequence[object]) -> None:
    if not values:
        raise ValueError("At least one sequence is required")
    if not values[0]:
        raise ValueError("Evaluation requires at least one observation")
    if any(len(value) != len(values[0]) for value in values[1:]):
        raise ValueError("Evaluation sequences must have equal length")
