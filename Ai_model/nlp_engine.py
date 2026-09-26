import re
import string

class SafetyNLPEngine:
    """
    Hybrid NLP Engine combining domain terminology rules, context-aware negation detection,
    entity extraction, and explainable safety risk features.
    """

    NEGATION_PATTERNS = [
        r"\bno\s+(?:leak|hazard|danger|risk|issue|spark|vapor|failure|defect|crack|flame|injury|incident|problem)\b",
        r"\bnot\s+(?:leaking|damaged|broken|energized|exposed|failing|slipping)\b",
        r"\bwithout\s+(?:any\s+)?(?:leak|hazard|danger|risk|incident|issue|problem|defect)\b",
        r"\bzero\s+(?:leak|leakage|emission|incident|defect)\b",
        r"\bfree\s+of\s+(?:leaks|hazards|defects)\b",
        r"\bclean\s+and\s+(?:safe|normal|dry|intact)\b",
        r"\ball\s+normal\b",
        r"\binspected\s+and\s+found\s+(?:safe|normal|good|intact|secure|in\s+order)\b",
        r"\bno\s+abnormalities\b"
    ]

    ENERGY_SOURCES = [
        ("Electrical (440V / High Voltage)", ["energized", "live cable", "electrical", "switchgear", "circuit breaker", "electric shock", "high voltage", "wire", "junction box", "transformer"]),
        ("Chemical / Hydrocarbon Vapors", ["gas", "hydrocarbon", "methane", "h2s", "crude", "flange leak", "gas leak", "vapor", "vapour", "condensate", "fuel", "diesel leak", "toxic gas"]),
        ("High-Pressure Fluid / Gas", ["high pressure", "pressure", "hydraulic", "burst", "pinhole leak", "hose rupture", "3000 psi", "pressurized", "relief valve", "blowdown", "wellhead"]),
        ("Gravitational Potential (Fall / Struck By)", ["height", "scaffold", "scaffolding", "ladder", "working at height", "fall protection", "life line", "harness", "catwalk", "rig floor", "elevated platform", "suspended load", "crane", "rigging", "sling", "lifting"]),
        ("Kinetic / Mechanical Pinch", ["moving parts", "rotating", "pinch point", "impeller", "belt", "pulley", "conveyor", "crush hazard", "drill string"]),
        ("Thermal / Ignition Source", ["hot work", "welding", "grinding", "torch", "cutting", "spark", "open flame", "furnace", "hot surface"]),
        ("Confined Space Atmosphere", ["confined space", "tank", "vessel", "manhole", "column entry", "separator interior", "oxygen deficiency"])
    ]

    ACTIVITIES = [
        ("Pump / Equipment Maintenance", ["pump", "compressor", "motor", "overhaul", "servicing", "repair", "repairing", "maintenance", "greasing", "replacement"]),
        ("Hot Work / Welding", ["welding", "cutting", "hot work", "grinding", "torch"]),
        ("Working at Height / Scaffolding", ["scaffolding", "scaffold", "ladder", "working at height", "rig mast", "derrick", "climbing"]),
        ("Pipeline / Valve Operations", ["pipeline", "valve", "manifold", "flange", "turn test", "pigging", "flowline"]),
        ("Rig Floor & Well Operations", ["drilling", "tripping", "mud pump", "blowout preventer", "bop", "rig floor", "drill pipe"]),
        ("Material Handling & Lifting", ["crane", "forklift", "lifting", "rigging", "hoisting", "tubular goods", "pipe yard"]),
        ("Routine Inspection & Housekeeping", ["inspection", "housekeeping", "patrol", "walkthrough", "cleaning", "survey"])
    ]

    BARRIER_FAILURES = [
        ("Isolation Incomplete / LOTO Missing", ["isolation was incomplete", "isolation not completed", "without isolation", "not isolated", "loto missing", "no lockout", "switchgear energized", "live power"]),
        ("Fall Protection Unlatched / Missing Guardrails", ["without harness", "unclipped", "not hooked", "missing guardrail", "missing toe-board", "no life line", "safety harness not secured"]),
        ("Pressure Relief / Containment Compromised", ["ruptured", "burst", "pinhole leak", "flange leaking", "gasket blown", "seal failure", "hose cracked"]),
        ("Exclusion Zone / Guard Bypassed", ["barrier removed", "guard missing", "bypassed", "no barricade", "exclusion zone absent", "pedestrian walkway"]),
        ("PPE Missing / Defective", ["without ppe", "no goggles", "missing gloves", "no helmet", "without safety glasses", "unprotected"]),
        ("Permit / Gas Test Absent", ["without permit", "no gas test", "no hot work permit", "unauthorized entry"])
    ]

    EQUIPMENT_KEYWORDS = [
        ("Compressor C-12", ["compressor", "c-12", "c12"]),
        ("Mud Pump P-07", ["mud pump", "pump p-07", "p-07", "p07"]),
        ("Generator G-04", ["generator", "g-04", "g04", "power gen"]),
        ("Valve V-19", ["valve", "v-19", "v19", "esd valve"]),
        ("Rig Mast Hoist H-02", ["hoist", "h-02", "h02", "rig hoist", "mast"]),
        ("Crude Oil Separator S-01", ["separator", "s-01", "s01", "vessel"]),
        ("Pipeline System", ["pipeline", "flowline", "manifold", "trunkline"]),
        ("Scaffolding Structure", ["scaffold", "scaffolding", "staging"])
    ]

    def __init__(self):
        pass

    VALID_HAZARD_DOMAINS = [
        # Electrical
        "electric", "electrical", "voltage", "wire", "cable", "switchgear", "circuit", "shock", "grounding", "earthing", "bijli", "taar", "current",
        # Gas & Chemical
        "gas", "leak", "leaking", "hydrocarbon", "methane", "h2s", "crude", "oil", "vapor", "vapour", "fuel", "diesel", "risav", "fume", "toxic", "chemical", "spill",
        # Pressure & Hydraulic
        "pressure", "psi", "hydraulic", "burst", "rupture", "hose", "blowout", "bop", "relief valve", "wellhead", "pinhole", "phat gaya",
        # Height, Lifting, Gravity
        "fall", "height", "scaffold", "scaffolding", "ladder", "harness", "lifeline", "rig floor", "derrick", "mast", "girna", "unchai",
        "crane", "hoist", "sling", "rigging", "suspended load", "pinch", "moving part", "drill", "pipe",
        # Fire & Thermal
        "fire", "spark", "flame", "hot work", "weld", "welding", "grind", "grinding", "torch", "explosion", "aag", "chingari",
        # Confined Space & Mechanical
        "confined space", "tank", "vessel", "manhole", "impeller", "belt", "pulley", "crush",
        # Equipment
        "pump", "compressor", "generator", "valve", "manifold", "separator", "pipeline", "flange", "motor", "engine",
        # Safety Barriers, Acts, Conditions
        "isolation", "isolated", "loto", "lockout", "tagout", "ppe", "helmet", "goggles", "gloves", "barrier", "guard",
        "guardrail", "permit", "ptw", "near miss", "incident", "unsafe", "hazard", "danger", "precursor", "sif", "khatra", "hadsa",
        "injury", "defect", "corrosion", "overdue", "trip", "unlatched", "unclipped", "chot", "broken", "damaged", "exposed",
        # Devanagari Hindi / Regional Oilfield Terms
        "बिजली", "विद्युत", "तार", "खुला", "पंप", "गैस", "रिसाव", "लीक", "आग", "ऊंचाई", "गिरना", "मचान", "खतरा", "गंभीर", "हादसा", "चोट", "प्रेशर"
    ]

    def check_negation(self, text: str) -> bool:
        """
        Check if the text represents a verified benign state or negative hazard statement
        (e.g., 'No leak was observed during inspection').
        """
        text_lower = text.lower()
        for pattern in self.NEGATION_PATTERNS:
            if re.search(pattern, text_lower):
                # Ensure it's not a negated barrier failure like "isolation was not completed"
                if any(bad in text_lower for bad in ["not completed", "not isolated", "not applied", "without isolation"]):
                    continue
                return True
        return False

    def validate_safety_report(self, text: str) -> dict:
        """
        Validates if the report genuinely pertains to industrial / oilfield safety.
        Rejects random conversation, casual talk, off-topic chatter, and gibberish.
        """
        text_lower = text.lower()

        # Check if text matches valid oilfield hazard keywords
        has_domain_terms = any(term in text_lower for term in self.VALID_HAZARD_DOMAINS)

        # Check if it's a valid safe inspection (negation)
        is_safe_inspection = self.check_negation(text_lower)

        if not has_domain_terms and not is_safe_inspection:
            return {
                "is_valid": False,
                "reason": "NO_OILFIELD_HAZARD",
                "message": "No genuine industrial hazard or safety problem detected regarding the oil camp or worksite."
            }

        return {
            "is_valid": True,
            "reason": "VALID_OBSERVATION"
        }

    def extract_entities(self, text: str) -> dict:
        """
        Extract structured entities: Hazard, Energy Source, Activity, Equipment,
        Worker Exposure, and Barrier Condition.
        """
        text_lower = text.lower()
        is_safe_statement = self.check_negation(text_lower)

        # 1. Equipment Extraction
        equipment = "General Equipment / Worksite"
        for eq_name, keywords in self.EQUIPMENT_KEYWORDS:
            if any(k in text_lower for k in keywords):
                equipment = eq_name
                break

        # 2. Activity Extraction
        activity = "Routine Plant Operations"
        for act_name, keywords in self.ACTIVITIES:
            if any(k in text_lower for k in keywords):
                activity = act_name
                break

        # 3. Negation handling: If it's a verified safe inspection report
        if is_safe_statement and not any(critical in text_lower for critical in ["not completed", "isolation was not", "incomplete", "ruptured", "burst"]):
            return {
                "is_negated": True,
                "hazard": "Routine inspection normal / No active hazard",
                "energy_source": "None Detected",
                "activity": activity,
                "equipment": equipment,
                "worker_exposure": False,
                "barrier_status": "All Barriers Intact & Verified",
                "raw_text": text
            }

        # 4. Energy Source & Hazard
        detected_energy = "Mechanical / Industrial Work"
        detected_hazard = "General safety observation"
        for energy_name, keywords in self.ENERGY_SOURCES:
            if any(k in text_lower for k in keywords):
                detected_energy = energy_name
                if "electrical" in energy_name.lower():
                    detected_hazard = "Electrical / energy isolation"
                elif "hydrocarbon" in energy_name.lower() or "gas" in energy_name.lower():
                    detected_hazard = "Gas / hydrocarbon release"
                elif "gravitational" in energy_name.lower():
                    detected_hazard = "Working at height / Fall hazard"
                elif "pressure" in energy_name.lower():
                    detected_hazard = "Hydraulic / Pressure release"
                elif "thermal" in energy_name.lower():
                    detected_hazard = "Hot work / Fire & Explosion"
                elif "confined" in energy_name.lower():
                    detected_hazard = "Confined space hazardous atmosphere"
                else:
                    detected_hazard = energy_name
                break

        # 5. Worker Exposure
        exposure_keywords = [
            "worker", "technician", "team", "personnel", "operator", "exposed", 
            "line of fire", "walking", "working near", "under load", "inside", 
            "unprotected", "without harness", "unclipped", "within 2 meters", "standing near"
        ]
        worker_exposure = any(k in text_lower for k in exposure_keywords)

        # 6. Barrier Failure Status
        barrier_status = "Barrier Degraded / Under Review"
        for b_name, keywords in self.BARRIER_FAILURES:
            if any(k in text_lower for k in keywords):
                barrier_status = b_name
                break
        else:
            if any(term in text_lower for term in ["missing", "failed", "broken", "cracked", "bypassed", "absent", "leaking", "spark"]):
                barrier_status = "Direct Barrier Compromised / Absent"
            elif is_safe_statement:
                barrier_status = "Barrier Intact"

        return {
            "is_negated": False,
            "hazard": detected_hazard,
            "energy_source": detected_energy,
            "activity": activity,
            "equipment": equipment,
            "worker_exposure": worker_exposure,
            "barrier_status": barrier_status,
            "raw_text": text
        }
