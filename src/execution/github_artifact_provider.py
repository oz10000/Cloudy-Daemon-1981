"""Proveedor de artefactos desde GitHub Actions."""
import os
import json
import zipfile
import tempfile
from typing import List, Dict, Optional
import aiohttp
from src.utils.logger import get_logger
from src.utils.retry import retry
from src.utils.retry_exceptions import RetryableError

logger = get_logger("github_artifact_provider")

class GitHubArtifactProvider:
    def __init__(self, repo: str, token: Optional[str] = None):
        self.repo = repo
        self.token = token or os.environ.get('GH_PAT')
        self.logger = logger

    @retry(max_attempts=3, delay=2.0, backoff=2.0, jitter=0.2, exceptions=(aiohttp.ClientError, TimeoutError, RetryableError))
    async def fetch_latest(self) -> List[Dict]:
        if not self.token:
            self.logger.warning("GH_PAT no configurado")
            return []

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"token {self.token}"}
            url = f"https://api.github.com/repos/{self.repo}/actions/runs?status=success&per_page=1"
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 401:
                        raise RetryableError("Token inválido o expirado (401)")
                    if resp.status != 200:
                        self.logger.error(f"Error obteniendo runs: {resp.status}")
                        return []
                    data = await resp.json()
                    runs = data.get('workflow_runs', [])
                    if not runs:
                        return []
                    run_id = runs[0]['id']
            except Exception as e:
                self.logger.error(f"Error en GitHub API: {e}")
                return []

            url = f"https://api.github.com/repos/{self.repo}/actions/runs/{run_id}/artifacts"
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    artifacts = data.get('artifacts', [])
                    if not artifacts:
                        return []
                    artifact = next((a for a in artifacts if a['name'] == 'signals'), artifacts[0])
                    artifact_id = artifact['id']
            except Exception as e:
                self.logger.error(f"Error obteniendo artifact: {e}")
                return []

            url = f"https://api.github.com/repos/{self.repo}/actions/artifacts/{artifact_id}/zip"
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return []
                    zip_data = await resp.read()
            except Exception as e:
                self.logger.error(f"Error descargando artifact: {e}")
                return []

            try:
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                    tmp.write(zip_data)
                    tmp_path = tmp.name
                signals = []
                with zipfile.ZipFile(tmp_path, 'r') as zf:
                    for name in zf.namelist():
                        if name.endswith('signals.json'):
                            with zf.open(name) as f:
                                data = json.load(f)
                                signals = data.get('signals', [])
                                break
                os.unlink(tmp_path)
                return signals
            except Exception as e:
                self.logger.error(f"Error extrayendo signals.json: {e}")
                return []
