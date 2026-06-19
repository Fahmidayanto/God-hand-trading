"""Event collectors package."""

from app.services.event_collectors.structure_collector import StructureCollector
from app.services.event_collectors.position_collector import PositionCollector
from app.services.event_collectors.system_collector import SystemCollector

__all__ = [
    "StructureCollector",
    "PositionCollector",
    "SystemCollector",
]
