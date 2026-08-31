# src/daps/anomaly_engine.py
import numpy as np
from typing import Dict, Any, List
from dataclasses import dataclass
from src.utils.logger import get_logger


@dataclass
class DAPSScore:
    overall: float = 0.0
    determinism: float = 0.0
    statistics: float = 0.0
    probability: float = 0.0
    system: float = 0.0


class AnomalyEngine:
    def __init__(self):
        self.history: List[DAPSScore] = []
        self.logger = get_logger()

    async def analyze(self, metrics: Dict) -> DAPSScore:
        determinism = 100.0
        if metrics.get('error_rate', 0) > 0.1:
            determinism -= 30
        if metrics.get('latency_ms', 0) > 500:
            determinism -= 20

        win_rate = metrics.get('win_rate', 0.5)
        statistics = win_rate * 100

        confidence = metrics.get('avg_confidence', 0.5)
        probability = confidence * 100

        system = 100.0
        if not metrics.get('connected', False):
            system -= 40
        if metrics.get('pending_repairs', 0) > 0:
            system -= 10 * metrics['pending_repairs']

        overall = np.mean([determinism, statistics, probability, system])

        score = DAPSScore(
            overall=overall,
            determinism=determinism,
            statistics=statistics,
            probability=probability,
            system=system
        )
        self.history.append(score)
        self.logger.debug(f"DAPS — Score calculado: {overall:.1f}%")
        return score

    def get_status(self, score: DAPSScore) -> str:
        if score.overall >= 80:
            return "EXCELLENT"
        elif score.overall >= 60:
            return "NORMAL"
        elif score.overall >= 40:
            return "WARNING"
        else:
            return "CRITICAL"
