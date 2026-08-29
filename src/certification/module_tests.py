# src/certification/module_tests.py
"""Tests estándar para módulos del sistema"""

from src.contracts.module_contract import ModuleContract

class ModuleTests:
    @staticmethod
    async def run_all(module: ModuleContract) -> dict:
        """Ejecuta una batería de tests genéricos."""
        results = {'passed': 0, 'total': 0, 'errors': []}
        # Test 1: health
        try:
            health = await module.health()
            if health.get('status') == 'ok':
                results['passed'] += 1
            else:
                results['errors'].append('health check failed')
        except Exception as e:
            results['errors'].append(f'health exception: {e}')
        results['total'] += 1
        # Test 2: start/stop (si existen)
        try:
            if hasattr(module, 'start'):
                await module.start()
                results['passed'] += 1
            else:
                results['passed'] += 1  # no requerido
        except Exception as e:
            results['errors'].append(f'start exception: {e}')
        results['total'] += 1
        return results
