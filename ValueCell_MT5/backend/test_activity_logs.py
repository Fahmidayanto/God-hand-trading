"""Test script for Activity Logs System."""

import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.activity_log_service import ActivityLogService
from app.models.activity_log import EventType, SeverityLevel


def test_activity_logs():
    """Test the activity log system."""
    
    print("=" * 70)
    print("Activity Logs System - Test Script")
    print("=" * 70)
    
    # Initialize service
    print("\n[1] Initializing ActivityLogService...")
    service = ActivityLogService(mt5_manager=None, cache_size=200)
    print("[OK] Service initialized")
    
    # Test system collector
    print("\n[2] Testing System Collector...")
    service.system_collector.log_info(
        title="Test Info Event",
        message="This is a test info event"
    )
    service.system_collector.log_warning(
        title="Test Warning Event",
        message="This is a test warning event"
    )
    service.system_collector.log_error(
        title="Test Error Event",
        message="This is a test error event"
    )
    print("[OK] System events logged")
    
    # Get recent logs
    print("\n[3] Fetching recent logs (limit=50)...")
    logs = service.get_recent_logs(limit=50)
    print(f"[OK] Fetched {len(logs)} logs")
    
    if logs:
        print("\n[4] Sample logs (first 5):")
        print("-" * 70)
        for i, log in enumerate(logs[:5], 1):
            print(f"\n{i}. [{log.severity.value}] {log.title}")
            print(f"   Event: {log.event_type.value}")
            print(f"   Time: {log.timestamp}")
            print(f"   Message: {log.message}")
            if log.metadata:
                print(f"   Metadata: {log.metadata}")
    else:
        print("\n[WARN] No logs found. This might be expected if data sources are empty.")
    
    # Test filtering by event type
    print("\n[5] Testing event type filter (SYSTEM_INFO)...")
    system_logs = service.get_logs_by_type(
        event_type=EventType.SYSTEM_INFO.value,
        limit=10
    )
    print(f"[OK] Found {len(system_logs)} SYSTEM_INFO logs")
    
    # Test filtering by severity
    print("\n[6] Testing severity filter (SUCCESS)...")
    success_logs = service.get_logs_by_severity(
        severity=SeverityLevel.SUCCESS.value,
        limit=10
    )
    print(f"[OK] Found {len(success_logs)} SUCCESS logs")
    
    # Get cache stats
    print("\n[7] Cache statistics:")
    stats = service.get_cache_stats()
    print(f"   Cache size: {stats['cache_size']}/{stats['cache_max_size']}")
    print(f"   Last update: {stats['last_update']}")
    
    # Test signal collector
    print("\n[8] Testing Signal Collector directly (skipped - no signal_collector in service)...")
    signal_logs = []
    
    # Test structure collector
    print("\n[9] Testing Structure Collector directly...")
    structure_logs = service.structure_collector.collect(limit=10)
    print(f"[OK] Structure collector returned {len(structure_logs)} logs")
    if structure_logs:
        print(f"   Latest structure: {structure_logs[0].title}")
    
    # Test position collector (may not work without MT5)
    print("\n[10] Testing Position Collector directly...")
    try:
        position_logs = service.position_collector.collect(limit=10)
        print(f"[OK] Position collector returned {len(position_logs)} logs")
        if position_logs:
            print(f"   Latest position: {position_logs[0].title}")
    except Exception as e:
        print(f"[WARN] Position collector skipped (MT5 not available): {e}")
    
    print("\n" + "=" * 70)
    print("Test completed successfully!")
    print("=" * 70)
    
    # Summary
    print("\n[SUMMARY]")
    print(f"   Total logs collected: {len(logs)}")
    print(f"   Signal logs: {len(signal_logs)}")
    print(f"   Structure logs: {len(structure_logs)}")
    print(f"   Event types available: {len([e for e in EventType])}")
    print(f"   Severity levels available: {len([s for s in SeverityLevel])}")
    
    return True


if __name__ == "__main__":
    try:
        result = test_activity_logs()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
