# src/contracts/module_contract.py
"""Contrato base para todos los módulos"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class ModuleContract(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        pass

    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def start(self) -> bool:
        pass

    @abstractmethod
    async def stop(self) -> bool:
        pass

    @abstractmethod
    async def test(self) -> Dict[str, Any]:
        pass