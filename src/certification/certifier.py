# src/certification/certifier.py
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List
from src.contracts.module_contract import ModuleContract
from src.utils.logger import get_logger


class Certifier:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = get_logger()
        self.certificates: List[Dict] = []

    async def certify_module(self, module: ModuleContract) -> Dict[str, Any]:
        self.logger.info(f"CERTIFY — Certificando módulo: {module.name} v{module.version}")

        test_result = await module.test()
        health = await module.health()

        module_hash = hashlib.sha256(f"{module.name}{module.version}".encode()).hexdigest()

        passed = test_result.get('passed', 0)
        total = test_result.get('total', 0)
        score = (passed / total * 100) if total > 0 else 0

        certified = score >= 80 and health.get('status', 'ok') == 'ok'

        certificate = {
            'module': module.name,
            'version': module.version,
            'timestamp': datetime.utcnow().isoformat(),
            'tests_passed': passed,
            'tests_total': total,
            'score': score,
            'health': health,
            'hash': module_hash,
            'certified': certified,
            'details': test_result
        }

        self.certificates.append(certificate)
        self.logger.info(f"CERTIFY — {module.name}: {'APROBADA' if certified else 'RECHAZADA'} (score={score:.1f}%)")
        return certificate

    def get_certificate(self, module_name: str) -> Dict:
        for cert in self.certificates:
            if cert['module'] == module_name:
                return cert
        return {}

    def generate_report(self) -> Dict:
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'certificates': self.certificates,
            'total_certified': sum(1 for c in self.certificates if c['certified']),
            'total_modules': len(self.certificates)
        }
