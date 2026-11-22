import logging
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)                      # works no matter where Windows launches us from
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QLockFile                      # noqa: E402
from PySide6.QtWidgets import QApplication                # noqa: E402

from core import autostart                                # noqa: E402
from core.db import Store                                 # noqa: E402
from pet.window import PetWindow                          # noqa: E402


def main() -> int:
    if "--install" in sys.argv:
        print("Will start with Windows:", autostart.enable()); return 0
    if "--uninstall" in sys.argv:
        autostart.disable(); print("Removed from Windows startup."); return 0

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(ROOT / "mamba.log", encoding="utf-8")])
    logging.getLogger("httpx").setLevel(logging.WARNING)

    lock = QLockFile(os.path.join(tempfile.gettempdir(), "mamba-bull.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):       # another bull is already running
        return 0

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # live in the tray
    win = PetWindow(Store())
    win.show()
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
