"""Startup/import behavior tests that should not depend on FastAPI TestClient."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


def test_main_import_defers_indicator_module() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        "-c",
        "import sys; import main; print('core.indicators' in sys.modules)",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - red phase evidence
        pytest.fail(f"import main timed out: {exc}")

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "False"
