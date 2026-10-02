from math import isclose

from model_config import MODEL_CONFIG
from scoring import (
    HistoricalRun,
    Inputs,
    calculate,
    expected_hours,
    regression_prediction_hours,
)


def test_raw_regression_prediction():
    reg = MODEL_CONFIG["expected_support"]["regression"]
    got = regression_prediction_hours(120, 6)
    expected = (
        reg["intercept"]
        + reg["complexity_coefficient"] * 6
        + reg["enrollment_coefficient"] * 120
    )
    assert isclose(got, expected, rel_tol=1e-12)


def test_expected_support_applies_minimum_floor():
    baseline = MODEL_CONFIG["expected_support"]["minimum_hours"]
    raw = regression_prediction_hours(6, 1)
    assert raw < baseline
    assert expected_hours(6, 1) == baseline


def test_expected_support_keeps_regression_when_above_floor():
    raw = regression_prediction_hours(120, 6)
    assert raw > MODEL_CONFIG["expected_support"]["minimum_hours"]
    assert isclose(expected_hours(120, 6), raw, rel_tol=1e-12)


def test_current_metrics():
    r = calculate(Inputs(enrollment=120, hours=45, complexity=6, satisfaction=85, hourly_rate=35))
    assert isclose(r["total_cost"], 1575)
    assert isclose(r["cost_per_student"], 13.125)
    assert isclose(r["baseline_adjusted_hours"], 25)
    assert isclose(r["baseline_adjusted_minutes_per_student"], 12.5)
    assert r["history"]["n_runs"] == 1
    assert r["history"]["support_drift_pp_per_run"] is None


def test_optional_history_and_na():
    history = [
        HistoricalRun("Previous 3", 80, 40, 5, 80, True),
        HistoricalRun("Previous 2", None, None, None, None, False),
        HistoricalRun("Previous 1", 100, 42, 5, None, True),
    ]
    r = calculate(Inputs(enrollment=120, hours=45, complexity=6, satisfaction=85, hourly_rate=35), history)
    # 2 prior valid runs + current
    assert r["history"]["n_runs"] == 3
    assert r["history"]["support_drift_pp_per_run"] is not None
    assert r["history"]["efficiency_stability_score_pct"] is not None
    assert 0 <= r["history"]["efficiency_stability_score_pct"] <= 100
    # Satisfaction trend uses oldest available and current, skipping N/A.
    assert r["history"]["satisfaction_change_pp"] == 5


def test_high_scale_negative_slope_is_operationally_zero():
    r = calculate(Inputs(enrollment=800, hours=70, complexity=6, satisfaction=85, hourly_rate=35))
    assert r["scale_context"]["observed_marginal_hours_per_10"] < 0
    assert r["scale_context"]["operational_marginal_hours_per_10"] == 0


def test_complexity_is_normalized_to_whole_number_scale():
    r = calculate(Inputs(enrollment=120, hours=45, complexity=5.4, satisfaction=85, hourly_rate=35))
    assert r["complexity"] == 5
    r2 = calculate(Inputs(enrollment=120, hours=45, complexity=5.6, satisfaction=85, hourly_rate=35))
    assert r2["complexity"] == 6


def test_complexity_model_metadata_matches_verified_1_to_10_refit():
    cfg = MODEL_CONFIG["complexity_scale"]
    reg = MODEL_CONFIG["expected_support"]["regression"]
    assert cfg["min"] == 1
    assert cfg["max"] == 10
    assert cfg["step"] == 1
    assert reg["sample_size"] == 87
    assert isclose(reg["complexity_coefficient"], 5.098687872867209, rel_tol=1e-12)
