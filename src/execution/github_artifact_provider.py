"""
GitHub Artifact Provider — Descarga de artifact usando GitHub API
"""
import os
import json
import zipfile
import tempfile
from typing import List, Dict, Optional
import aiohttp
from src.utils.logger import get_logger

class GitHubArtifactProvider:
    def __init__(self, repo: str, token: Optional[str] = None):
        self.repo = repo
        self.token = token or os.environ.get('GH_PAT')
        self.logger = get_logger()

    async def fetch_latest(self) -> List[Dict]:
        if not self.token:
            self.logger.warning("GH_PAT no configurado")
            return []

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"token {self.token}"}

            # 1. Último workflow exitoso
            url = f"https://api.github.com/repos/{self.repo}/actions/runs?status=success&per_page=1"
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        self.logger.error(f"Error obteniendo runs: {resp.status}")
                        return []
                    data = await resp.json()
                    runs = data.get('workflow_runs', [])
                    if not runs:
                        return []
                    run_id = runs[0]['id']
            except Exception as e:
                self.logger.error(f"Error en API: {e}")
                return []

            # 2. Obtener artifact
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

            # 3. Descargar artifact
            url = f"https://api.github.com/repos/{self.repo}/actions/artifacts/{artifact_id}/zip"
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return []
                    zip_data = await resp.read()
            except Exception as e:
                self.logger.error(f"Error descargando artifact: {e}")
                return []

            # 4. Extraer signals.json
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
