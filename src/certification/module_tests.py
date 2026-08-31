# src/certification/module_tests.py
from src.contracts.module_contract import ModuleContract

class ModuleTests:
    @staticmethod
    async def run_all(module: ModuleContract) -> dict:
        results = {'passed': 0, 'total': 0, 'errors': []}
        try:
            health = await module.health()
            if health.get('status') == 'ok':
                results['passed'] += 1
            else:
                results['errors'].append('health check failed')
        except Exception as e:
            results['errors'].append(f'health exception: {e}')
        results['total'] += 1
        try:
            if hasattr(module, 'start'):
                await module.start()
                results['passed'] += 1
            else:
                results['passed'] += 1
        except Exception as e:
            results['errors'].append(f'start exception: {e}')
        results['total'] += 1
        return results
