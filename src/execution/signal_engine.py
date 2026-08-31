"""
Signal Engine — Lectura y filtrado de señales desde archivo o API
"""

import json
import os
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional
from datetime import datetime
from src.utils.logger import get_logger
from .signal_ranker import SignalRanker

class SignalEngine:
    """Motor de lectura de señales con filtrado y ranking."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = get_logger()
        self.source_type = config.get('type', 'file')
        self.path = config.get('path', './data/signals/signals.json')
        self.api_url = config.get('api_url', '')
        self.refresh_interval = config.get('refresh_interval', 5)
        self.last_read: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

        # Ranking y filtros
        self.ranker = SignalRanker(config.get('ranking', {}))
        self.min_level = config.get('min_level', 'B-TIER')
        self.blocked_regimes = config.get('blocked_regimes', ['Chop'])

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def read_signals(self) -> List[Dict]:
        """Lee señales desde la fuente configurada, filtra y aplica ranking."""
        raw = []
        if self.source_type == 'file':
            raw = await self._read_from_file()
        elif self.source_type == 'api':
            raw = await self._read_from_api()
        elif self.source_type == 'demo':
            raw = self._generate_demo_signals()

        if not raw:
            return []

        # Filtrar por nivel y régimen
        filtered = []
        for s in raw:
            level = s.get('level', 'NO-TIER')
            regime = s.get('regime', 'Chop')
            if level == 'NO-TIER':
                continue
            if regime in self.blocked_regimes:
                continue
            if not s.get('is_valid', False):
                continue
            filtered.append(s)

        if not filtered:
            return []

        # Aplicar ranking y seleccionar la mejor
        best = self.ranker.select_best(filtered)
        return [best] if best else []

    async def _read_from_file(self) -> List[Dict]:
        """Lee señales desde un archivo JSON."""
        if not os.path.exists(self.path):
            return []

        try:
            with open(self.path, 'r') as f:
                data = json.load(f)

            signals = data.get('signals', []) if isinstance(data, dict) else data
            if not isinstance(signals, list):
                return []

            # Validar señales
            valid_signals = []
            for sig in signals:
                if self._validate_signal(sig):
                    valid_signals.append(sig)

            # Marcar como leídas (consumir)
            if valid_signals and self.config.get('consume_on_read', True):
                with open(self.path, 'w') as f:
                    json.dump({'signals': []}, f)

            return valid_signals
        except Exception as e:
            self.logger.error("SIGNAL", f"Error leyendo archivo: {e}")
            return []

    async def _read_from_api(self) -> List[Dict]:
        """Lee señales desde una API REST."""
        if not self.api_url:
            return []

        await self._ensure_session()
        try:
            async with self._session.get(self.api_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    signals = data.get('signals', []) if isinstance(data, dict) else data
                    if isinstance(signals, list):
                        return [s for s in signals if self._validate_signal(s)]
                return []
        except Exception as e:
            self.logger.error("SIGNAL", f"Error en API: {e}")
            return []

    def _generate_demo_signals(self) -> List[Dict]:
        """Genera señales de demostración."""
        import random
        symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        directions = ['LONG', 'SHORT']

        signal = {
            'symbol': random.choice(symbols),
            'direction': random.choice(directions),
            'entry': 0,
            'tp': 0,
            'sl': 0,
            'confidence': round(random.uniform(0.5, 0.95), 2),
            'timestamp': datetime.now().isoformat(),
            'level': random.choice(['S-TIER', 'A-TIER', 'B-TIER']),
            'regime': random.choice(['Expansión', 'Tendencia Fuerte', 'Tendencia Débil']),
            'is_valid': True,
            'score': random.uniform(0.3, 0.8),
            'atr_pct': 0.02,
            'entry_price': 60000 + random.randint(-500, 500),
            'sl_price': 59000 + random.randint(-500, 500),
            'tp_price': 61000 + random.randint(-500, 500),
        }
        return [signal]

    def _validate_signal(self, signal: Dict) -> bool:
        """Valida la estructura de una señal."""
        required = ['symbol', 'direction', 'entry_price', 'sl_price', 'tp_price']
        if not all(k in signal for k in required):
            return False
        if signal['direction'] not in ['LONG', 'SHORT']:
            return False
        return True

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
