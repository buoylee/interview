import os
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.property

LAB_ROOT = Path(__file__).parents[2]
LOAD_PROFILE = (
    "import runpy; "
    "from hypothesis import settings; "
    "runpy.run_path('tests/property/conftest.py'); "
    "print(settings.get_current_profile_name())"
)


@pytest.mark.parametrize(
    ("ci_value", "expected_profile"),
    [(None, "dev"), ("", "ci")],
)
def test_profile_selection_depends_on_ci_presence(
    ci_value: str | None,
    expected_profile: str,
) -> None:
    environment = os.environ.copy()
    if ci_value is None:
        environment.pop("CI", None)
    else:
        environment["CI"] = ci_value

    completed = subprocess.run(
        [sys.executable, "-c", LOAD_PROFILE],
        cwd=LAB_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == expected_profile
