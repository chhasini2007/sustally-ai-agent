import os
import sys
from unittest.mock import MagicMock

# Mock third-party libraries that might be missing in the local environment
# to allow parsing the import graph statically on any developer machine.
missing_libs = [
    "fastapi", "fastapi.middleware.cors", "pydantic", "requests", 
    "pandas", "plotly", "plotly.io", "pypdf", "pdfplumber", "tqdm", "urllib3"
]
for lib in missing_libs:
    sys.modules[lib] = MagicMock()

# Simulate Vercel environment variables
os.environ["DEPLOYMENT_MODE"] = "vercel"
os.environ["VERCEL"] = "1"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Starting static import tree analysis...")

try:
    # 1. Import the FastAPI app
    from api.index import app, get_agent
    print("FastAPI app module loaded successfully!")

    # 2. Trigger get_agent() to load Vercel mode imports
    agent, is_vercel = get_agent()
    print(f"Agent loaded (Vercel Mode = {is_vercel})")

    # 3. Check sys.modules for forbidden packages
    forbidden = ["torch", "sentence_transformers", "transformers", "chromadb", "sqlite3"]
    found = [pkg for pkg in forbidden if pkg in sys.modules]

    if found:
        print(f"FAIL: Forbidden modules loaded in memory: {found}")
        sys.exit(1)
    else:
        print("PASS: Import verification successful. No heavy ML or DB packages loaded in Vercel mode.")
        sys.exit(0)

except Exception as e:
    print(f"FAIL: Verification script crashed: {e}")
    sys.exit(1)
