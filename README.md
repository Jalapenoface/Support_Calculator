# eConcordia Course Scorecard - Flask App

This project converts the supplied **Strategic Course Auditor / eConcordia Course Scorecard** prototype into a deployable Flask application. It keeps the prototype's scoring logic, adds server-generated PDF and Excel downloads, and centralizes all calculations in `scoring.py` so the browser, PDF, Excel, and tests use the same math.

## Important model note

The equations below are **operational heuristics from the supplied prototype**, not published research formulas or validated institutional benchmarks. The source code provides the equations and threshold values, but it does **not** provide empirical citations or a statistical derivation for constants such as `15`, the `40/40/20` weights, the Vitality weights, or the letter-grade cut points. They should therefore be treated as a transparent starting model and calibrated against historical eConcordia data before high-stakes use.

## Inputs

| Input | Symbol | Meaning |
|---|---:|---|
| Enrollment | `E` | Number of enrolled students. |
| Total SM hours | `H` | Total Student Management/support hours for the semester. |
| Complexity | `C` | Course complexity on a 1-10 scale; higher means more complex. |
| Student satisfaction | `S` | Satisfaction percentage from 0-100. |
| Hourly rate | `R` | Dollar cost per support hour. |
| Technical severity | `T` | Context level 1-5. Does not affect Vitality. |
| Instructional-team severity | `P` | Context level 1-5. Does not affect Vitality. |

## Equations and what each number represents

### 1. Total Support Cost

`Total Cost = H x R`

This is the estimated semester labour cost represented by the entered support hours and hourly rate. Example with the defaults: `45 x $35 = $1,575`.

### 2. Cost per Student

`Cost per Student = Total Cost / E`

This distributes the semester support cost across enrolled students. Default example: `$1,575 / 120 = $13.13` per student.

Interpretation bands copied from the prototype:

- `< $15` = Very Efficient
- `$15 to < $25` = Efficient
- `$25 to < $40` = Moderate
- `>= $40` = High Cost

These are policy/heuristic thresholds; the supplied source does not state an external empirical origin.

### 3. Effort per Student

`Effort Hours per Student = H / E`

`Effort Minutes per Student = (H / E) x 60`

This expresses how much support time the course consumes per enrolled student. Default: `(45 / 120) x 60 = 22.5 minutes`.

Prototype interpretation bands:

- `> 25 min` = Needs Evaluation
- `> 15 to 25 min` = Inefficient
- `> 8 to 15 min` = Efficient
- `<= 8 min` = Very Efficient

### 4. Cost per Satisfied Student

First convert satisfaction to a ratio:

`Satisfaction Ratio = S / 100`

Then:

`Cost per Satisfied Student = Total Cost / (E x Satisfaction Ratio)`

The denominator estimates the number of satisfied students. At 120 students and 85% satisfaction, that is `120 x .85 = 102` estimated satisfied students. The default result is `$1,575 / 102 = $15.44`.

Prototype bands:

- `< $15` = Strong Value
- `$15 to < $25` = Good Value
- `$25 to < $40` = Moderate
- `>= $40` = High Investment

### 5. Pedagogical ROI

`Pedagogical ROI = [S / (C x H)] x 100`

This is **not financial ROI** and should not be interpreted as a monetary return. It is a heuristic satisfaction-to-effort ratio: satisfaction rises the score; complexity and support hours reduce it. Default: `[85 / (6 x 45)] x 100 = 31.48%`.

Prototype bands:

- `> 100` = Excellent Efficiency
- `> 70` = Good Efficiency
- `> 40` = Moderate Efficiency
- `<= 40` = Low Efficiency

Because `S` is already entered as a 0-100 percentage, the final `x 100` creates a scaled index. This is exactly how the supplied prototype calculates it; it is not a conventional ROI percentage.

### 6. Scalability Index

Raw scalability:

`Raw Scalability = E / (C x H)`

Displayed index:

`Scalability Index = min(10, Raw Scalability x 10)`

This rewards serving more students with fewer support hours and lower complexity. The score is capped at 10. Default: `120 / (6 x 45) x 10 = 4.44`, displayed as `4.4`.

Prototype bands:

- `>= 8.0` = Highly Scalable
- `5.0-7.9` = Moderately Scalable
- `2.0-4.9` = Limited Scaling
- `< 2.0` = Not Scalable

### 7. Efficiency Index

First calculate students served per support hour:

`Students per Hour = E / H`

Then calculate the complexity adjustment:

`Complexity Factor = (11 - C) / 10`

At complexity 1 the factor is 1.0; at complexity 10 it is 0.1. This means higher complexity deliberately reduces the efficiency score.

Finally:

