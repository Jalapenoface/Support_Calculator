# eConcordia Course Support Scorecard

The scorecard is designed to answer the following questions:

- **What does a course cost to support?**
- **How much support should a course require, given complexity and enrollment?**
- **Is the current course using more or fewer SM hours than expected?**
- **How do complexity and enrollment affect predicted support?**
- **What value/outcome context is available from satisfaction and cost?**
- **How does the course hold up over repeated offerings?** *(optional history)*
- **What enrollment-scale regime is the course operating in?**

The app intentionally keeps cost, expected support, efficiency, satisfaction, scale context, and longitudinal course health separate rather than collapsing them into a single weighted score.

## Run locally

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Deployed on Render

Build command: `pip install -r requirements.txt`

Start command: `gunicorn app:app`

A `Procfile` and `render.yaml` are included.

---

# Model configuration and maintenance

All model assumptions and fitted parameters are centralized in:

```text
model_config.py
```

This means the application, calculations, interface, PDF export, Excel export, and tests all read the same configuration instead of repeating model constants throughout the code.

The configurable items currently include:

- complexity scale minimum, maximum, step, and default
- minimum operating baseline
- regression intercept
- complexity coefficient
- enrollment coefficient
- model R²
- enrollment-scale bands and marginal workload estimates
- minimum number of runs required for history/trend metrics
- basic interface defaults

### What can be changed directly

Operational settings can be changed directly in `model_config.py`. For example, if the planning minimum changes from 20 to 22 hours, update:

```python
"minimum_hours": 22.0
```

The rest of the app will use that value automatically.

### What must be recalculated first

Some values are outputs of statistical analysis and should **not** simply be edited because a preferred number changes.

If the historical dataset is updated, re-run the relevant analysis before replacing:

- regression intercept
- complexity coefficient
- enrollment coefficient
- R²
- enrollment-band marginal slopes

If the **complexity scale itself changes** — for example from 1–10 to 1–5 — the regression must be re-fitted on that new scale. Do not simply change the scale maximum while keeping the old regression coefficients.

---

# Current inputs

| Input | Meaning |
|---|---|
| Enrollment | Most recent semester enrolled students |
| Total SM Hours | Actual support hours — most recent semester |
| Complexity | Current course complexity on the established whole-number 1–10 scale |
| Satisfaction | Optional student satisfaction percentage based on SOLE survey |
| Hourly Rate | Cost of 1 hour (base + any variable) |
| Operational context | Optional technical/team context; descriptive only — does not affect score |

## Optional history

Up to three prior runs can be entered. Each prior run has:

- enrollment
- actual SM hours
- complexity
- satisfaction *(optional)*

Every prior run can be left **N/A / not included**. Missing data are never converted to zero.

Both **current and historical Complexity** are entered from fixed dropdowns containing only the established whole-number values `1` through `10`. This matches the scale used to fit the Expected Support model and prevents decimals or out-of-range values from being entered.

The current run is already populated from the main inputs, so three prior runs + the current run gives a four-run view.

---

# Core equations

## 1. Total Support Cost

```text
Total Support Cost = Actual SM Hours × Hourly Rate
```

Direct semester labour cost represented by the entered SM hours.

## 2. Cost per Student

```text
Cost / Student = Total Support Cost ÷ Enrollment
```

This is the raw support cost distributed across enrolled students.

## 3. Operating Baseline

Baseline is the minimum number of hours estimated to operate a course regardless of enrollment, complexity, or other factors. The current planning baseline is:

```text
20 SM hours
```

The 20-hour baseline is based on the median observed SM hours for courses with fewer than 20 students and is used as an operational planning minimum. It is not the regression intercept.

This baseline is used in two ways:

1. to separate fixed course-operation requirements from variable support burden; and
2. as the minimum operational **Expected Support** estimate.

It is configurable in `model_config.py`.

## 4. Baseline-Adjusted Support Minutes per Student

```text
Adjusted Support Minutes / Student
= MAX(0, Actual SM Hours − 20) ÷ Enrollment × 60
```

This avoids making very small courses look inefficient simply because a fixed operating cost is divided among very few students.

## 5. Variable Support Cost per Student

```text
Variable Support Cost / Student
= MAX(0, Actual SM Hours − 20) × Hourly Rate ÷ Enrollment
```

This is the variable cost/student after removing the common operating baseline.

## 6. Cost per Satisfied Student

When satisfaction is available:

```text
Cost / Satisfied Student
= Total Support Cost ÷ (Enrollment × Satisfaction Ratio)
```

