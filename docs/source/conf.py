"""Sphinx configuration for the `modelito` documentation.

This is intentionally minimal and uses `sphinx_rtd_theme` for ReadTheDocs.
"""
import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.abspath("../../"))

project = "modelito"
author = "mail_summariser"

try:
    from modelito import __version__ as release
except Exception:
    release = "0.1.1"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosummary",
]

autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
