"""
Streamlit entry point for ShipGuard.

The dashboard itself lives in :mod:`shipguard.ui.app`. This file stays at
the repository root because that is the main-file path the Streamlit
Community Cloud deployment points at.

``runpy`` is used rather than a plain import on purpose: Streamlit
re-executes its main script on every interaction, and an imported module
would only run once (subsequent reruns would hit the import cache and
render nothing).
"""

import runpy


runpy.run_module("shipguard.ui.app", run_name="__main__")
