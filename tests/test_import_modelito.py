import importlib
import os
import sys
import pytest

pytestmark = pytest.mark.smoke

# Ensure the repository root is on sys.path so imports work in CI
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def test_import_modelito_package():
    mod = importlib.import_module("modelito")
    assert hasattr(mod, "__file__")
