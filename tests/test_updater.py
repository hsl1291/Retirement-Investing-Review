import io
import zipfile
from pathlib import Path

import pytest

from irasim import updater


def _zip(files: dict, top="owner-repo-abc123") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(f"{top}/{name}", data)
    return buf.getvalue()


class _Resp:
    def __init__(self, content): self.content = content
    def raise_for_status(self): pass


def test_zip_update_overwrites_code_preserves_user_data(tmp_path, monkeypatch):
    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "profile.json").write_text("MINE")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "Home.py").write_text("old")
    blob = _zip({"app/Home.py": "new", "user/profile.json": "OVERWRITE", "new_file.txt": "x"})
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(blob))
    msg = updater.apply_zip({"repo": "o/r", "branch": "b", "github_token": ""}, sha="deadbeef", root=tmp_path)
    assert (tmp_path / "app" / "Home.py").read_text() == "new"
    assert (tmp_path / "new_file.txt").exists()
    assert (tmp_path / "user" / "profile.json").read_text() == "MINE"
    assert (tmp_path / "user" / "installed_commit").read_text() == "deadbeef"
    assert "updated" in msg


def test_zip_slip_rejected(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("top/ok.txt", "x")
        z.writestr("top/../../evil.txt", "x")
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(buf.getvalue()))
    with pytest.raises(RuntimeError):
        updater.apply_zip({"repo": "o/r", "branch": "b", "github_token": ""}, root=tmp_path)
    assert not (tmp_path.parent / "evil.txt").exists()


def test_check_reports_error_when_offline(monkeypatch):
    monkeypatch.setattr(updater, "remote_commit", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    res = updater.check()
    assert res["error"] and not res["update_available"]


def test_live_refresh_never_reports_ok_on_empty_yahoo(tmp_path, monkeypatch):
    import pandas as pd

    from irasim import live

    monkeypatch.setattr(live, "CACHE", tmp_path)
    monkeypatch.setattr(live, "_fred", lambda *a, **k: (_ for _ in ()).throw(OSError("blocked")))
    import yfinance as yf
    monkeypatch.setattr(yf, "download", lambda *a, **k: pd.DataFrame())
    st = live.refresh()
    assert all(v.startswith("failed") for v in st.values()), st
    assert not list(tmp_path.glob("*.csv"))
