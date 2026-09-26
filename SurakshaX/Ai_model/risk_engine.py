class RiskEngine:
    """
    Prototype Risk Scoring Engine.
    Evaluates multi-factor risk drivers including Energy Hazard, Barrier Condition,
    Worker Exposure, Activity Context, Environmental Modifiers, and Machine Urgency.
    """

    def __init__(self):
        pass

    def calculate_risk(self, nlp_output: dict, sif_info: dict, weather_multiplier: float = 1.0, machine_overdue: bool = False) -> dict:
        """
        Calculates normalized risk score (0 - 100), risk level, and explainable AI risk drivers.
        """
        if nlp_output.get("is_negated", False):
            return {
                "risk_score": 12,
                "risk_level": "LOW",
                "risk_drivers": {
                    "high_energy": 0,
                    "worker_exposure": 0,
                    "barrier_failure": 0,
                    "activity_risk": 5,
                    "environmental_modifier": 0,
                    "machine_urgency": 0
                },
                "explanation": "No active hazard detected. Context analysis confirmed routine inspection or controlled condition without worker exposure.",
                "drivers_summary": [
                    {"label": "Hazard Severity", "score": 0, "max": 35, "desc": "Normal routine state"},
                    {"label": "Worker Exposure", "score": 0, "max": 25, "desc": "No line-of-fire exposure"},
                    {"label": "Barrier Integrity", "score": 0, "max": 20, "desc": "All barriers verified intact"},
                    {"label": "Activity Baseline", "score": 12, "max": 20, "desc": "Low-risk inspection routine"}
                ]
            }

        # 1. Base Severity & Energy Hazard (0 - 35 pts)
        energy = nlp_output.get("energy_source", "").lower()
        if "electrical" in energy or "hydrocarbon" in energy or "gas" in energy:
            energy_score = 35
            energy_desc = "High-energy release potential (Severe electrical / explosive hydrocarbon)"
        elif "pressure" in energy or "hydraulic" in energy or "gravitational" in energy or "fall" in energy:
            energy_score = 30
            energy_desc = "Significant energy hazard (High-pressure rupture / elevation fall)"
        elif "thermal" in energy or "kinetic" in energy or "confined" in energy:
            energy_score = 25
            energy_desc = "Moderate-to-high industrial energy hazard"
        else:
            energy_score = 15
            energy_desc = "Standard low-pressure or general industrial energy"

        # 2. Worker Line-of-fire Exposure (0 - 25 pts)
        if nlp_output.get("worker_exposure", False):
            exposure_score = 25
            exposure_desc = "Direct human presence in line-of-fire / active exposure"
        else:
            exposure_score = 8
            exposure_desc = "Indirect / low immediate worker line-of-fire exposure"

        # 3. Critical Barrier Failure (0 - 20 pts)
        barrier = nlp_output.get("barrier_status", "").lower()
        if any(b in barrier for b in ["incomplete", "missing", "bypassed", "ruptured", "burst", "unlatched", "absent"]):
            barrier_score = 20
            barrier_desc = "Primary critical safety barrier compromised or missing"
        elif any(b in barrier for b in ["degraded", "worn", "sticking"]):
            barrier_score = 12
            barrier_desc = "Barrier partially degraded or requiring maintenance"
        else:
            barrier_score = 5
            barrier_desc = "Standard barriers present"

        # 4. Activity Risk (0 - 15 pts)
        activity = nlp_output.get("activity", "").lower()
        if any(act in activity for act in ["hot work", "height", "scaffold", "drilling", "overhaul", "maintenance"]):
            activity_score = 12
            activity_desc = "High-risk operational activity (Intervention / Overhaul / Elevation)"
        else:
            activity_score = 6
            activity_desc = "Standard plant or routine monitoring activity"

        # 5. Machine Maintenance Urgency Factor (0 - 10 pts)
        machine_urgency_score = 10 if machine_overdue else 0
        machine_desc = "Associated machine maintenance is OVERDUE (+10%)" if machine_overdue else "Machine maintenance within nominal schedule"

        # 6. Environmental / Weather Multiplier (0 - 8 pts)
        weather_extra = 0
        if weather_multiplier > 1.1:
            weather_extra = min(8, int((weather_multiplier - 1.0) * 25))
            weather_desc = f"Adverse weather conditions detected (risk factor boosted by {weather_extra}%)"
        else:
            weather_desc = "Favorable environmental site conditions"

        raw_sum = energy_score + exposure_score + barrier_score + activity_score + machine_urgency_score + weather_extra
        total_risk = min(99, max(15, raw_sum))

        # Determine Risk Level
        if total_risk >= 85:
            risk_level = "CRITICAL"
        elif total_risk >= 65:
            risk_level = "HIGH"
        elif total_risk >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        drivers = {
            "high_energy": energy_score,
            "worker_exposure": exposure_score,
            "barrier_failure": barrier_score,
            "activity_risk": activity_score,
            "environmental_modifier": weather_extra,
            "machine_urgency": machine_urgency_score
        }

        # Human-Readable Explanation
        reasons = []
        if energy_score >= 30:
            reasons.append("high-energy source")
        if exposure_score >= 20:
            reasons.append("direct worker line-of-fire exposure")
        if barrier_score >= 18:
            reasons.append("compromised or missing safety barrier")
        if machine_overdue:
            reasons.append("overdue equipment maintenance deadline")
        if weather_extra > 0:
            reasons.append("adverse weather conditions")

        if reasons:
            explanation = f"{risk_level} priority because: " + " + ".join(reasons) + "."
        else:
            explanation = f"{risk_level} rating based on routine activity and controlled site baseline."

        drivers_summary = [
            {"label": "Energy Hazard Severity", "score": energy_score, "max": 35, "desc": energy_desc},
            {"label": "Worker Exposure (Line of Fire)", "score": exposure_score, "max": 25, "desc": exposure_desc},
            {"label": "Barrier Integrity & Condition", "score": barrier_score, "max": 20, "desc": barrier_desc},
            {"label": "Activity Complexity Risk", "score": activity_score, "max": 15, "desc": activity_desc},
            {"label": "Machine Maintenance Urgency", "score": machine_urgency_score, "max": 10, "desc": machine_desc}
        ]

        return {
            "risk_score": total_risk,
            "risk_level": risk_level,
            "risk_drivers": drivers,
            "explanation": explanation,
            "drivers_summary": drivers_summary
        }
