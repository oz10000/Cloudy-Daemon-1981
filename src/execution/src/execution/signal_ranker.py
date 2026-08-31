# src/execution/signal_ranker.py
import numpy as np
from typing import List, Dict
from src.utils.logger import get_logger

class SignalRanker:
    def __init__(self, config: Dict):
        self.logger = get_logger()
        self.weights = config.get('signal_weights', {
            'amplitude': 0.30,
            'probability': 0.20,
            'risk_reward': 0.20,
            'volatility': 0.15,
            'liquidity': 0.15
        })
        self.min_score = config.get('min_signal_score', 0.30)

    def rank(self, signals: List[Dict]) -> List[Dict]:
        if not signals:
            return []
        scored = []
        for s in signals:
            entry = s.get('entry_price', 0)
            tp = s.get('tp_price', 0)
            sl = s.get('sl_price', 0)
            amplitude = s.get('amplitude', tp - entry if tp > entry else 0)
            probability = s.get('confidence', 50) / 100
            risk = s.get('risk', entry - sl if sl > 0 else 0)
            reward = s.get('reward', tp - entry if tp > 0 else 0)
            risk_reward = reward / (risk + 1e-6)
            volatility = s.get('atr_pct', 0.02)
            liquidity = s.get('liquidity', 1.0)

            score = (
                self.weights['amplitude'] * amplitude +
                self.weights['probability'] * probability +
                self.weights['risk_reward'] * risk_reward +
                self.weights['volatility'] * (1 - volatility) +
                self.weights['liquidity'] * liquidity
            )
            score = np.clip(score, 0, 1)
            scored.append({**s, 'rank_score': score})

        scored.sort(key=lambda x: x['rank_score'], reverse=True)
        self.logger.debug("RANKER", f"Señales ordenadas: {[(s['symbol'], s['rank_score']) for s in scored]}")
        return scored

    def select_best(self, signals: List[Dict]) -> Dict:
        ranked = self.rank(signals)
        for s in ranked:
            if s.get('rank_score', 0) >= self.min_score:
                return s
        return None
