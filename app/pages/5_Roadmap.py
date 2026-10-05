import _shim  # noqa: F401
from pathlib import Path

import streamlit as st

from irasim import ui

ui.setup("Roadmap")
f = Path(__file__).resolve().parents[2] / "ROADMAP.md"
st.markdown(f.read_text() if f.exists() else "ROADMAP.md not found.")
