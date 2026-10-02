from __future__ import annotations

from datetime import date
from io import BytesIO

from flask import Flask, jsonify, render_template, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from model_config import MODEL_CONFIG

from scoring import (
    Inputs,
    HistoricalRun,
    MODEL_COMPLEXITY_COEF,
    MODEL_ENROLLMENT_COEF,
    MODEL_INTERCEPT,
    MODEL_R2,
    OPERATING_BASELINE_HOURS,
    COMPLEXITY_MIN,
    COMPLEXITY_MAX,
    COMPLEXITY_DEFAULT,
    HISTORY_MIN_RUNS_FOR_TREND,
    calculate,
)

app = Flask(__name__)

TECH = {
    1: "Platform remained stable; support was focused on routine instructional delivery.",
    2: "Minor tool or assessment friction; resolved with routine maintenance.",
    3: "Recurring tool or assessment friction or peak-period issues required reactive support.",
    4: "Major tool or assessment failure or outage materially increased support demand.",
    5: "Critical infrastructure failure severely affected course operations.",
}

TEAM = {
    1: "Instructional team is highly self-sufficient and follows established workflows.",
    2: "Team follows standard workflows with routine checks and limited intervention.",
    3: "Team requires regular guidance or hands-on support with course tools/workflows.",
    4: "Frequent custom requests or late changes create high operational demand.",
    5: "Sustained high-touch support or major workflow mismatch creates intensive overhead.",
}


def _optional_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value):
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def payload():
    d = request.get_json(silent=True) or request.form.to_dict(flat=True)

    i = Inputs(
        enrollment=_optional_float(d.get("enrollment")) if _optional_float(d.get("enrollment")) is not None else float(MODEL_CONFIG["defaults"]["enrollment"]),
        hours=_optional_float(d.get("hours")) if _optional_float(d.get("hours")) is not None else float(MODEL_CONFIG["defaults"]["hours"]),
        complexity=_optional_float(d.get("complexity")) if _optional_float(d.get("complexity")) is not None else COMPLEXITY_DEFAULT,
        satisfaction=_optional_float(d.get("satisfaction")),
        hourly_rate=_optional_float(d.get("hourly_rate")) if _optional_float(d.get("hourly_rate")) is not None else float(MODEL_CONFIG["defaults"]["hourly_rate"]),
        tech_severity=_optional_int(d.get("tech_severity")),
        team_severity=_optional_int(d.get("team_severity")),
    )

    meta = {
        k: str(d.get(k, "") or "")
        for k in ["course_name", "faculty_name", "department", "tech_notes", "team_notes"]
    }

    history_data = d.get("history", []) if isinstance(d, dict) else []
    history = []
    if isinstance(history_data, list):
        for idx, h in enumerate(history_data):
            if not isinstance(h, dict):
                continue
            history.append(
                HistoricalRun(
                    label=str(h.get("label") or f"Previous {len(history_data)-idx}"),
                    enrollment=_optional_float(h.get("enrollment")),
                    hours=_optional_float(h.get("hours")),
                    complexity=_optional_float(h.get("complexity")),
                    satisfaction=_optional_float(h.get("satisfaction")),
                    enabled=bool(h.get("enabled", False)),
                )
            )

    return i, meta, history


def fmt(value, pattern="{:.1f}", na="N/A"):
    if value is None:
        return na
    return pattern.format(value)


@app.get("/")
def index():
    return render_template("index.html", tech=TECH, team=TEAM, model_config=MODEL_CONFIG)


@app.post("/api/calculate")
def api_calculate():
    i, _, history = payload()
    return jsonify(calculate(i, history))


