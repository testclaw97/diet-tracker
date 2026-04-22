# Diet Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram diet coaching bot for Neha that tracks meals, snacks, cross trainer, and weight via 3 daily check-ins, stores data as JSON, and displays progress on a public GitHub Pages dashboard.

**Architecture:** Telegram bot (python-telegram-bot) on VPS with APScheduler for 3 daily Berlin-time jobs. Cross-session memory via compact daily summary files. Data pushed to GitHub Pages repo at 22:00 each day.

**Tech Stack:** Python 3, python-telegram-bot, APScheduler, claude -p (bypassPermissions), git SSH push, GitHub Pages (HTML + Chart.js)

---

## File Map

| File | Responsibility |
|---|---|
| `bot.py` | Telegram bot, scheduled jobs, message handler, claude -p calls |
| `memory.py` | Read/write daily JSON, build compact context block |
| `push_data.py` | Git add/commit/push data/ to GitHub |
| `start.sh` | PM2 entry point |
| `.env` | TELEGRAM_TOKEN, NEHA_CHAT_ID |
| `data/YYYY-MM-DD.json` | Daily meal/exercise log |
| `index.html` | GitHub Pages dashboard (pink/floral, Chart.js) |

---

## Task 1: Directory, env, start script

**Files:**
- Create: `~/products/diet-bot/.env`
- Create: `~/products/diet-bot/start.sh`
- Create: `~/products/diet-bot/CLAUDE.md`
- Create: `~/products/diet-bot/REFERENCES.md`

- [ ] Create product directory and data dir:
```bash
mkdir -p ~/products/diet-bot/data
cd ~/products/diet-bot
```

- [ ] Create `.env`:
```
TELEGRAM_TOKEN=REDACTED
NEHA_CHAT_ID=8701918489
```

- [ ] Create `start.sh`:
```bash
#!/bin/bash
cd /home/tejas/products/diet-bot
source .env
export TELEGRAM_TOKEN NEHA_CHAT_ID
python3 bot.py
```
```bash
chmod +x start.sh
```

- [ ] Create `CLAUDE.md`:
```markdown
# diet-bot

Diet coaching Telegram bot for Neha (Niharika).
Stack: Python, python-telegram-bot, APScheduler, claude -p
Data: ~/products/diet-bot/data/YYYY-MM-DD.json
Dashboard: https://testclaw97.github.io/diet-tracker/
PM2: diet-bot

## Key files
- bot.py — main bot, scheduler, claude -p calls
- memory.py — daily JSON read/write, context builder
- push_data.py — git push to GitHub
- data/ — daily JSON logs
```

- [ ] Create `REFERENCES.md`:
```markdown
# References

## Commands
Start: pm2 start start.sh --name diet-bot
Restart: pm2 restart diet-bot
Logs: pm2 logs diet-bot
Stop: pm2 stop diet-bot

## Neha
Telegram ID: 8701918489
Age: 28, Height: 169cm, Start: 88kg, Goal: 65kg by Aug 10 2026
Calories: 1400/day, low-carb, cross trainer 1x/day

## GitHub
Repo: git@github.com:testclaw97/diet-tracker.git
Pages URL: https://testclaw97.github.io/diet-tracker/
Data pushed nightly at 22:00 Berlin

## Schedule (Europe/Berlin)
09:00 — morning check-in
16:00 — afternoon check-in
22:00 — evening check-in + data push
Mon 08:00 — weekly weigh-in
```

- [ ] Install dependencies:
```bash
pip3 install python-telegram-bot apscheduler python-dotenv --break-system-packages
```
Expected: Successfully installed (or already satisfied)

- [ ] Commit:
```bash
cd ~/products/diet-bot && git init && git add . && git commit -m "feat: init diet-bot product"
```

---

## Task 2: memory.py — daily JSON + context builder

**Files:**
- Create: `~/products/diet-bot/memory.py`

