# 🛡️ SurakshaX: AI/NLP-Powered Early Warning & Intervention System for Serious Injury & Fatality (SIF) Precursors

**Smart India Hackathon 2026 | Problem Statement 26165**  
**Organization:** Oil India Limited (OIL)  

---

## 📌 1. Overview & Core USP

> **"Transform unstructured safety reports into early SIF warnings, prioritize the most critical risks, guide corrective action, and continuously learn from HSE feedback."**

### Core Safety Operational Cycle
$$\text{DETECT} \longrightarrow \text{UNDERSTAND} \longrightarrow \text{PRIORITIZE} \longrightarrow \text{ACT} \longrightarrow \text{LEARN}$$

1. **DETECT**: Ingest safety narratives via Worker Safety Gate, structured web forms, voice speech-to-text, or offline-cached reports.
2. **UNDERSTAND**: Hybrid NLP engine extracts energy sources, worker line-of-fire exposure, barrier failure states, and handles contextual negation (e.g., *"No leak was observed"*).
3. **PRIORITIZE**: Multi-factor risk engine ranks issues by compounding hazard severity, SIF potential, line-of-fire exposure, and machine maintenance urgency.
4. **ACT**: Generates immediate regulatory precautions (OISD/OSHA), required solutions, time-bound Kanban interventions, and simulated safety interlocks.
5. **LEARN**: Human-in-the-loop review interface captures HSE officer adjustments, feeding continuous learning statistics and model recalibration.

---

## 🚀 2. Quickstart & Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Modern web browser (Chrome, Edge, Firefox, Safari)