If satisfaction is N/A or zero, the result is N/A rather than zero.

---

# Expected Support Model

The current model uses the historical multiple regression fitted to the **whole-number 1–10 complexity scale** and enrollment.

The `+5.10 hours per complexity point` shown on the Model Drivers card is therefore **specifically a one-point change on this 1–10 scale** — for example, from complexity 4 to 5 — not a one-point change in the original raw complexity score.

### Verification of the 1–10 complexity coefficient

The historical raw complexity scores were converted to the 1–10 scale using the established calibration:

```text
Complexity 1–10
= 5 + (Raw Complexity − 26.1392045455) ÷ (0.5 × 14.8117428733)
```

The result is rounded to the nearest whole number and capped from 1 to 10. The multiple regression was then re-fitted using those whole-number complexity values plus enrollment across **87 courses**. That refit produced:

```text
Intercept = 7.053248901
Complexity coefficient = 5.098687873
Enrollment coefficient = 0.048554834
R² = 0.433483757
N = 87
```

So the Model Drivers statement is verified: **holding enrollment constant, one additional point on the whole-number 1–10 complexity scale is associated with approximately 5.10 additional expected SM hours.**

## Raw regression prediction

```text
Raw Regression Prediction
= 7.053248901
+ 5.098687873 × Complexity
+ 0.048554834 × Enrollment
```

Historical model fit:

```text
R² = 0.43348 (43.35%)
```

R² means the model explains about 43% of historical variation in SM hours. It is **not prediction accuracy**.

Interpretation of the coefficients, holding the other predictor constant:

```text
+1 complexity point ≈ +5.10 expected SM hours
+100 students ≈ +4.86 expected SM hours
```

The `7.053` intercept is a mathematical regression constant. It represents the model's theoretical value at zero complexity and zero enrollment and is **not** interpreted as the minimum number of hours required to operate a course.

## Operational Expected Support

The regression itself is left unchanged. After the raw regression prediction is calculated, the 20-hour minimum operating baseline is applied:

```text
Expected Support
= MAX(20, Raw Regression Prediction)
```

Example:

```text
Raw regression prediction = 12.4 hours
Expected Support = 20.0 hours
```

If the regression predicts 37.4 hours:

```text
Expected Support = 37.4 hours
```

This creates a hybrid statistical + operational benchmark: the historical regression determines expected workload for ordinary courses, while the operating baseline prevents unrealistically low support estimates for very small/simple courses.

All variance, efficiency, benchmark-cost, and historical trend calculations use **Operational Expected Support**, not an unfloored prediction below 20 hours.

## 7. Support Variance

```text
Support Variance (hours) = Actual SM Hours − Expected Support
```

- positive = course used more hours than the benchmark
- negative = course used fewer hours than the benchmark

## 8. Support Variance %

```text
Support Variance %
= (Actual SM Hours − Expected Support) ÷ Expected Support × 100
```

This is the main normalized measure used for comparing runs over time.

## 9. Efficiency vs Benchmark

```text
Efficiency vs Benchmark
= Expected Support ÷ Actual SM Hours × 100
```

Interpretation:

- `100%` = exactly at benchmark
- `>100%` = fewer hours used than expected
- `<100%` = more hours used than expected

This is not capped and is not mixed with satisfaction or complexity in a composite score.

## 10. Benchmark Cost Difference

```text
Benchmark Cost Difference
= (Actual SM Hours − Expected Support) × Hourly Rate
```

- negative = actual support cost below the model benchmark
- positive = actual support cost above the model benchmark

This is a benchmark difference, not proof of causal savings.

---

# Enrollment Scale Context

Scale context is descriptive and does **not** award points for being large.

The current exploratory portfolio analysis estimates marginal SM workload within enrollment bands while controlling for complexity. The app reports the historical marginal burden as **SM hours per 10 additional students**.

| Enrollment band | Observed marginal SM hours / +10 students |
|---|---:|
| <20 | N/A — operating-baseline regime |
| 20–49 | 4.50 |
| 50–99 | 2.65 |
| 100–199 | 3.12 |
| 200–299 | 0.98 |
| 300–499 | 0.92 |
| 500–699 | 1.36 |
| 700–999 | −0.58 observed → operationally treated as ~0 positive marginal burden |
| 1000+ | −0.11 observed → operationally treated as ~0 positive marginal burden |

Negative high-enrollment slopes are **not** interpreted as students reducing workload. They are interpreted operationally as no measurable positive marginal enrollment burden in those bands.

The band values are exploratory portfolio benchmarks and should not be mistaken for causal thresholds.