@app.post("/download/pdf")
def download_pdf():
    i, meta, history = payload()
    r = calculate(i, history)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title2",
        parent=styles["Title"],
        textColor=colors.HexColor("#912338"),
        fontSize=19,
        leading=23,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "H2x",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#912338"),
        spaceBefore=12,
        spaceAfter=6,
    )
    small = ParagraphStyle(
        "small",
        parent=styles["BodyText"],
        fontSize=8.2,
        leading=10.5,
        textColor=colors.HexColor("#475569"),
    )

    story = [
        Paragraph("eConcordia Course Support Scorecard", title),
        Paragraph(
            f"{meta['course_name'] or 'Course'} | {meta['faculty_name'] or 'Faculty not entered'} | {meta['department'] or 'Department not entered'}",
            styles["BodyText"],
        ),
        Spacer(1, 10),
    ]

    metrics = [
        ["Metric", "Result", "Meaning"],
        ["Total support cost", f"${r['total_cost']:,.2f}", "Actual entered SM hours × hourly rate"],
        ["Expected support hours", f"{r['expected_hours']:.1f} h", f"Regression prediction with a {OPERATING_BASELINE_HOURS:g}h minimum operating floor"],
        ["Actual vs expected", f"{r['support_variance_hours']:+.1f} h", f"{r['support_variance_pct']:+.1f}% vs benchmark"],
        ["Efficiency vs benchmark", fmt(r['efficiency_ratio'], "{:.1f}%"), "100% = expected workload"],
        ["Cost / student", fmt(r['cost_per_student'], "${:,.2f}"), "Actual support cost per enrolled student"],
        ["Variable support / student", fmt(r['variable_support_cost_per_student'], "${:,.2f}"), f"Cost/student after removing {OPERATING_BASELINE_HOURS:g}h operating baseline"],
        ["Adjusted support minutes / student", fmt(r['baseline_adjusted_minutes_per_student'], "{:.1f} min"), "Variable support after fixed baseline"],
        ["Cost / satisfied student", fmt(r['cost_per_satisfied_student'], "${:,.2f}"), "N/A when satisfaction is unavailable"],
        ["Benchmark cost difference", f"${r['benchmark_cost_difference']:+,.2f}", "Actual support cost minus model-benchmark support cost"],
        ["Enrollment scale", r['scale_context']['band'], "Descriptive scale context, not a performance score"],
        ["Marginal SM burden", fmt(r['scale_context']['operational_marginal_hours_per_10'], "{:.2f} h / +10 students"), "Historical band estimate controlling for complexity"],
    ]
    t = Table(metrics, colWidths=[145, 115, 235], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#912338")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story += [t]

    story += [Paragraph("Model drivers", h2)]
    story += [
        Paragraph(
            f"Raw regression prediction = {MODEL_INTERCEPT:.3f} + {MODEL_COMPLEXITY_COEF:.3f} × Complexity + {MODEL_ENROLLMENT_COEF:.5f} × Enrollment. "
            f"Operational Expected Support = MAX({OPERATING_BASELINE_HOURS:g}, raw regression prediction). "
            f"In this historical model, fitted on the whole-number 1-10 complexity scale, +1 complexity point is associated with about {MODEL_COMPLEXITY_COEF:.1f} additional SM hours and +100 students with about {MODEL_ENROLLMENT_COEF*100:.1f} additional SM hours, holding the other variable constant.",
            styles["BodyText"],
        ),
        Paragraph(f"Historical model R²: {MODEL_R2*100:.1f}% (variation explained, not prediction accuracy).", small),
    ]

    hist = r["history"]
    story += [Paragraph("Course history / durability", h2)]
    if hist["n_runs"] <= 1:
        story += [Paragraph("N/A — no prior course runs were entered.", styles["BodyText"])]
    else:
        history_rows = [["Run", "Enroll.", "Actual h", "Expected support", "Var. %", "Complexity", "Satisfaction"]]
        for row in hist["rows"]:
            history_rows.append([
                row["label"],
                f"{row['enrollment']:.0f}",
                f"{row['hours']:.1f}",
                f"{row['expected_hours']:.1f}",
                f"{row['variance_pct']:+.1f}%",
                f"{row['complexity']:.0f}",
                "N/A" if row["satisfaction"] is None else f"{row['satisfaction']:.0f}%",
            ])
        ht = Table(history_rows, colWidths=[78, 55, 60, 66, 58, 62, 68], repeatRows=1)
        ht.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.8),
            ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#cbd5e1")),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story += [ht, Spacer(1, 6)]
        summary_parts = [
            f"Enrollment change: {fmt(hist['enrollment_change_pct'], '{:+.1f}%')}",
            f"Complexity change: {fmt(hist['complexity_change'], '{:+.1f}')}",
            f"Support variance change: {fmt(hist['support_variance_change_pp'], '{:+.1f}%')}",
            f"Support drift: {fmt(hist['support_drift_pp_per_run'], '{:+.1f}%/run')}",
            f"Satisfaction change: {fmt(hist['satisfaction_change_pp'], '{:+.1f}%')}",
            f"Efficiency stability: {fmt(hist['efficiency_stability_score_pct'], '{:.1f}%')}",
        ]
        story += [Paragraph(" | ".join(summary_parts), small)]

    story += [Paragraph("Key insights", h2)]
    for insight in r["insights"]:
        story += [Paragraph("• " + insight, styles["BodyText"]), Spacer(1, 3)]

    story += [Paragraph("Method note", h2)]
    story += [Paragraph(
        "The support calculator is based on a combination of historical data and other coefficients. All information is available in the Read Me document. "
        f"Expected support uses the historical complexity + enrollment regression with a {OPERATING_BASELINE_HOURS:g}-hour minimum operating floor. Longitudinal metrics are only calculated when enough prior runs are supplied; missing history remains N/A rather than being treated as zero. Model parameters are centralized in model_config.py.",
        small,
    )]

    doc.build(story)
    buf.seek(0)
    name = (meta["course_name"] or "Course-Support-Scorecard").replace("/", "-").replace("\\", "-")
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"{name}-{date.today().isoformat()}.pdf")


