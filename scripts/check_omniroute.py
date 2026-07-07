import sys
import os
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import settings

def check_omniroute() -> bool:
    base_url = settings.OMNIROUTE_BASE_URL.rstrip("/")
    # Try models endpoint
    models_url = f"{base_url}/models"
    
    # Try health endpoint at root
    health_url = base_url.replace("/v1", "") + "/health"
    
    print(f"Checking OmniRoute connectivity...")
    print(f"- Checking Models endpoint: {models_url}")
    print(f"- Checking Health endpoint: {health_url}")
    
    # Try models
    try:
        resp = requests.get(models_url, timeout=3.0)
        if resp.status_code == 200:
            print("🟢 PASS: OmniRoute models endpoint is reachable and returned HTTP 200.")
            return True
    except requests.RequestException as e:
        print(f"⚪ Models check failed: {str(e)}")

    # Try health
    try:
        resp = requests.get(health_url, timeout=3.0)
        if resp.status_code == 200:
            print("🟢 PASS: OmniRoute health endpoint is reachable and returned HTTP 200.")
            return True
    except requests.RequestException as e:
        print(f"⚪ Health check failed: {str(e)}")
        
    print(f"\n🔴 FAIL: OmniRoute is NOT reachable at {base_url}.")
    print("👉 Please start the OmniRoute local service before running the Sustally application.")
    return False

if __name__ == "__main__":
    success = check_omniroute()
    sys.exit(0 if success else 1)
