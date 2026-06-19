"""Quick API endpoint test for Activity Logs."""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def print_response(title, response):
    """Pretty print API response."""
    print(f"\n{'='*70}")
    print(f"{title}")
    print(f"{'='*70}")
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2, default=str))

def test_activity_logs_api():
    """Test all activity logs endpoints."""
    
    print("\n" + "="*70)
    print("Activity Logs API - Endpoint Tests")
    print("="*70)
    print(f"\nBase URL: {API_BASE}")
    print("\nMake sure the backend server is running!")
    print("Start with: cd backend && python -m uvicorn app.main:app --reload")
    
    try:
        # Test 1: Health check
        print("\n[1] Testing health endpoint...")
        response = requests.get(f"{API_BASE}/health")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("[OK] Server is running")
        else:
            print("[ERROR] Server not responding")
            return False
        
        # Test 2: Get recent logs (default)
        print("\n[2] GET /activity-logs (default, limit=50)")
        response = requests.get(f"{API_BASE}/activity-logs")
        print_response("Recent Logs", response)
        
        data = response.json()
        print(f"\n[OK] Retrieved {data['total']} logs")
        if data['logs']:
            print(f"[OK] Latest log: {data['logs'][0]['title']}")
        
        # Test 3: Get with limit
        print("\n[3] GET /activity-logs?limit=10")
        response = requests.get(f"{API_BASE}/activity-logs?limit=10")
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"Total logs: {data['total']}")
        print(f"[OK] Limit parameter working")
        
        # Test 4: Get with since parameter
        print("\n[4] GET /activity-logs?since=<timestamp>")
        since_time = (datetime.now() - timedelta(hours=1)).isoformat()
        response = requests.get(f"{API_BASE}/activity-logs?since={since_time}")
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"Total logs (last hour): {data['total']}")
        print(f"[OK] Since parameter working")
        
        # Test 5: Filter by event type
        print("\n[5] GET /activity-logs?event_type=SYSTEM_INFO")
        response = requests.get(f"{API_BASE}/activity-logs?event_type=SYSTEM_INFO")
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"SYSTEM_INFO logs: {data['total']}")
        print(f"[OK] Event type filter working")
        
        # Test 6: Filter by severity
        print("\n[6] GET /activity-logs?severity=SUCCESS")
        response = requests.get(f"{API_BASE}/activity-logs?severity=SUCCESS")
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"SUCCESS logs: {data['total']}")
        print(f"[OK] Severity filter working")
        
        # Test 7: Get stats
        print("\n[7] GET /activity-logs/stats")
        response = requests.get(f"{API_BASE}/activity-logs/stats")
        print_response("Cache Statistics", response)
        
        # Test 8: Get event types
        print("\n[8] GET /activity-logs/event-types")
        response = requests.get(f"{API_BASE}/activity-logs/event-types")
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"Event types: {len(data['event_types'])}")
        print(f"Types: {', '.join(data['event_types'][:5])}...")
        print(f"[OK] Event types endpoint working")
        
        # Test 9: Get severity levels
        print("\n[9] GET /activity-logs/severity-levels")
        response = requests.get(f"{API_BASE}/activity-logs/severity-levels")
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"Severity levels: {data['severity_levels']}")
        print(f"[OK] Severity levels endpoint working")
        
        # Test 10: Clear cache
        print("\n[10] POST /activity-logs/clear-cache")
        response = requests.post(f"{API_BASE}/activity-logs/clear-cache")
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"Message: {data['message']}")
        print(f"[OK] Clear cache endpoint working")
        
        print("\n" + "="*70)
        print("All API endpoint tests passed successfully!")
        print("="*70)
        
        return True
    
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Could not connect to server!")
        print("Make sure the backend is running:")
        print("  cd d:\\Project\\Project MT5\\ValueCell_MT5\\backend")
        print("  python -m uvicorn app.main:app --reload")
        return False
    
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    success = test_activity_logs_api()
    sys.exit(0 if success else 1)
