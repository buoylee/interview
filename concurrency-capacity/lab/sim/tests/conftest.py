"""Make the sim/ scripts importable by bare name from tests.

The track dir is `concurrency-capacity` (hyphen, repo convention) which is
not a valid Python package name, so we add sim/ to sys.path and import the
modules directly (`from little import ...`) instead of a dotted package path.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
