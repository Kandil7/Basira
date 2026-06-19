"""
Launch script for Basira Dashboard.

Usage:
    python -m src.dashboard.launch
    or
    streamlit run src/dashboard/app.py
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Launch the Streamlit dashboard."""
    app_path = Path(__file__).parent / "app.py"

    print("🔍 Starting Basira Dashboard...")
    print(f"📁 App path: {app_path}")
    print("🌐 Opening in browser...")
    print("   Press Ctrl+C to stop")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.port", "8501",
            "--server.headless", "true",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
