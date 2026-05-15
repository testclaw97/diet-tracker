import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
DATA_DIR = Path(__file__).parent / "data"

EMPTY_DAY = {
    "date": "",
    "breakfast": None, "breakfast_kcal": 0,
    "lunch": None, "lunch_kcal": 0,
    "dinner": None, "dinner_kcal": 0,
    "snacks": None, "snacks_kcal": 0,
    "total_kcal": 0,
    "fitness_done": False, "fitness_minutes": 0, "fitness_type": None,
    "cross_trainer": False, "cross_trainer_minutes": 0,
    "weight_kg": None,
    "notes": ""
}


def is_fitness_done(d: dict) -> bool:
    """True if any exercise logged that day. Falls back to legacy cross_trainer flag."""
    return bool(d.get("fitness_done") or d.get("cross_trainer"))


def fitness_summary(d: dict) -> str:
    """Short label for the dashboard / prompts."""
    if d.get("fitness_done"):
        mins = d.get("fitness_minutes") or 0
        ftype = d.get("fitness_type") or "exercise"
        return f"{ftype} {mins}min" if mins else ftype
    if d.get("cross_trainer"):
        mins = d.get("cross_trainer_minutes") or 0
        return f"cross trainer {mins}min" if mins else "cross trainer"
    return "none"

def today_str():
    return datetime.now(BERLIN).strftime("%Y-%m-%d")

def data_path(date_str):
    return DATA_DIR / f"{date_str}.json"

def load_day(date_str):
    p = data_path(date_str)
    if p.exists():
        return json.loads(p.read_text())
    d = EMPTY_DAY.copy()
    d["date"] = date_str
    return d

def save_day(data: dict):
    DATA_DIR.mkdir(exist_ok=True)
    data["total_kcal"] = (
        data.get("breakfast_kcal", 0) +
        data.get("lunch_kcal", 0) +
        data.get("dinner_kcal", 0) +
        data.get("snacks_kcal", 0)
    )
    data_path(data["date"]).write_text(json.dumps(data, indent=2, ensure_ascii=False))

def update_today(**kwargs):
    return update_day(today_str(), **kwargs)

def update_day(date_str, **kwargs):
    d = load_day(date_str)
    d["date"] = date_str
    d.update(kwargs)
    save_day(d)
    return d

def build_memory_block() -> str:
    yesterday = (datetime.now(BERLIN) - timedelta(days=1)).strftime("%Y-%m-%d")
    y = load_day(yesterday)

    # Last 7 days for averages
    kcal_vals = []
    fit_days = 0
    for i in range(1, 8):
        d = load_day((datetime.now(BERLIN) - timedelta(days=i)).strftime("%Y-%m-%d"))
        if d.get("total_kcal", 0) > 0:
            kcal_vals.append(d["total_kcal"])
        if is_fitness_done(d):
            fit_days += 1

    week_avg = int(sum(kcal_vals) / len(kcal_vals)) if kcal_vals else 0

    yd_parts = []
    if y.get("breakfast"): yd_parts.append(f"Breakfast: {y['breakfast']} ({y['breakfast_kcal']} kcal)")
    if y.get("lunch"): yd_parts.append(f"Lunch: {y['lunch']} ({y['lunch_kcal']} kcal)")
    if y.get("dinner"): yd_parts.append(f"Dinner: {y['dinner']} ({y['dinner_kcal']} kcal)")
    if y.get("snacks"): yd_parts.append(f"Snacks: {y['snacks']} ({y['snacks_kcal']} kcal)")
    yd_parts.append(f"Total: {y['total_kcal']} kcal")
    fit = f"{fitness_summary(y)} ✅" if is_fitness_done(y) else "❌"
    yd_parts.append(f"Fitness: {fit}")

    yesterday_line = ". ".join(yd_parts)
    return (
        f"[Yesterday ({yesterday}): {yesterday_line}]\n"
        f"[Week avg: {week_avg} kcal/day. Fitness: {fit_days}/7 days.]\n"
    )

def get_latest_weight() -> str:
    for i in range(1, 60):
        d = load_day((datetime.now(BERLIN) - timedelta(days=i)).strftime("%Y-%m-%d"))
        if d.get("weight_kg"):
            return f"{d['weight_kg']}kg (logged {i} days ago)"
    return "not logged yet"
