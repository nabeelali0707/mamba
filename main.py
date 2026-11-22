import logging
import sys

from PySide6.QtWidgets import QApplication

from core.db import Store
from pet.window import PetWindow


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler("mamba.log", encoding="utf-8")])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # live in the tray
    win = PetWindow(Store())
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
