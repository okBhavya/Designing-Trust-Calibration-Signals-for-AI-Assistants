import pytest

from app.evaluation import (
    binary_auroc,
    bootstrap_interval,
    calibration_metrics,
    classification_metrics,
    fit_isotonic,
    proportion_confidence_interval,
    risk_coverage,
)


def test_classification_metrics_report_per_class_and_macro_f1():
    result = classification_metrics(
        ["supported", "contradicted", "insufficient_evidence"],
        ["supported", "supported", "insufficient_evidence"],
        ["supported", "contradicted", "insufficient_evidence"],
    )
    assert result.accuracy == pytest.approx(2 / 3)
    assert result.per_class["supported"].precision == pytest.approx(0.5)
    assert result.per_class["contradicted"].recall == 0
    assert result.confusion["contradicted"]["supported"] == 1


def test_auroc_requires_both_binary_classes():
    assert binary_auroc([0, 1, 0, 1], [0.1, 0.9, 0.2, 0.8]) == 1.0
    with pytest.raises(ValueError, match="both positive"):
        binary_auroc([1, 1], [0.1, 0.2])
    with pytest.raises(ValueError, match="finite"):
        binary_auroc([0, 1], [float("nan"), 0.9])


def test_calibration_metrics_keep_empty_bins_and_compute_brier():
    result = calibration_metrics([0, 1, 1, 0], [0.1, 0.9, 0.8, 0.2], bins=4)
    assert result.ece == pytest.approx(0.15)
    assert result.brier == pytest.approx(0.025)
    assert result.bin_counts == (2, 0, 0, 2)


def test_isotonic_calibration_is_monotonic_and_bounded():
    calibrator = fit_isotonic([0, 1, 0, 1], [0.1, 0.2, 0.3, 0.4])
    predictions = calibrator.predict([0.1, 0.2, 0.3, 0.4, 0.9])
    assert predictions == sorted(predictions)
    assert all(0 <= value <= 1 for value in predictions)


def test_isotonic_calibration_pools_tied_scores():
    calibrator = fit_isotonic([0, 1], [0.5, 0.5])
    assert calibrator.predict([0.5]) == [0.5]
    with pytest.raises(ValueError, match="probabilities"):
        fit_isotonic([0, 1], [0.1, 1.1])


def test_risk_coverage_orders_by_confidence():
    result = risk_coverage([True, False, True], [0.2, 0.9, 0.8])
    assert [point.threshold for point in result] == [0.9, 0.8, 0.2]
    assert result[-1].coverage == 1
    with pytest.raises(ValueError, match="bool"):
        risk_coverage([1, 0], [0.5, 0.6])


def test_bootstrap_and_proportion_intervals_are_reproducible():
    result = bootstrap_interval([True, True, False, True], lambda values: sum(values) / len(values), resamples=50)
    assert result.estimate == pytest.approx(0.75)
    assert result.resamples == 50
    assert proportion_confidence_interval(3, 4)[0] >= 0


def test_calibration_rejects_non_finite_probabilities():
    with pytest.raises(ValueError, match="probabilities"):
        calibration_metrics([0, 1], [0.2, float("inf")])
