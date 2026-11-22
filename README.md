# Mamba — the AI news bull

A desktop pet (a bull) that lives on your screen, tracks 40 AI labs, arXiv, Hugging Face,
Hacker News and more, and shows you the latest AI news in a speech bubble.

Run: `pip install -r requirements.txt` then `python main.py`

## Start with Windows
- Enable once: `python main.py --install` (or tick **Start with Windows** in the bull's right-click menu).
- Disable: `python main.py --uninstall` (or untick it).
- It registers `pythonw.exe main.py` under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
  (no admin rights). Only one bull can run at a time. If the network isn't up yet at boot, it retries every minute.

## Tuning
- Size: `SCALE` in `pet/bull.py`. Roaming speed: `ROAM_SPEED` in `pet/window.py`.
- Labs and sources: `config/labs.yaml`. What counts as relevant: `core/relevance.py`.
