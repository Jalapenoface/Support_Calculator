"""Central configuration for the eConcordia Course Support Scorecard.

Update model assumptions here rather than throughout the application.

Important:
- Operational settings such as the minimum support floor can be changed directly.
- Regression coefficients and R² should only be replaced after re-fitting the
  historical model.
- If the complexity scale changes (for example 1-10 to 1-5), re-fit the
  regression before changing the scale and coefficients here.
- Enrollment-band slopes are historical portfolio estimates and should be
  replaced when the band analysis is re-run on updated data.
"""

MODEL_CONFIG = {
    "version": "2026-10-01",

    # Input scale used by the current historical model.
    "complexity_scale": {
        "min": 1,
        "max": 10,
        "step": 1,
        "default": 6,
        "whole_numbers_only": True,
        "calibration": {
            "raw_mean": 26.139204545454547,
            "raw_stdev": 14.811742873348363,
            "formula": "5 + (Raw Complexity - Mean) / (0.5 * StDev), rounded and capped 1-10",
        },
    },

    # Expected-support model. The regression is fitted on the 1-10 complexity
    # scale. The operating baseline is an operational floor applied AFTER the
    # raw regression prediction is calculated.
    "expected_support": {
        "minimum_hours": 20.0,
        "regression": {
            "intercept": 7.053248900959058,
            "complexity_coefficient": 5.098687872867209,
            "enrollment_coefficient": 0.048554833837740806,
            "r_squared": 0.4334837571592314,
            "sample_size": 87,
        },
    },

    # Exploratory portfolio scale benchmarks. observed_hours_per_10 is the
    # fitted enrollment effect within the band, expressed as SM hours per +10
    # students while controlling for complexity. Negative high-enrollment
    # values are retained as observed, but operational burden is floored at 0.
    "enrollment_scale_bands": [
        {"min": 0, "max": 20, "label": "Micro / operating-baseline regime", "observed_hours_per_10": None},
        {"min": 20, "max": 50, "label": "20-49", "observed_hours_per_10": 4.502461322},
        {"min": 50, "max": 100, "label": "50-99", "observed_hours_per_10": 2.652777778},
        {"min": 100, "max": 200, "label": "100-199", "observed_hours_per_10": 3.115294238},
        {"min": 200, "max": 300, "label": "200-299", "observed_hours_per_10": 0.977504335},
        {"min": 300, "max": 500, "label": "300-499", "observed_hours_per_10": 0.921479783},
        {"min": 500, "max": 700, "label": "500-699", "observed_hours_per_10": 1.361912344},
        {"min": 700, "max": 1000, "label": "700-999", "observed_hours_per_10": -0.577647229},
        {"min": 1000, "max": None, "label": "1000+", "observed_hours_per_10": -0.111627907},
    ],

    # Rules for optional longitudinal calculations.
    "history": {
        "minimum_runs_for_change": 2,
        "minimum_runs_for_trend": 3,

        # Efficiency Stability is displayed as an intuitive 0-100% consistency
        # index rather than a raw standard deviation. A course with no
        # run-to-run variation in Support Variance % scores 100%. Each 1-point
        # increase in the SD of Support Variance % reduces the score by one
        # point under the current transparent one-for-one conversion.
        "stability_max_score": 100.0,
        "stability_sd_penalty": 1.0,
    },

    # UI defaults only. These are not statistical model parameters.
    "defaults": {
        "enrollment": 120,
        "hours": 45,
        "satisfaction": 85,
        "hourly_rate": 35,
    },
}
