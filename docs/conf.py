"""Sphinx configuration for getpaid-payu."""

project = "getpaid-payu"
author = "Dominik Kozaczko"
project_copyright = "2022-2026, Dominik Kozaczko"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "myst_parser",
]

autodoc_typehints = "description"
autodoc_member_order = "bysource"
autosummary_generate = True

html_theme = "furo"
html_title = "getpaid-payu"

myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
