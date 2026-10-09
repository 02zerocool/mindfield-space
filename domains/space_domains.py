"""
space_domains.py — Pre-configured mission domain definitions
=============================================================
Ten domain stacks covering the major knowledge areas of a space mission.
Each is a separate LanceDB on its own port — same lean_api.py, different corpus.

Import this in your own scripts to get the full domain map:
    from domains.space_domains import DOMAINS
"""

DOMAINS = {
    "telemetry": {
        "port":        18001,
        "lancedb":     "./lancedb_telemetry",
        "description": "Sensor data, anomaly logs, system health, operations reports",
        "color":       [0.2, 0.8, 1.0],   # cyan
        "pos":         [-8,  2, -5],
        "queries": [
            "sensor anomaly out of limit",
            "thermal subsystem temperature exceedance",
            "power system voltage current anomaly",
            "attitude control system fault recovery",
            "communication signal loss contingency",
        ],
    },
    "procedures": {
        "port":        18002,
        "lancedb":     "./lancedb_procedures",
        "description": "Mission procedures, crew checklists, EVA protocols, contingency ops",
        "color":       [0.9, 0.9, 1.0],   # white
        "pos":         [6,  3, -7],
        "queries": [
            "crew egress procedure emergency",
            "EVA suit donning checklist",
            "docking approach procedure nominal",
            "fire suppression contingency procedure",
            "cargo transfer operations checklist",
        ],
    },
    "fmea": {
        "port":        18003,
        "lancedb":     "./lancedb_fmea",
        "description": "Failure modes, fault trees, anomaly investigations, lessons learned",
        "color":       [1.0, 0.3, 0.2],   # red
        "pos":         [0,  8,  2],
        "queries": [
            "single point failure critical system",
            "fault tree analysis probability",
            "anomaly root cause investigation",
            "lessons learned failure recovery",
            "redundancy architecture backup path",
        ],
    },
    "propulsion": {
        "port":        18004,
        "lancedb":     "./lancedb_propulsion",
        "description": "Propulsion systems, thruster specs, propellant chemistry, burn analysis",
        "color":       [1.0, 0.6, 0.2],   # orange
        "pos":         [-5, -3,  8],
        "queries": [
            "thruster specific impulse performance",
            "propellant loading oxidizer fuel ratio",
            "main engine ignition sequence abort",
            "electric propulsion xenon hall thruster",
            "trajectory correction maneuver delta-v",
        ],
    },
    "astrodynamics": {
        "port":        18005,
        "lancedb":     "./lancedb_astrodynamics",
        "description": "Orbital mechanics, trajectory design, navigation, rendezvous",
        "color":       [0.5, 0.3, 1.0],   # deep violet
        "pos":         [9, -2,  4],
        "queries": [
            "orbital insertion burn periapsis apoapsis",
            "rendezvous proximity operations approach",
            "debris collision avoidance maneuver",
            "interplanetary transfer trajectory gravity assist",
            "atmospheric entry corridor angle heating",
        ],
    },
    "life_support": {
        "port":        18006,
        "lancedb":     "./lancedb_life_support",
        "description": "ECLSS, environmental control, human factors, crew health",
        "color":       [0.3, 0.9, 0.4],   # green
        "pos":         [-7,  5,  3],
        "queries": [
            "CO2 removal assembly CDRA performance",
            "water recovery system brine processor",
            "oxygen generation electrolysis pressure",
            "cabin atmosphere pressure humidity control",
            "crew health monitoring radiation dosimetry",
        ],
    },
    "comms": {
        "port":        18007,
        "lancedb":     "./lancedb_comms",
        "description": "Communications systems, link budgets, RF systems, deep space network",
        "color":       [0.2, 0.6, 1.0],   # sky blue
        "pos":         [4, -6, -6],
        "queries": [
            "link budget margin signal noise ratio",
            "deep space network contact schedule",
            "high gain antenna pointing acquisition",
            "data rate downlink capacity relay",
            "emergency UHF contingency communication",
        ],
    },
    "science": {
        "port":        18008,
        "lancedb":     "./lancedb_science",
        "description": "Mission science objectives, instrument specs, data processing",
        "color":       [0.9, 0.4, 0.8],   # magenta
        "pos":         [-3, -7, -4],
        "queries": [
            "science objective measurement requirement",
            "instrument calibration dark current bias",
            "spectral resolution sensitivity detection limit",
            "data pipeline reduction calibration pipeline",
            "observation planning scheduling constraints",
        ],
    },
    "regulations": {
        "port":        18009,
        "lancedb":     "./lancedb_regulations",
        "description": "NASA-STD, ECSS, safety requirements, certification standards",
        "color":       [0.85, 0.85, 0.6],  # pale yellow
        "pos":         [7,  4,  5],
        "queries": [
            "NASA-STD safety requirement verification",
            "ECSS qualification test standard",
            "planetary protection requirement category",
            "launch site range safety explosive ordnance",
            "human rating certification crewed vehicle",
        ],
    },
    "planetary": {
        "port":        18010,
        "lancedb":     "./lancedb_planetary",
        "description": "Planetary geology, atmospheres, surface science, astrobiology",
        "color":       [0.7, 0.5, 0.3],   # Mars brown
        "pos":         [-6, -5, -8],
        "queries": [
            "Mars regolith composition perchlorate",
            "Europa subsurface ocean ice shell thickness",
            "Titan atmosphere methane hydrocarbon cycle",
            "Mars atmospheric pressure dust storm global",
            "astrobiology biosignature detection criteria",
        ],
    },
}
