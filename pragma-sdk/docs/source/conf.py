# pylint: skip-file
# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
from pallets_sphinx_themes import ProjectLink
from pallets_sphinx_themes import get_version

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(1, os.path.abspath("./source"))
sys.path.insert(2, os.path.abspath(".."))
sys.path.insert(3, os.path.abspath("../pragma_sdk"))

# -- Project information -----------------------------------------------------

project = "pragma-sdk"
copyright = "2024, Pragma Labs"
author = "Pragma Labs"
release, version = get_version("pragma-sdk")


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "pallets_sphinx_themes",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html    _path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "furo"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
html_css_files = ["style.css"]

autodoc_class_signature = "separated"
autodoc_default_options = {"exclude-members": "__new__"}

pygments_dark_style = "dracula"

html_favicon = "_static/favicon.ico"
html_title = "🧩 SDK"
html_short_title = "pragma-sdk-docs"
html_permalinks_icon = "#"
html_title = f"Pragma SDK Documentation ({version})"

html_theme_options = {"light_logo": "pragma-logo.png", "dark_logo": "pragma-logo.png"}

html_context = {
    "project_links": [
        ProjectLink("PyPI Releases", "https://pypi.org/project/pragma-sdk/"),
        ProjectLink("Source Code", "https://github.com/astraly-labs/pragma-sdk/"),
        ProjectLink(
            "Issue Tracker", "https://github.com/astraly-labs/pragma-sdk/issues/"
        ),
        ProjectLink("Chat", "https://t.me/+Xri-uUMpWXI3ZmRk"),
    ]
}
