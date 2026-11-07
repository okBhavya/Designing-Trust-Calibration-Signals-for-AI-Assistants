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

def classification_metrics(
    actual: Sequence[str],
    predicted: Sequence[str],
    labels: Sequence[str],
) -> ClassificationMetrics:
    _require_equal_length(actual, predicted)
    ordered_labels = tuple(labels)
    if not ordered_labels or len(set(ordered_labels)) != len(ordered_labels):
        raise ValueError("labels must contain at least one unique class")
    known = set(ordered_labels)
    if any(value not in known for value in (*actual, *predicted)):
        raise ValueError("Observed labels must be declared in labels")

    confusion = {actual_label: {predicted_label: 0 for predicted_label in ordered_labels} for actual_label in ordered_labels}
    for actual_label, predicted_label in zip(actual, predicted):
        confusion[actual_label][predicted_label] += 1

    per_class: dict[str, ClassMetrics] = {}
    for label in ordered_labels:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[other][label] for other in ordered_labels if other != label)
        false_negative = sum(confusion[label][other] for other in ordered_labels if other != label)
        support = true_positive + false_negative
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = ClassMetrics(precision, recall, f1, support)
    return ClassificationMetrics(
        labels=ordered_labels,
        per_class=per_class,
        macro_f1=sum(metric.f1 for metric in per_class.values()) / len(ordered_labels),
        accuracy=sum(left == right for left, right in zip(actual, predicted)) / len(actual),
        confusion=confusion,
    )
