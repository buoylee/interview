"""Make app.py importable by bare name (track dir is hyphenated) and pin anyio."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


@pytest.fixture
def anyio_backend():
    return "asyncio"
