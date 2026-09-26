class RecommendationEngine:
    """
    Generates regulatory safety precautions (OISD / OSHA standard practices)
    and immediate corrective directives based on detected hazards, energy types, and barrier conditions.
    """

    def __init__(self):
        pass

    def get_recommendations(self, nlp_output: dict, sif_info: dict, risk_info: dict) -> dict:
        """
        Returns structured list of precautions, immediate required solution, and suggested responsible role.
        """
        if nlp_output.get("is_negated", False):
            return {
                "precautions": [
                    "Maintain routine inspection rounds per standard operating procedure",
                    "Record logbook entry in central oilfield asset register",
                    "Ensure preventive maintenance schedule remains up-to-date"
                ],
                "solution": "Inspection verified safe. No corrective intervention required; continue routine operations.",
                "responsible_role": "Area Operator / Routine Inspector",
                "urgency": "Planned / Routine"
            }

        hazard = nlp_output.get("hazard", "").lower()
        energy = nlp_output.get("energy_source", "").lower()
        barrier = nlp_output.get("barrier_status", "").lower()
        risk_level = risk_info.get("risk_level", "MEDIUM")

        precautions = []
        solution = ""
        role = "Area HSE Officer"

        if "electrical" in hazard or "electrical" in energy:
            precautions = [
                "Immediately suspend maintenance activity on electrical / mechanical components",
                "Apply certified Lockout / Tagout (LOTO) padlocks and warning tags at the main feeder panel",
                "Perform physical zero-energy test using a calibrated voltage detector",
                "Equip technicians with arc-flash rated PPE (Category 3/4) and insulated safety boots",
                "Obtain verified clearance certificate from authorized Electrical Supervisor before work resumes"
            ]
            solution = "Stop maintenance immediately until electrical isolation is physically verified and padlocked by an authorized HSE electrical supervisor."
            role = "Senior Electrical Supervisor & HSE Officer"

        elif "gas" in hazard or "hydrocarbon" in energy:
            precautions = [
                "Activate emergency sector alert and shut off all active hot work permits within 50 meters",
                "Deploy portable multi-gas detector and continuously monitor lower explosive limit (% LEL) and H2S PPM",
                "Isolate upstream and downstream block valves; depressurize hydrocarbon inventory to flare",
                "Mandate positive pressure breathing apparatus (SCBA) if toxic H2S or inert nitrogen is suspected",
                "Post designated safety sentry at the hazard perimeter to prevent unauthorized entry"
            ]
            solution = "Isolate gas source, ventilate the sector, verify atmospheric LEL is zero percent, and inspect flange integrity prior to re-commissioning."
            role = "Process Safety Engineer & HSE Incident Controller"

        elif "height" in hazard or "fall" in energy or "scaffold" in hazard:
            precautions = [
                "Halt all work at height and safely evacuate personnel from elevated structure",
                "Enforce 100% tie-off policy with shock-absorbing dual lanyards attached to certified anchor points",
                "Inspect scaffolding structure: install missing toe-boards, intermediate guardrails, and secure platform planks",
                "Affix red 'DO NOT ENTER' warning tag on access ladder until scaffolding re-certified by competent inspector",
                "Ensure all hand tools are tethered with tool lanyards to prevent dropped object hazards"
            ]
            solution = "Suspend elevated work, barricade access ladder, and rectify missing fall protection barriers before issuing green scaffolding clearance tag."
            role = "Scaffolding Inspector & Rig Safety Officer"

        elif "pressure" in hazard or "hydraulic" in energy:
            precautions = [
                "De-energize hydraulic power pack and vent fluid pressure to zero PSI via bleed valves",
                "Verify pressure gauge indicates true zero prior to touching lines or unions",
                "Install certified burst-containment ballistic wrap / safety whip-checks across all flexible high-pressure hoses",
                "Establish strict line-of-fire exclusion perimeter around pressurized equipment",
                "Conduct hydrostatic pressure test on replacement line per API / OISD standards"
            ]
            solution = "Depressurize the system immediately, bleed remaining stored energy, and replace damaged hose with certified pressure-tested assembly."
            role = "Mechanical Maintenance Lead & HSE Officer"

        elif "suspended" in energy or "lifting" in hazard or "crane" in energy or "forklift" in hazard:
            precautions = [
                "Halt lifting operation and lower suspended load to ground level if safe to do so",
                "Demarcate visible barricaded exclusion perimeter beneath crane / hoist radius",
                "Inspect rigging hardware: web slings, wire ropes, and shackles for damage, kinks, or missing load rating tags",
                "Assign a dedicated, high-visibility Banksman / Rigging Marshall to direct load movement",
                "Prohibit carrying suspended tubular goods over active pedestrian pathways"
            ]
            solution = "Halt material transit, clear personnel from line-of-fire, and establish certified rigging taglines before resuming transport."
            role = "Rigging Supervisor & Rig Floor Marshall"

        elif "confined" in energy or "confined" in hazard:
            precautions = [
                "Prohibit vessel entry and post dedicated entry watchman at manway",
                "Perform continuous multi-gas atmospheric testing (Oxygen >= 19.5%, LEL 0%, H2S 0 PPM)",
                "Ensure positive mechanical forced ventilation is active throughout the entry",
                "Confirm rescue team readiness, tripod hoist, and emergency retrieval harness in place",
                "Verify valid Confined Space Entry Permit signed by site HSE manager"
            ]
            solution = "Halt confined entry, evacuate vessel interior, test atmosphere, and re-validate Confined Space Permit conditions."
            role = "Confined Space Entry Controller & HSE Lead"

        elif "hot work" in hazard or "thermal" in energy:
            precautions = [
                "Extinguish welding torch and halt all spark-generating tools immediately",
                "Conduct flammable gas survey within 15 meters radius of hot work location",
                "Cover all sewer drains, oily sumps, and open hydrocarbon conduits with fireproof blankets",
                "Station certified fire watch personnel equipped with pressurized AFFF / CO2 fire extinguishers",
                "Re-validate Hot Work Permit clearance"
            ]
            solution = "Quench hot work immediately, dampen hot surfaces, and re-test atmosphere for flammable gases before resuming."
            role = "Fire & Safety Inspector"

        else:
            precautions = [
                "Stop the unsafe act or condition immediately",
                "Ensure required Personal Protective Equipment (PPE) is correctly donned",
                "Barricade the immediate area to prevent accidental exposure",
                "Escalate report to area HSE supervisor for formal inspection"
            ]
            solution = "Mitigate immediate hazard, restore missing safety controls, and record corrective action in site HSE log."
            role = "Area Safety Officer"

        urgency = "Immediate" if risk_level == "CRITICAL" else "Within 24 Hours" if risk_level == "HIGH" else "Within 3 Days" if risk_level == "MEDIUM" else "Planned"

        return {
            "precautions": precautions,
            "solution": solution,
            "responsible_role": role,
            "urgency": urgency
        }
