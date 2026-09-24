"""Scoring engine for the eConcordia Course Scorecard.

The equations reproduce the logic in the supplied Strategic Course Auditor HTML.
Constants and thresholds are configurable heuristics, not externally validated norms.
"""
from dataclasses import dataclass, asdict

@dataclass
class Inputs:
    enrollment: float = 120
    hours: float = 45
    complexity: float = 6
    satisfaction: float = 85
    hourly_rate: float = 35
    tech_severity: int = 2
    team_severity: int = 1


def _label(value, bands, default):
    for upper, label in bands:
        if value < upper:
            return label
    return default


def calculate(i: Inputs) -> dict:
    enrollment = max(0.0, float(i.enrollment))
    hours = max(0.0, float(i.hours))
    complexity = min(10.0, max(1.0, float(i.complexity)))
    satisfaction = min(100.0, max(0.0, float(i.satisfaction)))
    rate = max(0.0, float(i.hourly_rate))

    total_cost = hours * rate
    cps = total_cost / enrollment if enrollment else 0.0
    effort_hours = hours / enrollment if enrollment else 0.0
    effort_minutes = effort_hours * 60
    sat_ratio = satisfaction / 100 if satisfaction > 0 else 0
    cpss = total_cost / (enrollment * sat_ratio) if enrollment and sat_ratio else 0.0

    denominator = complexity * hours
    pedagogical_roi = (satisfaction / denominator) * 100 if denominator else 0.0

    scalability_raw = enrollment / denominator if denominator else 0.0
    scalability = min(10.0, scalability_raw * 10)

    students_per_hour = enrollment / hours if hours else 0.0
    complexity_factor = (11 - complexity) / 10
    efficiency = min(100, round(students_per_hour * complexity_factor * 15))
    resource_util = min(100, round(efficiency * 0.4 + satisfaction * 0.4 + (100 - complexity * 10) * 0.2))

    vitality_score = efficiency * 0.3 + satisfaction * 0.5 + (10 - complexity) * 2
    if vitality_score >= 85: grade, grade_label = "A+", "Excellent"
    elif vitality_score >= 75: grade, grade_label = "A", "Very Good"
    elif vitality_score >= 65: grade, grade_label = "B+", "Good Standing"
    elif vitality_score >= 55: grade, grade_label = "B", "Satisfactory"
    elif vitality_score >= 45: grade, grade_label = "C+", "Needs Attention"
    elif vitality_score >= 35: grade, grade_label = "C", "At Risk"
    else: grade, grade_label = "F", "Critical Review"

    cps_label = "Calculating..." if cps <= 0 else _label(cps, [(15, "Very Efficient"), (25, "Efficient"), (40, "Moderate")], "High Cost")
    if effort_minutes > 25: effort_label = "Needs Evaluation"
    elif effort_minutes > 15: effort_label = "Inefficient"
    elif effort_minutes > 8: effort_label = "Efficient"
    else: effort_label = "Very Efficient"
    cpss_label = "Adjusted for Satisfaction" if cpss <= 0 else _label(cpss, [(15, "Strong Value"), (25, "Good Value"), (40, "Moderate")], "High Investment")
    if pedagogical_roi > 100: proi_label = "Excellent Efficiency"
    elif pedagogical_roi > 70: proi_label = "Good Efficiency"
    elif pedagogical_roi > 40: proi_label = "Moderate Efficiency"
    else: proi_label = "Low Efficiency"
    if scalability >= 8: scalability_label = "Highly Scalable"
    elif scalability >= 5: scalability_label = "Moderately Scalable"
    elif scalability >= 2: scalability_label = "Limited Scaling"
    else: scalability_label = "Not Scalable"

    recommendations = []
    if cps > 30: recommendations.append(("High Per-Student Cost", "Consider increasing enrollment or optimizing support hours to improve cost efficiency."))
    if satisfaction < 70: recommendations.append(("Low Satisfaction Alert", "Student satisfaction is below threshold. Review course content and support quality."))
    if complexity > 7 and hours < 50: recommendations.append(("Resource Mismatch", "High complexity course may benefit from additional support hours."))
    if efficiency > 80 and satisfaction > 85: recommendations.append(("High Performer", "This course demonstrates high efficiency and satisfaction under the current model."))
    if enrollment > 150 and hours < 40: recommendations.append(("Scaling Opportunity", "High enrollment with low hours. Evaluate whether additional support would improve outcomes."))
    if not recommendations: recommendations.append(("Balanced Metrics", "Course metrics are within the model's default ranges. Continue monitoring trends."))

    return {
        "inputs": asdict(i),
        "total_cost": total_cost,
        "cost_per_student": cps,
        "cost_per_student_label": cps_label,
        "effort_hours_per_student": effort_hours,
        "effort_minutes_per_student": effort_minutes,
        "effort_label": effort_label,
        "cost_per_satisfied_student": cpss,
        "cost_per_satisfied_student_label": cpss_label,
        "pedagogical_roi": pedagogical_roi,
        "pedagogical_roi_label": proi_label,
        "scalability_raw": scalability_raw,
        "scalability_index": scalability,
        "scalability_label": scalability_label,
        "students_per_hour": students_per_hour,
        "complexity_factor": complexity_factor,
        "efficiency_index": efficiency,
        "resource_utilization": resource_util,
        "satisfaction_score": satisfaction,
        "vitality_score": vitality_score,
        "vitality_grade": grade,
        "vitality_label": grade_label,
        "context_severity": int(i.tech_severity) + int(i.team_severity),
        "recommendations": recommendations,
    }
