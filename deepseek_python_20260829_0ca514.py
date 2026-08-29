# src/repair/rollback.py
"""Rollback a un snapshot anterior"""

from typing import Optional
from src.persistence.snapshot_manager import SnapshotManager

async def rollback_to_snapshot(snapshot_manager: SnapshotManager,
                               position_manager, order_manager,
                               snapshot_id: Optional[str] = None):
    """Restaura el estado desde un snapshot."""
    if snapshot_id:
        snapshot = await snapshot_manager.load(snapshot_id)
    else:
        snapshot = await snapshot_manager.load_latest_snapshot()
    if snapshot:
        await position_manager.restore(snapshot.get('positions', []))
        await order_manager.restore(snapshot.get('orders', []))
        return True
    return False