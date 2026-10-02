"""Scoring and analytics engine for the rebuilt eConcordia Course Support Scorecard.

The rebuilt model intentionally separates:
1) direct cost metrics,
2) a regression-based expected-support benchmark,
3) current efficiency versus that benchmark,
4) descriptive scale context, and
5) optional longitudinal course-health metrics.

No composite 'vitality', 'pedagogical ROI', or 'scalability' score is used.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import stdev
from typing import Iterable, Optional

from model_config import MODEL_CONFIG

# Convenience aliases. All values originate in model_config.py so the model can
# be updated in one place without hunting through calculation/UI/export code.
COMPLEXITY_MIN = float(MODEL_CONFIG["complexity_scale"]["min"])
COMPLEXITY_MAX = float(MODEL_CONFIG["complexity_scale"]["max"])
COMPLEXITY_DEFAULT = float(MODEL_CONFIG["complexity_scale"]["default"])

_EXPECTED = MODEL_CONFIG["expected_support"]
_REGRESSION = _EXPECTED["regression"]
MODEL_INTERCEPT = float(_REGRESSION["intercept"])
MODEL_COMPLEXITY_COEF = float(_REGRESSION["complexity_coefficient"])
MODEL_ENROLLMENT_COEF = float(_REGRESSION["enrollment_coefficient"])
MODEL_R2 = float(_REGRESSION["r_squared"])
OPERATING_BASELINE_HOURS = float(_EXPECTED["minimum_hours"])

SCALE_BANDS = MODEL_CONFIG["enrollment_scale_bands"]
HISTORY_MIN_RUNS_FOR_CHANGE = int(MODEL_CONFIG["history"]["minimum_runs_for_change"])
HISTORY_MIN_RUNS_FOR_TREND = int(MODEL_CONFIG["history"]["minimum_runs_for_trend"])
STABILITY_MAX_SCORE = float(MODEL_CONFIG["history"]["stability_max_score"])
STABILITY_SD_PENALTY = float(MODEL_CONFIG["history"]["stability_sd_penalty"])


@dataclass
class Inputs:
    enrollment: float = float(MODEL_CONFIG["defaults"]["enrollment"])
    hours: float = float(MODEL_CONFIG["defaults"]["hours"])
    complexity: float = COMPLEXITY_DEFAULT
    satisfaction: Optional[float] = float(MODEL_CONFIG["defaults"]["satisfaction"])
    hourly_rate: float = float(MODEL_CONFIG["defaults"]["hourly_rate"])
    tech_severity: Optional[int] = None
    team_severity: Optional[int] = None


@dataclass
class HistoricalRun:
    label: str
    enrollment: Optional[float] = None
    hours: Optional[float] = None
    complexity: Optional[float] = None
    satisfaction: Optional[float] = None
    enabled: bool = True


def _clean_float(value, minimum: Optional[float] = None, maximum: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None:
        x = max(minimum, x)
    if maximum is not None:
        x = min(maximum, x)
    return x


def _clean_complexity(value) -> Optional[int]:
    """Normalize complexity to the whole-number 1-10 scale used to fit the model."""
    x = _clean_float(value, COMPLEXITY_MIN, COMPLEXITY_MAX)
    if x is None:
        return None
    # UI inputs are dropdowns, but normalize API values defensively as well.
    return max(int(COMPLEXITY_MIN), min(int(COMPLEXITY_MAX), int(x + 0.5)))


def regression_prediction_hours(enrollment: float, complexity: float) -> float:
    """Raw fitted regression prediction before the operational minimum is applied."""
    return (
        MODEL_INTERCEPT
        + MODEL_COMPLEXITY_COEF * complexity
        + MODEL_ENROLLMENT_COEF * enrollment
    )


def expected_hours(enrollment: float, complexity: float) -> float:
    """Operational expected-support estimate: regression prediction with a floor."""
    raw = regression_prediction_hours(enrollment, complexity)
    return max(OPERATING_BASELINE_HOURS, raw)


def scale_context(enrollment: float) -> dict:
    for band in SCALE_BANDS:
        lower = float(band["min"])
        upper = band["max"]
        label = band["label"]
        observed_per10 = band["observed_hours_per_10"]
        in_band = enrollment >= lower and (upper is None or enrollment < float(upper))
        if in_band:
            if observed_per10 is None:
                return {
                    "band": label,
                    "observed_marginal_hours_per_10": None,
                    "operational_marginal_hours_per_10": None,
                    "interpretation": f"Below {float(upper):g} students, the portfolio data are treated as an operating-baseline regime rather than a scalability regime.",
                }
            observed_per10 = float(observed_per10)
            operational = max(0.0, observed_per10)
            if observed_per10 < 0:
                interp = "Historical enrollment slope is slightly negative; operationally this is interpreted as approximately zero positive SM cost."
            elif operational < 1:
                interp = "Historical marginal SM cost is low at this enrollment scale."
            else:
                interp = "Historical marginal SM cost remains measurable at this enrollment scale."
            return {
                "band": label,
                "observed_marginal_hours_per_10": observed_per10,
                "operational_marginal_hours_per_10": operational,
                "interpretation": interp,
            }
    raise RuntimeError("Scale band lookup failed")


def _linear_slope(values: list[float]) -> Optional[float]:
    """Slope of values against equally spaced run numbers 1..n."""
    n = len(values)
    if n < 2:
        return None
    xs = list(range(1, n + 1))
    xbar = sum(xs) / n
    ybar = sum(values) / n
    denom = sum((x - xbar) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((x - xbar) * (y - ybar) for x, y in zip(xs, values)) / denom


def _historical_row(run: HistoricalRun) -> Optional[dict]:
    if not run.enabled:
        return None
    e = _clean_float(run.enrollment, 0)
    h = _clean_float(run.hours, 0)
    c = _clean_complexity(run.complexity)
    s = _clean_float(run.satisfaction, 0, 100)
    if e is None or h is None or c is None:
        return None
    raw_exp = regression_prediction_hours(e, c)
    exp = max(OPERATING_BASELINE_HOURS, raw_exp)
    variance_h = h - exp
    variance_pct = (variance_h / exp * 100) if exp else None
    efficiency_ratio = (exp / h * 100) if h > 0 else None
    return {
        "label": run.label,
        "enrollment": e,
        "hours": h,
        "complexity": c,
        "satisfaction": s,
        "regression_prediction_hours": raw_exp,
        "expected_hours": exp,
        "expected_support_floor_applied": raw_exp < OPERATING_BASELINE_HOURS,
        "variance_hours": variance_h,
        "variance_pct": variance_pct,
        "efficiency_ratio": efficiency_ratio,
    }


def history_analytics(current: dict, historical_runs: Iterable[HistoricalRun]) -> dict:
    # User enters Previous 3 -> Previous 2 -> Previous 1; current is appended last.
    rows: list[dict] = []
    for run in historical_runs:
        row = _historical_row(run)
        if row is not None:
            rows.append(row)

    current_row = {
        "label": "Current",
        "enrollment": current["enrollment"],
        "hours": current["hours"],
        "complexity": current["complexity"],
        "satisfaction": current["satisfaction"],
        "regression_prediction_hours": current["regression_prediction_hours"],
        "expected_hours": current["expected_hours"],
        "expected_support_floor_applied": current["expected_support_floor_applied"],
        "variance_hours": current["support_variance_hours"],
        "variance_pct": current["support_variance_pct"],
        "efficiency_ratio": current["efficiency_ratio"],
    }
    rows.append(current_row)

    n = len(rows)
    result = {
        "rows": rows,
        "n_runs": n,
        "history_level": "N/A" if n < HISTORY_MIN_RUNS_FOR_CHANGE else ("Limited history" if n < HISTORY_MIN_RUNS_FOR_TREND else ("Developing trend" if n == HISTORY_MIN_RUNS_FOR_TREND else "Four-run trend")),
        "support_drift_pp_per_run": None,
        "support_variance_change_pp": None,
        "complexity_change": None,
        "satisfaction_change_pp": None,
        "enrollment_change_pct": None,
        "efficiency_stability_sd_pp": None,
        "efficiency_stability_score_pct": None,
        "oldest_label": rows[0]["label"] if n > 1 else None,
    }

    if n < HISTORY_MIN_RUNS_FOR_CHANGE:
        return result

    oldest = rows[0]
    current_row = rows[-1]
    result["support_variance_change_pp"] = current_row["variance_pct"] - oldest["variance_pct"]
    result["complexity_change"] = current_row["complexity"] - oldest["complexity"]
    if oldest["enrollment"] > 0:
        result["enrollment_change_pct"] = (current_row["enrollment"] - oldest["enrollment"]) / oldest["enrollment"] * 100

    sat_rows = [r for r in rows if r["satisfaction"] is not None]
    if len(sat_rows) >= 2:
        result["satisfaction_change_pp"] = sat_rows[-1]["satisfaction"] - sat_rows[0]["satisfaction"]

    if n >= HISTORY_MIN_RUNS_FOR_TREND:
        variances = [r["variance_pct"] for r in rows]
        result["support_drift_pp_per_run"] = _linear_slope(variances)
        sd = stdev(variances)
        result["efficiency_stability_sd_pp"] = sd
        result["efficiency_stability_score_pct"] = max(
            0.0,
            min(STABILITY_MAX_SCORE, STABILITY_MAX_SCORE - (sd * STABILITY_SD_PENALTY)),
        )

    return result


def calculate(i: Inputs, historical_runs: Optional[Iterable[HistoricalRun]] = None) -> dict:
    enrollment = _clean_float(i.enrollment, 0) or 0.0
    hours = _clean_float(i.hours, 0) or 0.0
    complexity = _clean_complexity(i.complexity) or int(COMPLEXITY_MIN)
    satisfaction = _clean_float(i.satisfaction, 0, 100)
    rate = _clean_float(i.hourly_rate, 0) or 0.0

    total_cost = hours * rate
    cost_per_student = total_cost / enrollment if enrollment > 0 else None
    raw_effort_minutes = (hours / enrollment * 60) if enrollment > 0 else None

    baseline_adjusted_hours = max(0.0, hours - OPERATING_BASELINE_HOURS)
    baseline_adjusted_minutes_per_student = (
        baseline_adjusted_hours / enrollment * 60 if enrollment > 0 else None
    )
    variable_support_cost_per_student = (
        baseline_adjusted_hours * rate / enrollment if enrollment > 0 else None
    )

    satisfaction_ratio = satisfaction / 100 if satisfaction is not None else None
    cost_per_satisfied_student = None
    if enrollment > 0 and satisfaction_ratio is not None and satisfaction_ratio > 0:
        cost_per_satisfied_student = total_cost / (enrollment * satisfaction_ratio)

    raw_exp = regression_prediction_hours(enrollment, complexity)
    exp = max(OPERATING_BASELINE_HOURS, raw_exp)
    variance_h = hours - exp
    variance_pct = variance_h / exp * 100 if exp else None
    efficiency_ratio = exp / hours * 100 if hours > 0 else None
    benchmark_cost_difference = variance_h * rate

    scale = scale_context(enrollment)

    current = {
        "enrollment": enrollment,
        "hours": hours,
        "complexity": complexity,
        "satisfaction": satisfaction,
        "hourly_rate": rate,
        "total_cost": total_cost,
        "cost_per_student": cost_per_student,
        "raw_effort_minutes_per_student": raw_effort_minutes,
        "operating_baseline_hours": OPERATING_BASELINE_HOURS,
        "baseline_adjusted_hours": baseline_adjusted_hours,
        "baseline_adjusted_minutes_per_student": baseline_adjusted_minutes_per_student,
        "variable_support_cost_per_student": variable_support_cost_per_student,
        "cost_per_satisfied_student": cost_per_satisfied_student,
        "regression_prediction_hours": raw_exp,
        "expected_hours": exp,
        "expected_support_floor_applied": raw_exp < OPERATING_BASELINE_HOURS,
        "support_variance_hours": variance_h,
        "support_variance_pct": variance_pct,
        "efficiency_ratio": efficiency_ratio,
        "benchmark_cost_difference": benchmark_cost_difference,
        "model_intercept": MODEL_INTERCEPT,
        "complexity_coef": MODEL_COMPLEXITY_COEF,
        "enrollment_coef": MODEL_ENROLLMENT_COEF,
        "model_r2": MODEL_R2,
        "complexity_component_hours": MODEL_COMPLEXITY_COEF * complexity,
        "enrollment_component_hours": MODEL_ENROLLMENT_COEF * enrollment,
        "complexity_hours_per_point": MODEL_COMPLEXITY_COEF,
        "enrollment_hours_per_100": MODEL_ENROLLMENT_COEF * 100,
        "scale_context": scale,
        "context_severity": (
            (int(i.tech_severity) if i.tech_severity is not None else 0)
            + (int(i.team_severity) if i.team_severity is not None else 0)
        ) or None,
    }

    history = history_analytics(current, historical_runs or [])

    # Fact-based key insights; no composite score or arbitrary grade.
    insights: list[str] = []
    if raw_exp < OPERATING_BASELINE_HOURS:
        insights.append(
            f"The raw regression prediction is {raw_exp:.1f} hours, below the {OPERATING_BASELINE_HOURS:g}-hour minimum operating baseline; Expected Support is therefore set to {OPERATING_BASELINE_HOURS:g} hours."
        )
    if variance_pct is not None:
        if variance_pct > 0:
            insights.append(f"Current SM workload is {abs(variance_pct):.1f}% above the model benchmark ({abs(variance_h):.1f} additional hours).")
        elif variance_pct < 0:
            insights.append(f"Current SM workload is {abs(variance_pct):.1f}% below the model benchmark ({abs(variance_h):.1f} fewer hours).")
        else:
            insights.append("Current SM workload is exactly on the model benchmark.")
    if scale["operational_marginal_hours_per_10"] is None:
        insights.append("This enrollment is in the micro-course operating-baseline regime; marginal scalability is not estimated.")
    else:
        insights.append(
            f"At this enrollment scale, the historical portfolio shows about {scale['operational_marginal_hours_per_10']:.2f} additional SM hours per 10 additional students, controlling for complexity."
        )
    if history["n_runs"] >= HISTORY_MIN_RUNS_FOR_CHANGE:
        ev = history["enrollment_change_pct"]
        cv = history["complexity_change"]
        sv = history["support_variance_change_pp"]
        pieces = []
        if ev is not None:
            pieces.append(f"enrollment {ev:+.1f}%")
        if cv is not None:
            pieces.append(f"complexity {cv:+.1f}")
        if sv is not None:
            pieces.append(f"support variance {sv:+.1f}%")
        if pieces:
            insights.append("Since the oldest entered run: " + ", ".join(pieces) + ".")

    current["history"] = history
    current["insights"] = insights
    return current
