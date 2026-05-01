import json
from datetime import date
from pathlib import Path

NOTES_FILE = Path(__file__).parent / "data" / "notes.json"


def _load():
    if not NOTES_FILE.exists():
        return {"constraints": [], "preferences": []}
    with open(NOTES_FILE) as f:
        return json.load(f)


def _save(data):
    NOTES_FILE.parent.mkdir(exist_ok=True)
    with open(NOTES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_constraint(text: str, expires: str | None = None):
    data = _load()
    data["constraints"].append({"text": text, "expires": expires})
    _save(data)


def add_preference(text: str):
    data = _load()
    if text not in data["preferences"]:
        data["preferences"].append(text)
        _save(data)


def build_block() -> str:
    data = _load()
    today = date.today().isoformat()
    active = [c for c in data["constraints"] if not c.get("expires") or c["expires"] >= today]
    if active != data["constraints"]:
        data["constraints"] = active
        _save(data)
    parts = []
    if active:
        parts.append("Active constraints: " + "; ".join(c["text"] for c in active))
    if data["preferences"]:
        parts.append("Preferences: " + "; ".join(data["preferences"]))
    return ("[" + " | ".join(parts) + "]\n") if parts else ""