The app reads these bands from `model_config.py`, so updated historical band analysis can be inserted in one place.

---

# Course History / Durability Metrics

History is optional.

## Data sufficiency rules

- current run only → longitudinal metrics show **N/A**
- current + 1 prior run → change metrics can be shown; trend/stability remain N/A
- 3 or more total runs → support-drift slope and efficiency stability can be calculated
- satisfaction metrics only use runs where satisfaction is actually entered

The minimum run requirements are configurable in `model_config.py`.

## 11. Support Drift

For every valid run:

```text
Expected_i = MAX(20, regression(Complexity_i, Enrollment_i))
Variance%_i = (Actual_i − Expected_i) ÷ Expected_i × 100
```

With at least three total runs:

```text
Support Drift = slope of Variance% across successive runs
```

Displayed as **% per run** for readability.

- positive slope = support burden is moving upward relative to benchmark
- negative slope = support burden is moving downward relative to benchmark
- near zero = relative support demand is stable

No arbitrary grade is assigned.

## 12. Complexity Change

```text
Complexity Change = Current Complexity − Oldest Entered Complexity
```

Shows whether the course has become structurally more or less complex.

## 13. Satisfaction Change

```text
Satisfaction Change
= Current Satisfaction − Oldest Available Satisfaction
```

Displayed as %. N/A if fewer than two satisfaction values are available.

## 14. Enrollment Change

```text
Enrollment Change %
= (Current Enrollment − Oldest Enrollment) ÷ Oldest Enrollment × 100
```

When viewed alongside complexity and support variance, this shows whether a course has absorbed growth while remaining structurally/support-wise stable.

## 15. Efficiency Stability

With at least three total valid runs, the app first calculates the sample standard deviation of **Support Variance %** across the runs. That raw dispersion is then converted to a simple 0–100% consistency scale:

```text
Efficiency Stability %
= MAX(0, 100 − [SD of Support Variance % × stability penalty])
```

The current configured stability penalty is `1.0`, so the conversion is one-for-one. For example, a standard deviation of `21.3` produces:

```text
100 − 21.3 = 78.7% stability
```

Interpretation:

- `100%` = no run-to-run variation in benchmark-relative support
- lower values = greater variability across offerings
- `0%` = variability is at or above the full 100-point scale

This is a transparent **consistency index**, not a probability or a statistical confidence level. Both the maximum score and the SD penalty are configurable in `model_config.py`.

## 16. Support Variance Change

```text
Support Variance Change
= Current Variance % − Oldest Entered Variance %
```

Displayed with the `%` symbol in the interface. It is a compact before/after view of whether the course is farther above or below benchmark than it used to be.

---

# Value framing

The application does not create a single "value score." Instead it keeps the relevant dimensions visible:

- support cost
- cost/student
- variable support cost/student
- expected vs actual support
- satisfaction
- cost/satisfied student
- benchmark cost difference
- support/complexity/satisfaction trends over time

This lets stakeholders distinguish, for example, a high-satisfaction but resource-intensive course from a low-cost course with poor satisfaction rather than collapsing those cases into the same weighted number.

---

# How the app works

At a high level, each calculation follows this sequence:

```text
Current course inputs
        ↓
Raw regression prediction from complexity + enrollment
        ↓
Apply minimum operating baseline
        ↓
Operational Expected Support
        ↓
Compare Actual SM Hours with Expected Support
        ↓
Cost, variance, efficiency and benchmark-cost metrics
        ↓
Add satisfaction context when available
        ↓
Add enrollment-scale context
        ↓
If prior runs are entered, repeat the same benchmark calculation for each run
        ↓
Calculate support drift, stability and change over time
```

The application deliberately separates **model parameters** from **calculation logic**:

- `model_config.py` = values that may be updated after new analysis
- `scoring.py` = equations and calculation logic
- `app.py` = Flask routes plus PDF/Excel exports
- `templates/index.html` = interactive interface

That separation means future historical recalibration should usually require updating `model_config.py`, not rewriting the calculator.

---

# Files

```text
app.py                 Flask routes + PDF/Excel exports
model_config.py        Central model parameters, scales, baselines and band benchmarks
scoring.py             Calculation and longitudinal-analysis logic
templates/index.html    Interactive scorecard UI
static/style.css        Responsive styling
requirements.txt        Python dependencies
Procfile                Gunicorn startup command
render.yaml             Render deployment config
tests/test_scoring.py   Calculation tests
README.md               Model documentation
```

# Tests

```bash
pip install pytest
python -m pytest -q
```
