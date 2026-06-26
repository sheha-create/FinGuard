#!/usr/bin/env python3
"""FinGuard - Start the server and keep it running."""

import subprocess
import sys
import time

print("=" * 60)
print("FinGuard - Real-Time AML & Transaction Fraud Analyzer")
print("=" * 60)
print()
print("Starting server on http://localhost:8000")
print("Press Ctrl+C to stop")
print()

try:
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "backend.main:app", 
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=r"C:\Users\Home\finguard"
    )
except KeyboardInterrupt:
    print("\nShutting down...")