`Efficiency Index = min(100, round(Students per Hour x Complexity Factor x 15))`

The constant `15` is a **scaling constant** in the supplied prototype. Its purpose is to map the underlying students-per-hour value into a percentage-like 0-100 display. The source does not document an empirical derivation for 15.

Default: `(120 / 45) x 0.5 x 15 = 20`, so Efficiency Index = `20%`.

### 8. Satisfaction Score

`Satisfaction Score = S`

No transformation is applied. The performance bar simply displays the entered satisfaction percentage.

### 9. Resource Utilization

`Resource Utilization = min(100, round[(Efficiency x 0.4) + (S x 0.4) + ((100 - C x 10) x 0.2)])`

This is a weighted composite:

- **40% Efficiency Index**
- **40% Student Satisfaction**
- **20% inverse complexity**

The inverse-complexity term is `100 - (C x 10)`, so a complexity of 1 contributes 90 before weighting and a complexity of 10 contributes 0.

Default: `(20 x .4) + (85 x .4) + ((100 - 60) x .2) = 8 + 34 + 8 = 50%`.

The 40/40/20 weighting is defined in the prototype but no external derivation is supplied.

### 10. Vitality Score and Letter Grade

`Vitality Score = (Efficiency x 0.3) + (S x 0.5) + ((10 - C) x 2)`

The model gives:

- **30% coefficient to efficiency**
- **50% coefficient to satisfaction**
- up to **18 additional points for lower complexity**, because `(10-C) x 2` ranges from 18 at complexity 1 to 0 at complexity 10.

Default: `(20 x .3) + (85 x .5) + ((10 - 6) x 2) = 6 + 42.5 + 8 = 56.5`, which maps to **B / Satisfactory**.

Grade cut points:

| Vitality score | Grade | Label |
|---:|:---:|---|
| `>= 85` | A+ | Excellent |
| `>= 75` | A | Very Good |
| `>= 65` | B+ | Good Standing |
| `>= 55` | B | Satisfactory |
| `>= 45` | C+ | Needs Attention |
| `>= 35` | C | At Risk |
| `< 35` | F | Critical Review |

Again, these cut points are model rules from the prototype, not academic course grades and not externally validated thresholds.

### 11. Environmental Context Severity

`Context Severity = T + P`

Each context input is 1-5, so the total ranges from 2-10. The prototype explicitly states that this contextual score **does not mathematically affect the Vitality Grade**. It exists to document conditions that may explain support demand.

## Strategic recommendation rules

The prototype also uses simple trigger rules rather than a predictive model:

- Cost/student `> $30` -> High Per-Student Cost
- Satisfaction `< 70%` -> Low Satisfaction Alert
- Complexity `> 7` and hours `< 50` -> Resource Mismatch
- Efficiency `> 80` and satisfaction `> 85%` -> High Performer
- Enrollment `> 150` and hours `< 40` -> Scaling Opportunity
- If none trigger -> Balanced Metrics

These should be reviewed when the underlying score thresholds are calibrated.

## A note about the supplied prototype's displayed defaults

Some hard-coded values visible in the original HTML before JavaScript recalculates are inconsistent with the equations in its `calculateMetrics()` function. This Flask version treats the **calculation code as authoritative**. With the prototype defaults (`E=120`, `H=45`, `C=6`, `S=85`, `R=$35`), the calculated results are:

- Total cost: **$1,575**
- Cost/student: **$13.13**
- Effort/student: **22.5 min**
- Cost/satisfied student: **$15.44**
- Pedagogical ROI: **31.48%**
- Scalability: **4.4/10**
- Efficiency: **20%**
- Resource utilization: **50%**
- Vitality score: **56.5 = B**

## Recommended calibration before institutional use

The next analytical step is to export historical course data and compare the model's outputs against observed support load, satisfaction, course size, and operational outcomes. The constants and cut points can then be replaced with percentiles, regression-derived weights, or institutionally chosen service standards. Keeping all formulas in `scoring.py` makes that calibration straightforward.

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

## Deploy on Render

Push this folder to GitHub and create a Python Web Service. Render can also read `render.yaml`.

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`

The PDF and Excel routes use `POST`, matching the browser buttons. This avoids the GET/POST mismatch that can produce a **405 Method Not Allowed** error on hosted deployments.

## Project structure

```text
app.py                 Flask routes + PDF/Excel export
scoring.py             Single source of truth for equations
requirements.txt       Python dependencies
Procfile               Gunicorn start command
render.yaml            Render deployment definition
templates/index.html   Scorecard interface
static/style.css       Responsive styling
tests/test_scoring.py  Default-value regression test
README.md              Model documentation and deployment guide
```

## Test

```bash
pip install pytest
pytest -q
```
