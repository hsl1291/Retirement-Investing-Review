"""Launcher: self-update -> make sure dependencies match -> start the app.

    python run.py              normal start
    python run.py --no-update  skip the update check
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
USER = ROOT / "user"


def ensure_deps() -> None:
    req = ROOT / "requirements.txt"
    stamp = USER / "requirements.sha"
    h = hashlib.sha256(req.read_bytes()).hexdigest()
    if stamp.exists() and stamp.read_text() == h:
        return
    print("Installing/updating dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])
    USER.mkdir(exist_ok=True)
    stamp.write_text(h)


def main() -> int:
    if "--no-update" not in sys.argv:
        try:
            from irasim import updater

            if updater.config()["auto_update"]:
                res = updater.update()
                print(f"[update] {res['message']}")
        except Exception as e:  # noqa: BLE001 - never block startup on an update problem
            print(f"[update] skipped ({e})")
    try:
        ensure_deps()
    except subprocess.CalledProcessError:
        print("Dependency install failed; trying to start anyway.")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "Home.py")], env=env)


if __name__ == "__main__":
    sys.exit(main())
