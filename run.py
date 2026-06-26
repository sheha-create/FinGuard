#!/usr/bin/env python3
"""FinGuard - AML Transaction Fraud Analyzer

Run this script to start the FinGuard application.
"""

import sys
import subprocess
import os
from pathlib import Path


def install_requirements():
    """Install Python dependencies."""
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("Dependencies installed successfully!")


def check_models():
    """Check if ML models exist, train if not."""
    models_dir = Path("models")
    if_model = models_dir / "isolation_forest.pkl"
    ae_model = models_dir / "autoencoder.pth"
    
    if if_model.exists() and ae_model.exists():
        print("ML models found!")
        return True
    
    print("Training ML models (this may take a moment)...")
    return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("FinGuard - Real-Time AML & Transaction Fraud Analyzer")
    print("=" * 60)
    print()
    
    original_dir = os.getcwd()
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    try:
        install_requirements()
        
        print()
        print("Starting FinGuard server...")
        print("Open http://localhost:8000 in your browser")
        print("Press Ctrl+C to stop the server")
        print()
        
        import uvicorn
        uvicorn.run(
            "backend.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    main()
