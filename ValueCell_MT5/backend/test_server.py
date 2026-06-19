"""Quick test script for backend."""

import sys
from app.main import app
from app.config import get_settings

def test_app():
    """Test app initialization."""
    print("=" * 50)
    print("Testing ValueCell Backend")
    print("=" * 50)
    
    # Test settings
    settings = get_settings()
    print(f"\n✅ Settings loaded:")
    print(f"   - App Name: {settings.APP_NAME}")
    print(f"   - Version: {settings.APP_VERSION}")
    print(f"   - Environment: {settings.APP_ENV}")
    print(f"   - API Port: {settings.API_PORT}")
    print(f"   - MT5 Login: {settings.MT5_LOGIN}")
    print(f"   - Trading Mode: {settings.TRADING_MODE}")
    
    # Test app creation
    print(f"\n✅ FastAPI app created:")
    print(f"   - Title: {app.title}")
    print(f"   - Version: {app.version}")
    
    # Test routes
    routes = [route.path for route in app.routes]
    print(f"\n✅ Routes registered: {len(routes)}")
    print(f"   Sample routes:")
    for route in routes[:10]:
        print(f"   - {route}")
    
    # Count API endpoints
    api_routes = [r for r in routes if '/api/v1/' in r]
    print(f"\n✅ API v1 Endpoints: {len(api_routes)}")
    
    print("\n" + "=" * 50)
    print("✅ Backend is ready!")
    print("=" * 50)
    print(f"\nTo start server:")
    print(f"  cd backend")
    print(f"  start.bat")
    print(f"\nOr manually:")
    print(f"  uvicorn app.main:app --reload --host 0.0.0.0 --port {settings.API_PORT}")
    print(f"\nAPI Docs: http://localhost:{settings.API_PORT}/docs")
    print()
    
    return True

if __name__ == "__main__":
    try:
        success = test_app()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
