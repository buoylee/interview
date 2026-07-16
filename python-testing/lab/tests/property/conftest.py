import os
from pathlib import Path

from hypothesis.database import DirectoryBasedExampleDatabase
from hypothesis import settings


example_database = DirectoryBasedExampleDatabase(Path(".hypothesis/examples"))

settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    print_blob=True,
    derandomize=True,
    database=None,
)
settings.register_profile(
    "dev",
    max_examples=25,
    database=example_database,
)
settings.load_profile("ci" if "CI" in os.environ else "dev")
