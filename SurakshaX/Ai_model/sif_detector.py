class SIFDetector:
    """
    Serious Injury and Fatality (SIF) Precursor Detector.
    Identifies high-consequence scenarios by evaluating high-energy sources,
    critical barrier integrity, and worker line-of-fire exposure.
    """

    HIGH_CONSEQUENCE_ENERGIES = [
        "electrical", "hydrocarbon", "gas", "pressure", "hydraulic",
        "gravitational", "fall", "suspended load", "confined space", "thermal", "fire"
    ]

    BARRIER_COMPROMISE_INDICATORS = [
        "incomplete", "missing", "bypassed", "compromised", "ruptured", "burst", "unlatched", "cracked", "absent"
    ]

    def __init__(self):
        pass

    def evaluate_sif(self, nlp_output: dict) -> dict:
        """
        Determine whether a report contains a Serious Injury and Fatality (SIF) Precursor.
        Returns: sif_potential (bool), confidence (float), scenario (str), energy_transfer_path (str)
        """
        if nlp_output.get("is_negated", False):
            return {
                "sif_potential": False,
                "confidence": 0.96,
                "scenario": "No credible SIF scenario detected. Verified routine or controlled state.",
                "energy_transfer_path": "No uncontrolled energy release vector."
            }

        energy = nlp_output.get("energy_source", "").lower()
        hazard = nlp_output.get("hazard", "").lower()
        barrier = nlp_output.get("barrier_status", "").lower()
        exposure = nlp_output.get("worker_exposure", False)

        has_high_energy = any(e in energy or e in hazard for e in self.HIGH_CONSEQUENCE_ENERGIES)
        has_barrier_failure = any(b in barrier for b in self.BARRIER_COMPROMISE_INDICATORS)

        # SIF Scenario Decision Matrix
        sif_potential = False
        confidence = 0.85
        scenario = "Standard workplace incident / unsafe act without direct high-energy fatality precursor."
        energy_path = "Energy contained within standard working parameters."

        if has_high_energy and has_barrier_failure and exposure:
            sif_potential = True
            confidence = 0.94
            if "electrical" in energy:
                scenario = "High-energy electrical arc flash or electrocution risk due to energized system during maintenance."
                energy_path = "Direct contact with live conductor / incomplete LOTO boundary."
            elif "gas" in energy or "hydrocarbon" in energy:
                scenario = "Flash fire, vapor cloud ignition, or asphyxiation from uncontrolled hydrocarbon release near personnel."
                energy_path = "Flammable vapor plume dispersing into active hot work or ignition zone."
            elif "pressure" in energy or "hydraulic" in energy:
                scenario = "High-pressure fluid injection trauma or severe blunt-force impact from component failure."
                energy_path = "High velocity jet stream or ruptured line whipping in line-of-fire."
            elif "gravitational" in energy or "height" in hazard:
                scenario = "Fatal trauma from high-elevation fall (> 2 meters) without effective secondary fall arrest."
                energy_path = "Unarrested vertical fall to deck or lower structure."
            elif "suspended" in energy or "crane" in energy or "lifting" in hazard:
                scenario = "Catastrophic crush trauma or pinned worker from dropped suspended tubular or heavy load."
                energy_path = "Gravitational kinetic energy transfer onto pedestrian pathway."
            elif "confined" in energy:
                scenario = "Toxic H2S poisoning or oxygen-deficient asphyxiation within unventilated enclosed vessel."
                energy_path = "Toxic inhalation pathway within enclosed space without life-support barrier."
            else:
                scenario = "Major hazardous energy release with worker in direct line-of-fire."
                energy_path = "Uncontrolled industrial energy transfer."

        elif has_high_energy and (has_barrier_failure or exposure):
            # High energy with either exposure or barrier failure is borderline SIF precursor
            sif_potential = True
            confidence = 0.88
            scenario = "Credible SIF precursor: High-energy hazard with degraded safety barriers."
            energy_path = "Barrier degraded; proximity to workers presents imminent escalation risk."

        elif has_high_energy:
            sif_potential = False
            confidence = 0.82
            scenario = "High energy present but controlled by intact barriers; maintain proactive monitoring."
            energy_path = "Engineered primary barrier currently active."

        return {
            "sif_potential": sif_potential,
            "confidence": confidence,
            "scenario": scenario,
            "energy_transfer_path": energy_path
        }
