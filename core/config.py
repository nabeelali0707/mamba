from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_labs() -> dict:
    with open(ROOT / "config" / "labs.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
