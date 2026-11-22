from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from sources.fetchers import fetch_all
from .config import load_labs
from .db import Store
from .models import NewsItem

log = logging.getLogger("mamba.worker")


class FetchThread(QThread):
    """Fetches everything off the UI thread and reports only brand-new items."""
    done = Signal(list, bool)   # new_items, was_first_run
    failed = Signal(str)

    def __init__(self, store: Store, parent=None) -> None:
        super().__init__(parent)
        self.store = store

    def run(self) -> None:
        try:
            first = self.store.count() == 0
            items = fetch_all(load_labs())
            new: list[NewsItem] = self.store.add_many(items)
            log.info("fetched %d items, %d new", len(items), len(new))
            self.done.emit(new, first)
        except Exception as ex:  # noqa: BLE001
            log.exception("fetch failed")
            self.failed.emit(str(ex))
