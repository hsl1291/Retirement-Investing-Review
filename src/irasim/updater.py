"""Self-updater: keeps the install in sync with the GitHub repo.

Two install types, both handled:
  * git clone  -> ``git pull --ff-only``
  * ZIP install -> downloads the branch zip from GitHub and overwrites app files.

``user/`` (your saved profile, cache, config) and ``.venv/`` are never touched.
Repo/branch can be overridden in ``user/config.json``:
    {"repo": "owner/name", "branch": "main", "github_token": "...", "auto_update": true}
A token is only needed if the repo is private.

    python -m irasim.updater          # check only
    python -m irasim.updater --apply  # check and apply
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USER = ROOT / "user"
DEFAULTS = {"repo": "hsl1291/Retirement-Investing-Review",
            "branch": "claude/relaxed-knuth-jrc4fk",
            "github_token": "", "auto_update": True}
PRESERVE = {"user", ".venv", ".git", "__pycache__", ".pytest_cache"}


def config() -> dict:
    cfg = dict(DEFAULTS)
    f = USER / "config.json"
    if f.exists():
        try:
            cfg.update(json.loads(f.read_text()))
        except (OSError, ValueError):
            pass
    return cfg


def save_config(**kw) -> None:
    USER.mkdir(exist_ok=True)
    cfg = {k: v for k, v in config().items() if v != DEFAULTS.get(k) or k in kw}
    cfg.update(kw)
    (USER / "config.json").write_text(json.dumps(cfg, indent=2))


def _headers(cfg, accept="application/vnd.github+json") -> dict:
    h = {"Accept": accept, "User-Agent": "irasim-updater"}
    if cfg.get("github_token"):
        h["Authorization"] = f"Bearer {cfg['github_token']}"
    return h


def is_git_clone() -> bool:
    return (ROOT / ".git").exists()


def installed_commit() -> str | None:
    if is_git_clone():
        try:
            return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                  text=True, timeout=10, check=True).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    f = USER / "installed_commit"
    return f.read_text().strip() if f.exists() else None


def remote_commit(cfg: dict | None = None, timeout: int = 10) -> str:
    import requests

    cfg = cfg or config()
    r = requests.get(f"https://api.github.com/repos/{cfg['repo']}/commits/{cfg['branch']}",
                     headers=_headers(cfg, "application/vnd.github.sha"), timeout=timeout)
    r.raise_for_status()
    return r.text.strip()


def check(timeout: int = 10) -> dict:
    cfg = config()
    out = {"repo": cfg["repo"], "branch": cfg["branch"], "local": installed_commit(),
           "type": "git clone" if is_git_clone() else "zip install", "remote": None,
           "update_available": False, "error": None}
    try:
        out["remote"] = remote_commit(cfg, timeout)
        # a zip install with no recorded commit is treated as "unknown -> offer update"
        out["update_available"] = out["local"] != out["remote"]
    except Exception as e:  # noqa: BLE001 - offline/private repo/rate limit: report, don't crash
        out["error"] = str(e)
    return out


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> Path:
    top = {n.split("/")[0] for n in zf.namelist() if n.strip("/")}
    if len(top) != 1:
        raise RuntimeError("unexpected zip layout")
    for n in zf.namelist():
        target = (dest / n).resolve()
        if dest.resolve() not in target.parents and target != dest.resolve():
            raise RuntimeError(f"unsafe path in zip: {n}")
    zf.extractall(dest)
    return dest / top.pop()


def _copy_tree(src: Path, dst: Path) -> int:
    n = 0
    for item in src.iterdir():
        if item.name in PRESERVE:
            continue
        target = dst / item.name
        if item.is_dir():
            target.mkdir(exist_ok=True)
            n += _copy_tree(item, target)
        else:
            shutil.copy2(item, target)
            n += 1
    return n


def apply_zip(cfg: dict | None = None, sha: str | None = None, root: Path = ROOT, timeout: int = 60) -> str:
    import requests

    cfg = cfg or config()
    url = f"https://api.github.com/repos/{cfg['repo']}/zipball/{cfg['branch']}"
    r = requests.get(url, headers=_headers(cfg), timeout=timeout)
    r.raise_for_status()
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        top = _safe_extract(zf, Path(tmp))
        n = _copy_tree(top, root)
    (root / "user").mkdir(exist_ok=True)
    if sha:
        (root / "user" / "installed_commit").write_text(sha)
    return f"updated {n} files from {cfg['repo']}@{cfg['branch']}"


def apply_git() -> str:
    cfg = config()
    run = lambda *a: subprocess.run(a, cwd=ROOT, capture_output=True, text=True, timeout=120)  # noqa: E731
    dirty = run("git", "status", "--porcelain", "--untracked-files=no").stdout.strip()
    if dirty:
        raise RuntimeError("local changes to tracked files; commit or stash them before updating")
    f = run("git", "fetch", "origin", cfg["branch"])
    if f.returncode:
        raise RuntimeError(f.stderr.strip() or "git fetch failed")
    m = run("git", "merge", "--ff-only", "FETCH_HEAD")
    if m.returncode:
        raise RuntimeError(m.stderr.strip() or "cannot fast-forward (local commits diverge)")
    return m.stdout.strip().splitlines()[-1] if m.stdout.strip() else "already up to date"


def update() -> dict:
    """Check and apply. Returns {ok, message, requirements_changed}."""
    before = _req_hash()
    st = check()
    if st["error"]:
        return {"ok": False, "message": f"update check failed: {st['error']}", "requirements_changed": False}
    if not st["update_available"]:
        return {"ok": True, "message": "already up to date", "requirements_changed": False}
    try:
        msg = apply_git() if is_git_clone() else apply_zip(sha=st["remote"])
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"update failed: {e}", "requirements_changed": False}
    return {"ok": True, "message": msg, "requirements_changed": _req_hash() != before}


def _req_hash() -> str:
    f = ROOT / "requirements.txt"
    return hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else ""


if __name__ == "__main__":
    if "--apply" in sys.argv:
        res = update()
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["ok"] else 1)
    print(json.dumps(check(), indent=2))
