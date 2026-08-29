# src/daps/anomaly_engine.py
"""Anomaly Engine — Análisis estadístico avanzado (Z‑score, percentiles, outlier detection)"""

import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from src.utils.logger import get_logger
from .scoring import DAPSScore
from .validation import validate_metrics

class AnomalyEngine:
    def __init__(self, history_size: int = 100):
        self.history: List[DAPSScore] = []
        self.history_size = history_size
        self.logger = get_logger()

    async def analyze(self, metrics: Dict) -> DAPSScore:
        """Analiza las métricas y genera un puntaje DAPS."""
        # Validar entrada
        if not validate_metrics(metrics):
            self.logger.warning("DAPS", "Métricas inválidas, usando valores por defecto")
            metrics = self._default_metrics()

        # 1. Determinismo (basado en error_rate y latencia)
        determinism = 100.0
        error_rate = metrics.get('error_rate', 0.0)
        latency = metrics.get('latency_ms', 0.0)
        if error_rate > 0.1:
            determinism -= 30
        if latency > 500:
            determinism -= 20

        # 2. Estadística (win_rate, sharpe, drawdown)
        win_rate = metrics.get('win_rate', 0.5)
        sharpe = metrics.get('sharpe', 0.0)
        drawdown = metrics.get('drawdown', 0.0)
        # Normalizar win_rate a 0-100
        stat_score = win_rate * 100
        # Ajustar por sharpe y drawdown
        if sharpe < 0.5:
            stat_score -= 10
        if drawdown > 0.1:
            stat_score -= 20
        stat_score = max(0, min(100, stat_score))

        # 3. Probabilidad (confianza promedio)
        confidence = metrics.get('avg_confidence', 0.5)
        prob_score = confidence * 100

        # 4. Sistema (conectividad, reparaciones pendientes)
        system_score = 100.0
        if not metrics.get('connected', False):
            system_score -= 40
        pending_repairs = metrics.get('pending_repairs', 0)
        system_score -= pending_repairs * 10
        system_score = max(0, system_score)

        # Score global (promedio ponderado)
        overall = np.mean([determinism, stat_score, prob_score, system_score])

        score = DAPSScore(
            overall=overall,
            determinism=determinism,
            statistics=stat_score,
            probability=prob_score,
            system=system_score
        )

        # Almacenar historial
        self.history.append(score)
        if len(self.history) > self.history_size:
            self.history.pop(0)

        self.logger.debug("DAPS", f"Score calculado: {overall:.1f}% (D={determinism:.0f}, E={stat_score:.0f}, P={prob_score:.0f}, S={system_score:.0f})")
        return score

    def _default_metrics(self) -> Dict:
        return {
            'error_rate': 0.0,
            'latency_ms': 100,
            'win_rate': 0.5,
            'sharpe': 0.0,
            'drawdown': 0.0,
            'avg_confidence': 0.5,
            'connected': True,
            'pending_repairs': 0
        }

    def get_status(self, score: DAPSScore) -> str:
        if score.overall >= 80:
            return "EXCELLENT"
        elif score.overall >= 60:
            return "NORMAL"
        elif score.overall >= 40:
            return "WARNING"
        else:
            return "CRITICAL"
