"""Start the local map-first application using the existing dependency bundle."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".packages"))
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("foundation:create_app", factory=True, host="127.0.0.1", port=8766)
