# src/daps/scoring.py
"""DAPS Scoring — Estructura de puntuación"""

from dataclasses import dataclass

@dataclass
class DAPSScore:
    overall: float = 0.0
    determinism: float = 0.0
    statistics: float = 0.0
    probability: float = 0.0
    system: float = 0.0