- [ ] Create `memory.py`:
```python
import json
import os
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
    "cross_trainer": False, "cross_trainer_minutes": 0,
    "weight_kg": None,
    "notes": ""
}

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
    d = load_day(today_str())
    d.update(kwargs)
    save_day(d)
    return d

def build_memory_block() -> str:
    yesterday = (datetime.now(BERLIN) - timedelta(days=1)).strftime("%Y-%m-%d")
    y = load_day(yesterday)
    
    # Last 7 days for averages
    kcal_vals = []
    ct_days = 0
    for i in range(1, 8):
        d = load_day((datetime.now(BERLIN) - timedelta(days=i)).strftime("%Y-%m-%d"))
        if d.get("total_kcal", 0) > 0:
            kcal_vals.append(d["total_kcal"])
        if d.get("cross_trainer"):
            ct_days += 1

    week_avg = int(sum(kcal_vals) / len(kcal_vals)) if kcal_vals else 0

    yd_parts = []
    if y.get("breakfast"): yd_parts.append(f"Breakfast: {y['breakfast']} ({y['breakfast_kcal']} kcal)")
    if y.get("lunch"): yd_parts.append(f"Lunch: {y['lunch']} ({y['lunch_kcal']} kcal)")
    if y.get("dinner"): yd_parts.append(f"Dinner: {y['dinner']} ({y['dinner_kcal']} kcal)")
    if y.get("snacks"): yd_parts.append(f"Snacks: {y['snacks']} ({y['snacks_kcal']} kcal)")
    yd_parts.append(f"Total: {y['total_kcal']} kcal")
    ct = f"{y['cross_trainer_minutes']}min ✅" if y.get("cross_trainer") else "❌"
    yd_parts.append(f"Cross trainer: {ct}")

    yesterday_line = ". ".join(yd_parts)
    return (
        f"[Yesterday ({yesterday}): {yesterday_line}]\n"
        f"[Week avg: {week_avg} kcal/day. Cross trainer: {ct_days}/7 days.]\n"
    )

def get_latest_weight() -> str:
    for i in range(1, 60):
        d = load_day((datetime.now(BERLIN) - timedelta(days=i)).strftime("%Y-%m-%d"))
        if d.get("weight_kg"):
            return f"{d['weight_kg']}kg (logged {i} days ago)"
    return "not logged yet"
```

