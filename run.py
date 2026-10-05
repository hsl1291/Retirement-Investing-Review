"""Long Haul launcher: self-update -> make sure dependencies match -> start the app.

    python run.py              normal start
    python run.py --no-update  skip the update check
    python run.py --no-browser don't open a browser tab
"""
import hashlib
import os
import subprocess
import sys
import threading
import webbrowser
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


def open_when_ready(port: str, timeout_s: int = 90) -> None:
    """Open the browser only once the server answers (first start can take a while)."""
    import time
    import urllib.request

    url = f"http://localhost:{port}"
    for _ in range(timeout_s * 2):
        try:
            urllib.request.urlopen(url + "/_stcore/health", timeout=1)
            webbrowser.open(url)
            return
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.5)
    print(f"Server did not respond; open {url} manually.")


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
    port = os.environ.get("IRASIM_PORT", "8501")
    # headless avoids Streamlit's first-run email prompt; we open the browser ourselves
    if "--no-browser" not in sys.argv:
        threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()
    extra = [a for a in sys.argv[1:] if a not in ("--no-update", "--no-browser")]
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "Home.py"),
                            "--server.headless", "true", "--server.port", port, *extra], env=env)


if __name__ == "__main__":
    sys.exit(main())
