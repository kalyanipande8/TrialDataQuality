"""End-to-end pipeline runner: simulate multi-site data, then validate it."""

import subprocess
import sys
import os

BASE_DIR = os.path.dirname(__file__)


def run(script):
    print(f"\n=== Running {script} ===")
    result = subprocess.run([sys.executable, os.path.join(BASE_DIR, script)])
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    run("simulate_site_data.py")
    run("validate_site_data.py")
