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

def binary_auroc(actual: Sequence[int], scores: Sequence[float]) -> float:
    _require_equal_length(actual, scores)
    if any(value not in (0, 1) for value in actual):
        raise ValueError("AUROC labels must be binary 0/1")
    if any(not isfinite(value) for value in scores):
        raise ValueError("AUROC scores must be finite")
    positives = sum(actual)
    negatives = len(actual) - positives
    if not positives or not negatives:
        raise ValueError("AUROC requires both positive and negative observations")
    ordered = sorted(zip(scores, actual))
    rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = (index + 1 + end) / 2
        rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        index = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)

def calibration_metrics(
    actual: Sequence[int],
    probabilities: Sequence[float],
    bins: int = 10,
) -> CalibrationMetrics:
    _require_equal_length(actual, probabilities)
    if bins < 1:
        raise ValueError("bins must be positive")
    if any(value not in (0, 1) for value in actual):
        raise ValueError("Calibration labels must be binary 0/1")
    if any(not isfinite(value) or value < 0 or value > 1 for value in probabilities):
        raise ValueError("Calibration probabilities must be in [0, 1]")
    counts = [0] * bins
    bucket_errors = [0.0] * bins
    bucket_probability = [0.0] * bins
    bucket_outcome = [0.0] * bins
    for outcome, probability in zip(actual, probabilities):
        bucket = min(bins - 1, int(probability * bins))
        counts[bucket] += 1
        bucket_probability[bucket] += probability
        bucket_outcome[bucket] += outcome
    for index, count in enumerate(counts):
        if count:
            bucket_errors[index] = abs(bucket_probability[index] / count - bucket_outcome[index] / count)
    ece = sum(count * error for count, error in zip(counts, bucket_errors)) / len(actual)
    brier = sum((probability - outcome) ** 2 for probability, outcome in zip(probabilities, actual)) / len(actual)
    return CalibrationMetrics(ece=ece, brier=brier, bin_counts=tuple(counts))
