"""Start-with-Windows via the per-user Run registry key (no admin rights needed)."""
from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "MambaBull"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MAIN = Path(__file__).resolve().parent.parent / "main.py"


def _command() -> str:
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")           # windowless interpreter: no console flash
    return f'"{pyw if pyw.exists() else exe}" "{MAIN}"'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
        return True
    except OSError:
        return False


def enable() -> str:
    import winreg
    cmd = _command()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
    return cmd


def disable() -> None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
    except OSError:
        pass