@app.post("/download/excel")
def download_excel():
    i, meta, history = payload()
    r = calculate(i, history)

    wb = Workbook()
    ws = wb.active
    ws.title = "Scorecard"
    maroon = "912338"
    dark = "334155"
    light = "F8FAFC"

    ws["A1"] = "eConcordia Course Support Calculator"
    ws["A1"].font = Font(size=18, bold=True, color=maroon)
    ws.merge_cells("A1:C1")

    rows = [
        ("Course", meta["course_name"]),
        ("Faculty", meta["faculty_name"]),
        ("Department", meta["department"]),
        ("", ""),
        ("CURRENT INPUTS", ""),
        ("Enrollment", r["enrollment"]),
        ("Actual SM hours", r["hours"]),
        (f"Complexity ({COMPLEXITY_MIN:g}-{COMPLEXITY_MAX:g})", r["complexity"]),
        ("Satisfaction", None if r["satisfaction"] is None else r["satisfaction"] / 100),
        ("Hourly rate", r["hourly_rate"]),
        ("", ""),
        ("CURRENT RESULTS", ""),
        ("Total support cost", r["total_cost"]),
        ("Raw regression prediction", r["regression_prediction_hours"]),
        ("Expected support hours", r["expected_hours"]),
        ("Support variance hours", r["support_variance_hours"]),
        ("Support variance %", r["support_variance_pct"] / 100),
        ("Efficiency vs benchmark", None if r["efficiency_ratio"] is None else r["efficiency_ratio"] / 100),
        ("Cost / student", r["cost_per_student"]),
        ("Raw effort min / student", r["raw_effort_minutes_per_student"]),
        ("Baseline-adjusted min / student", r["baseline_adjusted_minutes_per_student"]),
        ("Variable support cost / student", r["variable_support_cost_per_student"]),
        ("Cost / satisfied student", r["cost_per_satisfied_student"]),
        ("Benchmark cost difference", r["benchmark_cost_difference"]),
        ("Enrollment scale", r["scale_context"]["band"]),
        ("Marginal SM hours / +10 students", r["scale_context"]["operational_marginal_hours_per_10"]),
    ]

    for rr, (a, b) in enumerate(rows, start=3):
        ws.cell(rr, 1, a)
        ws.cell(rr, 2, b)

    for row_num in [7, 14]:
        ws.cell(row_num, 1).font = Font(bold=True, color="FFFFFF")
        ws.cell(row_num, 1).fill = PatternFill("solid", fgColor=maroon)

    # Formats
    for c in ["B11", "B19", "B20"]:
        ws[c].number_format = "0.0%"
    for c in ["B12", "B15", "B21", "B24", "B25", "B26"]:
        ws[c].number_format = "$#,##0.00"
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 55

    # History sheet
    hs = wb.create_sheet("History")
    hs.append(["Run", "Enrollment", "Actual SM Hours", "Complexity", "Satisfaction", "Expected Support Hours", "Variance Hours", "Variance %", "Efficiency vs Benchmark"])
    for row in r["history"]["rows"]:
        hs.append([
            row["label"], row["enrollment"], row["hours"], row["complexity"],
            None if row["satisfaction"] is None else row["satisfaction"] / 100,
            row["expected_hours"], row["variance_hours"], row["variance_pct"] / 100,
            None if row["efficiency_ratio"] is None else row["efficiency_ratio"] / 100,
        ])
    hs.append([])
    hs.append(["History level", r["history"]["history_level"]])
    hs.append(["Enrollment change", None if r["history"]["enrollment_change_pct"] is None else r["history"]["enrollment_change_pct"] / 100])
    hs.append(["Complexity change", r["history"]["complexity_change"]])
    hs.append(["Support variance change (%)", r["history"]["support_variance_change_pp"]])
    hs.append(["Support drift (%/run)", r["history"]["support_drift_pp_per_run"]])
    hs.append(["Satisfaction change (%)", r["history"]["satisfaction_change_pp"]])
    hs.append(["Efficiency stability (%)", r["history"]["efficiency_stability_score_pct"]])
    for c in hs[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=dark)
    for row in hs.iter_rows(min_row=2, max_row=hs.max_row):
        for cell in row:
            cell.alignment = Alignment(vertical="top")
    for row in range(2, 2 + len(r["history"]["rows"])):
        hs.cell(row, 5).number_format = "0.0%"
        hs.cell(row, 8).number_format = "0.0%"
        hs.cell(row, 9).number_format = "0.0%"
    hs.column_dimensions["A"].width = 20
    for col in "BCDEFGHI":
        hs.column_dimensions[col].width = 18

    # Methodology sheet
    eq = wb.create_sheet("Methodology")
    eq.append(["Metric / model", "Equation / rule", "Meaning"])
    methodology = [
        ("Model configuration", "model_config.py", f"Central source for model version {MODEL_CONFIG['version']}, scales, baseline, regression parameters, enrollment bands, and history rules."),
        ("Total support cost", "Actual SM Hours × Hourly Rate", "Direct semester support labour cost."),
        ("Cost / student", "Total Support Cost ÷ Enrollment", "Actual support cost distributed across enrolled students."),
        ("Operating baseline", f"{OPERATING_BASELINE_HOURS:g} SM hours", "Planning baseline used to separate fixed course-operation support from variable support."),
        ("Baseline-adjusted support minutes / student", f"MAX(0, Actual SM Hours − {OPERATING_BASELINE_HOURS:g}) ÷ Enrollment × 60", "Variable support per enrolled student after fixed operating baseline."),
        ("Raw regression prediction", f"{MODEL_INTERCEPT:.6f} + {MODEL_COMPLEXITY_COEF:.6f}×Complexity + {MODEL_ENROLLMENT_COEF:.8f}×Enrollment", f"Historical multiple-regression prediction using the {COMPLEXITY_MIN:g}-{COMPLEXITY_MAX:g} complexity scale and enrollment."),
        ("Expected support hours", f"MAX({OPERATING_BASELINE_HOURS:g}, Raw regression prediction)", "Operational estimate used for variance, efficiency, and history calculations. The fitted regression itself is not altered."),
        ("Model R²", f"{MODEL_R2:.6f}", "Share of historical SM-hour variation explained by complexity + enrollment; not prediction accuracy."),
        ("Support variance", "Actual SM Hours − Expected SM Hours", "Positive = above benchmark workload; negative = below benchmark."),
        ("Support variance %", "(Actual − Expected) ÷ Expected", "Relative distance from benchmark workload."),
        ("Efficiency vs benchmark", "Expected SM Hours ÷ Actual SM Hours", "100% = benchmark; >100% uses fewer hours than expected; <100% uses more."),
        ("Benchmark cost difference", "(Actual SM Hours − Expected SM Hours) × Hourly Rate", "Dollar difference from model-benchmark support cost; not causal savings."),
        ("Cost / satisfied student", "Total Cost ÷ (Enrollment × Satisfaction Ratio)", "N/A if satisfaction is not entered."),
        ("Scale context", "Enrollment-band marginal slope, controlling for complexity", "Descriptive portfolio context; not a course performance score."),
        ("Support drift", "Slope of Support Variance % across ≥3 runs", "Direction of support cost relative to benchmark over successive offerings."),
        ("Complexity change", "Current Complexity − Oldest entered Complexity", "Whether the course has become structurally more/less complex."),
        ("Satisfaction change", "Current Satisfaction − Oldest available Satisfaction", "Outcome change displayed as %."),
        ("Efficiency stability", "MAX(0, 100 − [sample SD of Support Variance % × configured penalty])", "0-100% consistency index. 100% means no run-to-run variation in benchmark-relative support; lower values mean more variability."),
    ]
    for row in methodology:
        eq.append(row)
    for c in eq[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=maroon)
    eq.column_dimensions["A"].width = 34
    eq.column_dimensions["B"].width = 74
    eq.column_dimensions["C"].width = 72
    for row in eq.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    name = (meta["course_name"] or "Course-Support-Scorecard").replace("/", "-").replace("\\", "-")
    return send_file(
        out,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"{name}-{date.today().isoformat()}.xlsx",
    )


if __name__ == "__main__":
    app.run(debug=True)
