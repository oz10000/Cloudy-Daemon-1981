# src/repair/__init__.py
"""Repair — Autoreparación del sistema"""
from .repair_engine import RepairEngine
from .diagnosis import diagnose
from .rollback import rollback_to_snapshot