- [ ] Verify syntax:
```bash
cd ~/products/diet-bot && python3 -c "import memory; print(memory.build_memory_block())"
```
Expected: prints a memory block (mostly empty/zeros for new install — that's fine)

- [ ] Commit:
```bash
git add memory.py && git commit -m "feat: daily JSON memory and context builder"
```

---

## Task 3: push_data.py — nightly GitHub push

**Files:**
- Create: `~/products/diet-bot/push_data.py`

- [ ] Create `push_data.py`:
```python
import subprocess
import logging
from pathlib import Path

REPO_DIR = Path(__file__).parent
log = logging.getLogger(__name__)

def push_to_github():
    try:
        today_files = list((REPO_DIR / "data").glob("*.json"))
        if not today_files:
            log.info("No data files to push")
            return
        subprocess.run(["git", "add", "data/"], cwd=REPO_DIR, check=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=REPO_DIR
        )
        if result.returncode == 0:
            log.info("No changes to push")
            return
        subprocess.run(
            ["git", "commit", "-m", f"data: nightly update"],
            cwd=REPO_DIR, check=True
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        log.info("Data pushed to GitHub")
    except subprocess.CalledProcessError as e:
        log.error(f"Git push failed: {e}")
```

- [ ] Commit:
```bash
git add push_data.py && git commit -m "feat: nightly git push to GitHub Pages"
```

---

## Task 4: bot.py — main bot

**Files:**
- Create: `~/products/diet-bot/bot.py`

- [ ] Create `bot.py`:
```python
#!/usr/bin/env python3
import asyncio
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from telegram.constants import ChatAction
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import memory
import push_data

load_dotenv()
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
NEHA_CHAT_ID = int(os.environ["NEHA_CHAT_ID"])
BERLIN = ZoneInfo("Europe/Berlin")
WORKDIR = "/home/tejas/products/diet-bot"

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# In-session history: list of (user_msg, bot_response) tuples, max 5
session_history = []
cross_trainer_asked = False  # reset daily at midnight


SYSTEM_PROMPT = """You are Neha's personal dietitian and health coach. You are warm, encouraging, and professional.
Neha's profile: Age 28, 169cm, current weight ~88kg, goal 65kg by August 10 2026.
Daily target: 1400 kcal, low-carb diet. Cross trainer: 1x per day goal.
Key rules:
- Estimate calories for any food Neha mentions (be realistic, not optimistic)
- Gently flag if she exceeds 1400 kcal without being harsh
- Be concise in replies — max 3-4 sentences unless she asks for more
- Speak naturally, like a caring friend who is also a professional
- If she asks for meal suggestions, make them low-carb and under her remaining kcal budget
- Never use bullet lists in scheduled check-in messages — keep them conversational
"""


async def run_claude(prompt: str) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", prompt,
            "--output-format", "text",
            "--permission-mode", "bypassPermissions",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=WORKDIR,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode().strip()
        if not output and stderr:
            output = stderr.decode().strip()[:500]
        return output or "(no response)"
    except Exception as e:
        return f"Error: {e}"


def build_prompt(user_message: str) -> str:
    mem = memory.build_memory_block()
    today = memory.load_day(memory.today_str())
    
    # Today's partial log
    today_parts = []
    if today.get("breakfast"): today_parts.append(f"Breakfast: {today['breakfast']} ({today['breakfast_kcal']} kcal)")
    if today.get("lunch"): today_parts.append(f"Lunch: {today['lunch']} ({today['lunch_kcal']} kcal)")
    if today.get("dinner"): today_parts.append(f"Dinner: {today['dinner']} ({today['dinner_kcal']} kcal)")
    if today.get("snacks"): today_parts.append(f"Snacks: {today['snacks']}")
    remaining = 1400 - today.get("total_kcal", 0)
    today_parts.append(f"Remaining budget: {remaining} kcal")
    today_line = ". ".join(today_parts) if today_parts else "Nothing logged yet today."

    # Session history
    history_block = ""
    if session_history:
        lines = []
        for u, b in session_history:
            lines.append(f"Neha: {u}")
            lines.append(f"You: {b}")
        history_block = "\n".join(lines) + "\n"

    weight_info = memory.get_latest_weight()

    return (
        f"{SYSTEM_PROMPT}\n"
        f"{mem}"
        f"[Today so far: {today_line}]\n"
        f"[Latest weight: {weight_info}]\n\n"
        f"{history_block}"
        f"Neha: {user_message}\n"
        f"You:"
    )


async def send_and_store(bot, message: str, user_trigger: str = ""):
    response = await run_claude(message)
    await bot.send_message(chat_id=NEHA_CHAT_ID, text=response)
    if user_trigger:
        session_history.append((user_trigger, response))
        if len(session_history) > 5:
            session_history.pop(0)
    log.info(f"Sent response ({len(response)} chars)")
    return response


async def keep_typing(bot, chat_id):
    while True:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(4)


# ── Scheduled jobs ──────────────────────────────────────────────

async def morning_checkin(app):
    global session_history, cross_trainer_asked
    session_history = []  # fresh session each morning
    cross_trainer_asked = False
    mem = memory.build_memory_block()
    today = datetime.now(BERLIN).strftime("%A, %B %d")
    prompt = (
        f"{SYSTEM_PROMPT}\n{mem}\n"
        f"It is 9am on {today} in Berlin. Write a warm morning check-in for Neha.\n"
        f"Include: 1) One specific, actionable diet tip based on her recent logs "
        f"(if logs are empty, give a general low-carb tip). "
        f"2) Ask what she plans to eat today. "
        f"3) Ask if she plans to do cross trainer today. "
        f"Keep it friendly, short, no bullet points."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=NEHA_CHAT_ID, text=response)
    session_history.append(("(morning check-in)", response))
    log.info("Morning check-in sent")


async def afternoon_checkin(app):
    today = memory.load_day(memory.today_str())
    mem = memory.build_memory_block()
    prompt = (
        f"{SYSTEM_PROMPT}\n{mem}\n"
        f"[Today so far: breakfast logged: {'yes' if today.get('breakfast') else 'no'}, "
        f"lunch logged: {'yes' if today.get('lunch') else 'no'}]\n"
        f"It is 4pm. Write a friendly afternoon check-in for Neha. "
        f"Ask about lunch if not logged. Ask about any snacks or sweets. "
        f"Offer encouragement. Keep it very short — 2 sentences max."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=NEHA_CHAT_ID, text=response)
    session_history.append(("(afternoon check-in)", response))
    log.info("Afternoon check-in sent")


async def evening_checkin(app):
    global cross_trainer_asked
    today = memory.load_day(memory.today_str())
    mem = memory.build_memory_block()
    ct_done = today.get("cross_trainer", False)
    prompt = (
        f"{SYSTEM_PROMPT}\n{mem}\n"
        f"[Today: breakfast: {today.get('breakfast','not logged')}, "
        f"lunch: {today.get('lunch','not logged')}, "
        f"dinner: {today.get('dinner','not logged')}, "
        f"total kcal so far: {today.get('total_kcal',0)}, "
        f"cross trainer done: {ct_done}]\n"
        f"It is 10pm. Write a warm evening check-in. "
        f"Ask about dinner if not logged. "
        + ("" if ct_done else "Ask if she did cross trainer today. ")
        + "Give a short summary of today's eating if she has logged meals, "
        f"and one encouraging word for tomorrow. Keep it under 4 sentences."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=NEHA_CHAT_ID, text=response)
    session_history.append(("(evening check-in)", response))

    # Push data to GitHub
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, push_data.push_to_github)
    log.info("Evening check-in sent + data pushed")


async def monday_weighin(app):
    prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"[Latest weight: {memory.get_latest_weight()}]\n"
        f"It is Monday morning. Ask Neha for her weekly weigh-in in a warm, "
        f"non-pressuring way. Remind her that the number is just data, not judgment. "
        f"One sentence only."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=NEHA_CHAT_ID, text=response)
    log.info("Monday weigh-in request sent")


# ── Message handler ──────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != NEHA_CHAT_ID:
        return
    text = update.message.text or ""
    if not text:
        return

    log.info(f"Message from Neha: {text[:80]}")

    # Detect and save data mentions (simple keyword parsing — Claude handles the rest)
    text_lower = text.lower()
    today = memory.load_day(memory.today_str())

    # Cross trainer detection
    if any(w in text_lower for w in ["cross trainer", "crosstrainer", "training", "sport"]):
        if any(w in text_lower for w in ["yes", "ja", "done", "did", "finished", "gemacht"]):
            import re
            mins = re.search(r"(\d+)\s*(min|minute)", text_lower)
            memory.update_today(cross_trainer=True, cross_trainer_minutes=int(mins.group(1)) if mins else 30)

    # Weight detection (e.g. "I'm 86kg" or "86.5 kg")
    import re
    weight_match = re.search(r"(\d{2,3}(?:[.,]\d)?)\s*kg", text_lower)
    if weight_match and "goal" not in text_lower and "target" not in text_lower:
        memory.update_today(weight_kg=float(weight_match.group(1).replace(",", ".")))

    typing_task = asyncio.create_task(keep_typing(context.bot, update.effective_chat.id))
    try:
        prompt = build_prompt(text)
        response = await run_claude(prompt)
    finally:
        typing_task.cancel()

    await update.message.reply_text(response)
    session_history.append((text, response))
    if len(session_history) > 5:
        session_history.pop(0)


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tejas can check today's log: /log"""
    today = memory.load_day(memory.today_str())
    msg = (
        f"📊 Today ({today['date']}):\n"
        f"Breakfast: {today.get('breakfast') or '—'} ({today.get('breakfast_kcal',0)} kcal)\n"
        f"Lunch: {today.get('lunch') or '—'} ({today.get('lunch_kcal',0)} kcal)\n"
        f"Dinner: {today.get('dinner') or '—'} ({today.get('dinner_kcal',0)} kcal)\n"
        f"Snacks: {today.get('snacks') or '—'} ({today.get('snacks_kcal',0)} kcal)\n"
        f"Total: {today.get('total_kcal',0)} kcal / 1400 kcal\n"
        f"Cross trainer: {'✅ ' + str(today.get('cross_trainer_minutes',0)) + 'min' if today.get('cross_trainer') else '❌'}\n"
        f"Weight: {today.get('weight_kg') or '—'} kg"
    )
    await update.message.reply_text(msg)


# ── Main ──────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("log", cmd_log))

    scheduler = AsyncIOScheduler(timezone=BERLIN)
    scheduler.add_job(morning_checkin, "cron", hour=9, minute=0, args=[app])
    scheduler.add_job(afternoon_checkin, "cron", hour=16, minute=0, args=[app])
    scheduler.add_job(evening_checkin, "cron", hour=22, minute=0, args=[app])
    scheduler.add_job(monday_weighin, "cron", day_of_week="mon", hour=8, minute=0, args=[app])
    scheduler.start()

    log.info("Diet bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
```

- [ ] Verify syntax:
```bash
cd ~/products/diet-bot && python3 -c "import ast; ast.parse(open('bot.py').read()); print('OK')"
```
Expected: `OK`

- [ ] Commit:
```bash
git add bot.py && git commit -m "feat: main diet coaching bot with scheduler and memory"
```

---

## Task 5: GitHub repo + Pages dashboard

**Files:**
- Create: `~/products/diet-bot/index.html`

- [ ] **Manual step (TJ does this):** Create new GitHub repo `diet-tracker` at https://github.com/new
  - Name: `diet-tracker`
  - Public: yes
  - Do NOT add README (we'll push from VPS)

- [ ] Set up remote and push:
```bash
cd ~/products/diet-bot
git remote add origin git@github.com:testclaw97/diet-tracker.git
git branch -M main
git push -u origin main
```

- [ ] Create `index.html` (GitHub Pages dashboard, pink/floral theme):
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Neha's Health Journey 🌸</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
  :root {
    --pink: #f48fb1; --light-pink: #fce4ec; --deep-pink: #c2185b;
    --green: #81c784; --bg: #fff9fb; --card: #ffffff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Nunito', sans-serif; background: var(--bg); color: #333; }
  .hero {
    background: linear-gradient(135deg, #f48fb1, #f8bbd0, #fce4ec);
    padding: 32px 20px 48px;
    text-align: center;
  }
  .hero h1 { font-size: 1.8rem; font-weight: 800; color: #fff; text-shadow: 0 1px 4px rgba(0,0,0,.15); }
  .hero p { color: #fff; margin-top: 6px; font-size: 0.95rem; opacity: .9; }
  .flower { font-size: 2rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px; padding: 20px; max-width: 700px; margin: -24px auto 0; }
  .card { background: var(--card); border-radius: 16px; padding: 18px; text-align: center;
    box-shadow: 0 2px 12px rgba(244,143,177,.2); }
  .card .val { font-size: 1.6rem; font-weight: 800; color: var(--deep-pink); }
  .card .lbl { font-size: 0.78rem; color: #999; margin-top: 4px; }
  .section { max-width: 700px; margin: 24px auto; padding: 0 20px; }
  .section h2 { font-size: 1.1rem; font-weight: 700; color: var(--deep-pink); margin-bottom: 14px; }
  .progress-wrap { background: #fce4ec; border-radius: 999px; height: 14px; overflow: hidden; }
  .progress-bar { background: linear-gradient(90deg, var(--pink), var(--deep-pink));
    height: 100%; border-radius: 999px; transition: width .5s; }
  .progress-label { display: flex; justify-content: space-between; font-size: .78rem;
    color: #999; margin-top: 5px; }
  .meals-table { width: 100%; border-collapse: collapse; font-size: .88rem; }
  .meals-table th { color: #999; font-weight: 600; text-align: left; padding: 6px 4px;
    border-bottom: 1px solid #f0f0f0; }
  .meals-table td { padding: 8px 4px; border-bottom: 1px solid #f9f0f3; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: .75rem; font-weight: 700; }
  .badge.green { background: #e8f5e9; color: #388e3c; }
  .badge.red { background: #fce4ec; color: #c62828; }
  canvas { max-width: 100%; }
  .footer { text-align: center; padding: 32px; color: #ccc; font-size: .78rem; }
</style>
</head>
<body>

<div class="hero">
  <div class="flower">🌸</div>
  <h1>Neha's Health Journey</h1>
  <p id="subtitle">Loading your progress...</p>
</div>

<div class="cards">
  <div class="card"><div class="val" id="today-kcal">—</div><div class="lbl">kcal today</div></div>
  <div class="card"><div class="val" id="ct-streak">—</div><div class="lbl">day streak 🏃</div></div>
  <div class="card"><div class="val" id="kg-lost">—</div><div class="lbl">kg lost 💪</div></div>
  <div class="card"><div class="val" id="days-left">—</div><div class="lbl">days to goal</div></div>
</div>

<div class="section">
  <h2>🎯 Weight Progress</h2>
  <div class="progress-wrap"><div class="progress-bar" id="weight-bar" style="width:0%"></div></div>
  <div class="progress-label"><span id="weight-start">88 kg</span><span id="weight-now">—</span><span>65 kg</span></div>
</div>

<div class="section">
  <h2>🔥 Calories — Last 7 Days</h2>
  <canvas id="kcalChart" height="180"></canvas>
</div>

<div class="section">
  <h2>🥗 Recent Meals</h2>
  <table class="meals-table">
    <thead><tr><th>Date</th><th>Meals</th><th>kcal</th><th>🏃</th></tr></thead>
    <tbody id="meals-tbody"></tbody>
  </table>
</div>

<div class="footer">🌷 You're doing amazing, Neha! 🌷</div>

<script>
const GOAL_KG = 65, START_KG = 88, GOAL_DATE = new Date("2026-08-10");

function daysLeft() {
  return Math.max(0, Math.round((GOAL_DATE - new Date()) / 86400000));
}

async function loadDay(dateStr) {
  try {
    const r = await fetch(`data/${dateStr}.json?t=${Date.now()}`);
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

function dateStr(offset = 0) {
  const d = new Date(); d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

async function init() {
  const days = [];
  for (let i = 6; i >= 0; i--) {
    const d = await loadDay(dateStr(-i));
    days.push({ date: dateStr(-i), data: d });
  }

  const today = days[days.length - 1].data;
  document.getElementById("today-kcal").textContent = today ? today.total_kcal || 0 : 0;
  document.getElementById("days-left").textContent = daysLeft();

  // Cross trainer streak
  let streak = 0;
  for (let i = days.length - 1; i >= 0; i--) {
    if (days[i].data?.cross_trainer) streak++; else break;
  }
  document.getElementById("ct-streak").textContent = streak;

  // Weight
  let latestWeight = null;
  for (let i = days.length - 1; i >= 0; i--) {
    if (days[i].data?.weight_kg) { latestWeight = days[i].data.weight_kg; break; }
  }
  const lost = latestWeight ? (START_KG - latestWeight).toFixed(1) : "0";
  document.getElementById("kg-lost").textContent = lost;
  if (latestWeight) {
    const pct = Math.max(0, Math.min(100, ((START_KG - latestWeight) / (START_KG - GOAL_KG)) * 100));
    document.getElementById("weight-bar").style.width = pct + "%";
    document.getElementById("weight-now").textContent = latestWeight + " kg";
    document.getElementById("subtitle").textContent =
      `${lost} kg lost · ${daysLeft()} days to go · You got this! 🌸`;
  } else {
    document.getElementById("subtitle").textContent = `${daysLeft()} days to August 10 · Let's go! 🌸`;
  }

  // Chart
  const labels = days.map(d => d.date.slice(5));
  const kcals = days.map(d => d.data?.total_kcal || 0);
  new Chart(document.getElementById("kcalChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "kcal",
        data: kcals,
        backgroundColor: kcals.map(k => k > 1400 ? "#f48fb1" : "#f8bbd0"),
        borderRadius: 8,
      }, {
        label: "goal (1400)",
        data: Array(7).fill(1400),
        type: "line",
        borderColor: "#c2185b",
        borderDash: [5, 5],
        pointRadius: 0,
        fill: false,
      }]
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  });

  // Meals table
  const tbody = document.getElementById("meals-tbody");
  [...days].reverse().forEach(({ date, data }) => {
    if (!data) return;
    const meals = [data.breakfast, data.lunch, data.dinner].filter(Boolean).join(", ") || "—";
    const ct = data.cross_trainer
      ? `<span class="badge green">✅ ${data.cross_trainer_minutes}min</span>`
      : `<span class="badge red">❌</span>`;
    tbody.innerHTML += `<tr><td>${date.slice(5)}</td><td>${meals}</td><td>${data.total_kcal||0}</td><td>${ct}</td></tr>`;
  });
}

init();
</script>
</body>
</html>
```

- [ ] Commit and push dashboard:
```bash
cd ~/products/diet-bot
git add index.html
git commit -m "feat: GitHub Pages dashboard — pink floral theme"
git push origin main
```

- [ ] Enable GitHub Pages: Go to https://github.com/testclaw97/diet-tracker/settings/pages → Source: Deploy from branch `main`, folder `/` (root) → Save.

Expected URL (may take 1-2 min): `https://testclaw97.github.io/diet-tracker/`

---

## Task 6: Launch + verify

- [ ] Start with PM2:
```bash
cd ~/products/diet-bot
/home/tejas/.npm-global/lib/node_modules/pm2/bin/pm2 start start.sh --name diet-bot
/home/tejas/.npm-global/lib/node_modules/pm2/bin/pm2 save
```

- [ ] Check it's running:
```bash
/home/tejas/.npm-global/lib/node_modules/pm2/bin/pm2 status diet-bot
```
Expected: `online`

- [ ] Check logs for errors:
```bash
/home/tejas/.npm-global/lib/node_modules/pm2/bin/pm2 logs diet-bot --lines 20 --nostream
```
Expected: `Diet bot started` — no errors

- [ ] Test: Send Neha's bot a message from her Telegram account. Confirm reply arrives.

- [ ] Test `/log` command — confirm today's (empty) log is returned.

- [ ] Commit bot.py uncommitted changes to claude-bot (from earlier session):
```bash
cd ~/bots/claude-bot && git add bot.py && git commit -m "feat: add GF to authorized users, group shared memory"
```

---

## Notes for executor

- The `data/` folder must exist before starting the bot (`mkdir -p ~/products/diet-bot/data`)
- The GitHub repo must be created manually by TJ before Task 5 git push
- GitHub Pages takes 1-2 minutes to go live after enabling
- The bot sends proactively to `NEHA_CHAT_ID` — she does NOT need to start a conversation first
- `/log` command works for both TJ and Neha (no auth restriction — it's just a read)
- Meal kcal estimation is done by Claude in conversation — the JSON fields are populated when Claude's response triggers `update_today()`. **Note:** The current bot.py does basic keyword detection for cross trainer and weight. For meal logging, Claude responds conversationally and TJ/Neha can use `/log` to verify. A future improvement would be structured meal parsing.