### Setup Instructions
1. Navigate to the project directory:
   ```bash
   cd "d:/SIH 2026/sifguard"
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize and seed the SQLite database with realistic Oil India Limited data:
   ```bash
   python database/seed.py
   ```

4. Launch the local Flask server:
   ```bash
   python app.py
   ```

5. Open your web browser at:
   ```
   http://127.0.0.1:5000
   ```

---

## 🔑 3. Demo Credentials & User Roles

Switch roles instantly from the top-right role switcher without requiring repeated logins:

| Role | Demo User | Department | Capabilities |
|---|---|---|---|
| **Worker** | Rahul Das (`W001`) | Mechanical Maintenance (Site A) | Safety Gate badge check, voice/text reporting, personal status |
| **HSE Officer** | Ankur Sharma (`HSE01`) | Corporate HSE Directorate | Risk Priority ranking, Human-in-the-loop review, accept/correct, analytics |
| **Admin** | Dr. Prabal Saikia (`ADM01`) | Digital Safety Operations | System KPIs, interlocks, machine registry, weather controls |

---

## 🧠 4. AI / NLP Architecture

SurakshaX utilizes a **Hybrid Domain Rule + Contextual Negation + ML Feature Extraction** architecture that runs completely locally without external cloud API dependencies:

1. **Context-Aware Negation Handling**:
   - Regex-based syntactic negation models: `\bno\s+(?:leak|hazard|issue)\b`, `\bnot\s+leaking\b`, `\binspected\s+and\s+found\s+safe\b`.
   - Distinguishes routine safe observations (e.g., *"No leak observed during pipeline inspection"*) from barrier failures (e.g., *"Isolation was not completed"*), preventing false-positive alarms.
2. **Entity & Feature Extraction**:
   - **Dangerous Energy**: Electrical (440V/11kV), Hydrocarbon gas vapors, High-pressure hydraulic (3000 PSI), Gravitational (falls > 2m, suspended crane loads), Thermal/Ignition, Confined space atmosphere.
   - **Worker Exposure**: Detects proximity terms (*line of fire, unprotected, walking beneath load, inside vessel*).
   - **Barrier Condition**: *LOTO missing, unlatched fall arrest, ruptured hose, bypassed interlock, intact*.
3. **SIF Precursor Decision Logic**:
   - Implements Campbell Institute / Duffey & Saull methodology: SIF potential is triggered when high-consequence energy exists in combination with compromised direct barriers and worker line-of-fire exposure.
4. **Explainable AI (XAI)**:
   - Breaks down each risk score into weighted component bars:
     $$\text{Risk Score} = \min\Big(100, \text{Energy}(35) + \text{Exposure}(25) + \text{BarrierFailure}(20) + \text{Activity}(15) + \text{OverdueMachine}(10) + \text{Weather}(8)\Big)$$
   - Generates plain-English rationale (*"CRITICAL priority because: high-energy source + direct worker line-of-fire exposure + compromised safety barrier + overdue equipment maintenance"*).

---

## 🎙️ 5. Voice Architecture

- Implements the browser **Web Speech API** (`webkitSpeechRecognition` / `SpeechRecognition`).
- Features a responsive microphone toggle with pulsing red recording indicator.
- Converts worker speech into real-time editable transcripts.
- Gracefully degrades with clear notifications on browsers lacking speech recognition while keeping standard text input 100% operational.

---

## 🚪 6. AI Safety Gate Architecture

- Pre-entry clearance verification for enrolled worker IDs (`W001` - `W006`).
- Real-time HTML5 Canvas visual HUD displaying simulated computer vision bounding boxes:
  - `[HELMET]` (EN 397)
  - `[SAFETY VEST]` (Class 3)
  - `[SAFETY GOGGLES]` (ANSI Z87.1)
  - `[GLOVES]` (Cut Level 5)
  - `[BOOTS]` (IS 15298)
- Flags missing items with **ACCESS DENIED**.
- Provides **"Mark Precautions Completed"** action to simulate on-the-spot PPE donning and grant clearance (**ACCESS GRANTED**).

---

## 📡 7. Offline-First Architecture

- Detects network transitions via `navigator.onLine` and `online`/`offline` window events.
- Queues safety reports in `localStorage` when disconnected in remote oilfields.
- Displays a prominent **OFFLINE MODE** badge with real-time pending sync count.
- Automatically syncs queued reports via `/api/reports/sync` once internet connectivity is restored.
- Includes a manual toggle button on the network pill to demonstrate offline behavior during presentations.

---

## ⚙️ 8. Machine Maintenance & Interlock Simulation

- Real-time dynamic calculation of **Days Remaining** or **Overdue by $X$ Days** ($M_{101}$ Compressor C-12 overdue by 15 days, $M_{102}$ Mud Pump P-07 overdue by 9 days).
- Overdue status automatically boosts intervention urgency and compounds risk score by +15%.
- **"Simulate Safety Interlock"** button allows HSE officers to engage software machine lockout.
- Includes industrial safety disclaimer highlighting that real deployment requires certified hardware PLCs and physical LOTO locks.

---

## 🔄 9. Human-in-the-Loop & Continuous Learning

- HSE officers can review any report with four distinct actions:
  - **✓ Accept AI Recommendation**
  - **✎ Correct** (Adjust risk %, SIF classification, hazard category, and add officer notes)
  - **🔍 Field Verification Required**
  - **✗ Reject**
- All corrections are logged into the `feedback_log` table.
- Dashboard tracks model concordance improvements (e.g., initial baseline 72.4% improving to 81.2% with active human calibration).

---

## 📊 10. SIH Feature Mapping Summary

| SIH Requirement | Implementation in SurakshaX | Verified File / Endpoint |
|---|---|---|
| **Role-Based Views** | Worker, HSE Officer, Admin modes | `routes/auth_routes.py`, `static/js/app.js` |
| **Industrial Dashboard** | 8 KPI cards, 4 summary charts | `templates/index.html`, `static/js/charts.js` |
| **Smart Safety Gate** | Camera canvas, PPE bounding boxes, Access Denied/Granted | `static/js/safety_gate.js`, `/api/safety_gate/check` |
| **Voice Reporting** | Web Speech API, live transcript, edit fallback | `static/js/voice.js`, `templates/index.html` |
| **Context-Aware NLP** | Negation parsing ("No leak observed"), entity extraction | `ai/nlp_engine.py`, `tests/test_sifguard.py` |
| **SIF Precursor Detection** | Campbell Institute criteria, scenario description | `ai/sif_detector.py` |
| **Explainable AI (XAI)** | Risk drivers progress bars & narrative explanation | `ai/risk_engine.py`, `templates/index.html` |
| **Regulatory Precautions** | OISD/OSHA standard controls & immediate solution | `ai/recommendations.py` |
| **HSE Risk Priority** | Compounding multi-factor score, "Why is this #1?" modal | `/api/hse/priority`, `static/js/app.js` |
| **Interventions Kanban** | 🔴 Immediate, 🟠 24h, 🟡 3 Days, 🟢 Planned | `routes/hse_routes.py`, `templates/index.html` |
| **Machine Safety & Lock** | Overdue days calculus, simulated hardware interlock | `routes/machines_routes.py` |
| **Site Weather Context** | Multipliers for Site A (Duliajan), B (Moran), C (Digboi) | `routes/analytics_routes.py` |
| **Offline-First Mode** | LocalStorage queuing, auto-sync upon reconnection | `static/js/offline.js`, `/api/reports/sync` |
| **HSE Review & Learning** | Accept, Correct, Reject, feedback log, accuracy tracking | `routes/hse_routes.py`, `templates/index.html` |
| **10x Safety Analytics** | 10 interactive Chart.js charts & top recurring precursors | `static/js/charts.js` |

---

## ⚖️ Safety Disclaimers
> **Decision Support Only:** AI recommendations generated by SurakshaX are intended for decision-support only. Final operational and safety decisions remain with authorized HSE personnel.  
> **Simulated Machine Interlock:** Software safety interlocks demonstrated in this prototype are simulations. Real industrial machine control requires certified hardware safety PLCs, interlock switches, formal Lockout/Tagout (LOTO) protocols, and authorized permits to work.
