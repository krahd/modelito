import importlib
import os
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import pytest

pytestmark = pytest.mark.smoke

# Ensure the repository root is on sys.path so imports work in CI
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def test_import_modelito_package():
    mod = importlib.import_module("modelito")
    assert hasattr(mod, "__file__")


def test_package_root_exports_flatten_message_inputs():
    from modelito import flatten_message_inputs

    assert flatten_message_inputs(["hello"]) == [{"role": "user", "content": "hello"}]


def test_doctor_console_script_declared_in_pyproject():
    pyproject = Path(REPO_ROOT) / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert data["project"]["scripts"]["modelito-doctor"] == "modelito.doctor:main"
