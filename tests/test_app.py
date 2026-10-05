"""Smoke-test every Streamlit page headlessly (offline data mode)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = ["Home.py"] + [f"pages/{p.name}" for p in sorted((APP / "pages").glob("*.py"))]


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(page):
    at = AppTest.from_file(str(APP / page), default_timeout=180).run()
    assert not at.exception, [e.value for e in at.exception]


def test_optimizer_runs_and_returns_table():
    at = AppTest.from_file(str(APP / "pages/3_Optimizer.py"), default_timeout=300).run()
    [b for b in at.button if b.label == "Run optimizer"][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.dataframe) >= 1


def test_taxes_conversion_analysis_runs():
    at = AppTest.from_file(str(APP / "pages/4_Taxes_and_Roth.py"), default_timeout=300).run()
    [b for b in at.button if b.label == "Run conversion analysis"][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.dataframe) >= 1
