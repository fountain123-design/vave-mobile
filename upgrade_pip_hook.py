#!/usr/bin/env python3
"""Buildozer pre-build hook: upgrade pip in venv to fix resolvelib incompatibility."""
import os
import sys
import subprocess
from pathlib import Path

def main():
    # Buildozer sets BUILDODBZER_VENV or we find it
    venv_candidates = [
        os.environ.get('BUILDOZER_VENV'),
        os.environ.get('VIRTUAL_ENV'),
    ]

    # Also search for venv in typical buildozer locations
    for p in Path('.buildozer').rglob('venv'):
        venv_candidates.append(str(p))

    for venv in venv_candidates:
        if not venv:
            continue
        pip_path = Path(venv) / 'bin' / 'pip'
        python_path = Path(venv) / 'bin' / 'python'
        if python_path.exists():
            print(f"[hook] Upgrading pip in {venv}...")
            subprocess.run([str(python_path), '-m', 'pip', 'install', '--upgrade', 'pip'],
                         check=False)
            return

if __name__ == '__main__':
    main()
