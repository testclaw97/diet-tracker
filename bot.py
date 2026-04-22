#!/usr/bin/env python3
import asyncio
import logging
import os
import re
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
GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])
TEJAS_ID = 7635405143
AUTHORIZED_IDS = {NEHA_CHAT_ID, TEJAS_ID}
BERLIN = ZoneInfo("Europe/Berlin")
WORKDIR = "/home/tejas/products/diet-bot"

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

session_history = []
cross_trainer_done_today = False

SYSTEM_PROMPT = """You are Neha's personal dietitian and health coach. You are warm, encouraging, and professional.
Neha's profile: Age 28, 169cm, current weight ~88kg, goal 65kg by August 10 2026.
Daily target: 1400 kcal, low-carb diet. Cross trainer: 1x per day goal.
Key rules:
- Estimate calories for any food Neha mentions (be realistic, not optimistic)
- Gently flag if she is close to or over 1400 kcal without being harsh
- Be concise — max 3-4 sentences unless she asks for more
- Speak naturally, like a caring friend who is also a professional
- If she asks for meal suggestions, make them low-carb and within her remaining kcal budget
- Never use bullet lists in scheduled check-in messages — keep them conversational
- If she mentions eating something unhealthy, acknowledge it kindly and move on — no guilt
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

    today_parts = []
    if today.get("breakfast"):
        today_parts.append(f"Breakfast: {today['breakfast']} ({today['breakfast_kcal']} kcal)")
    if today.get("lunch"):
        today_parts.append(f"Lunch: {today['lunch']} ({today['lunch_kcal']} kcal)")
    if today.get("dinner"):
        today_parts.append(f"Dinner: {today['dinner']} ({today['dinner_kcal']} kcal)")
    if today.get("snacks"):
        today_parts.append(f"Snacks: {today['snacks']} ({today['snacks_kcal']} kcal)")
    remaining = 1400 - today.get("total_kcal", 0)
    today_parts.append(f"Remaining kcal budget: {remaining}")
    today_line = ". ".join(today_parts) if today_parts else "Nothing logged yet today."

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


async def keep_typing(bot, chat_id):
    while True:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(4)


# ── Scheduled jobs ────────────────────────────────────────────────

async def morning_checkin(app):
    global session_history, cross_trainer_done_today
    session_history = []
    cross_trainer_done_today = False
    mem = memory.build_memory_block()
    today_name = datetime.now(BERLIN).strftime("%A")
    prompt = (
        f"{SYSTEM_PROMPT}\n{mem}\n"
        f"It is 9am on {today_name} in Berlin. Write a warm morning check-in for Neha.\n"
        f"Include: 1) One specific, actionable diet tip based on her recent logs "
        f"(if no logs yet, give a good low-carb breakfast idea). "
        f"2) Ask what she plans to eat today. "
        f"3) Ask if she plans to do cross trainer today. "
        f"Keep it friendly, short, conversational — no bullet points, max 4 sentences."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=response)
    session_history.append(("(morning check-in)", response))
    log.info("Morning check-in sent")


async def afternoon_checkin(app):
    today = memory.load_day(memory.today_str())
    mem = memory.build_memory_block()
    prompt = (
        f"{SYSTEM_PROMPT}\n{mem}\n"
        f"[Today so far: breakfast logged: {'yes — ' + str(today.get('breakfast','')) if today.get('breakfast') else 'no'}, "
        f"lunch logged: {'yes — ' + str(today.get('lunch','')) if today.get('lunch') else 'no'}]\n"
        f"It is 4pm. Write a brief friendly afternoon check-in. "
        f"If lunch isn't logged, ask about it. Ask if she had any snacks or sweets. "
        f"Keep it to 2 sentences max — short and warm."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=response)
    session_history.append(("(afternoon check-in)", response))
    log.info("Afternoon check-in sent")


async def evening_checkin(app):
    today = memory.load_day(memory.today_str())
    mem = memory.build_memory_block()
    ct_done = today.get("cross_trainer", False) or cross_trainer_done_today
    prompt = (
        f"{SYSTEM_PROMPT}\n{mem}\n"
        f"[Today: breakfast: {today.get('breakfast') or 'not logged'}, "
        f"lunch: {today.get('lunch') or 'not logged'}, "
        f"dinner: {today.get('dinner') or 'not logged'}, "
        f"total kcal so far: {today.get('total_kcal', 0)}, "
        f"cross trainer: {'done' if ct_done else 'not recorded yet'}]\n"
        f"It is 10pm. Write a warm evening check-in. "
        f"Ask about dinner if not logged. "
        + ("" if ct_done else "Ask if she did cross trainer today. ")
        + "If she has logged meals, give a brief summary of today — was it a good day? "
        f"End with one encouraging sentence for tomorrow. Max 4 sentences."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=response)
    session_history.append(("(evening check-in)", response))

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, push_data.push_to_github)
    log.info("Evening check-in sent + data pushed")


async def monday_weighin(app):
    weight_info = memory.get_latest_weight()
    prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"[Latest weight: {weight_info}]\n"
        f"It is Monday morning. Ask Neha gently for her weekly weigh-in. "
        f"Remind her the number is just information, not a judgment. "
        f"One or two sentences only."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=response)
    log.info("Monday weigh-in request sent")


# ── Meal extraction ───────────────────────────────────────────────

async def extract_and_save_meals(user_text: str, bot_response: str):
    prompt = (
        f"Extract meal data from this conversation. Output ONLY valid JSON or the word null.\n\n"
        f"User said: {user_text}\n"
        f"Dietitian estimated: {bot_response}\n\n"
        f"If food was mentioned, output JSON like:\n"
        f'[{{"meal":"breakfast","description":"oats with banana","kcal":380}}]\n'
        f"meal must be one of: breakfast, lunch, dinner, snacks\n"
        f"Multiple meals in one message = multiple objects in the array.\n"
        f"If no food was mentioned, output: null"
    )
    raw = await run_claude(prompt)
    try:
        raw = raw.strip()
        if raw.lower() == "null" or not raw.startswith("["):
            return
        import json as _json
        meals = _json.loads(raw)
        for m in meals:
            meal_key = m.get("meal")
            if meal_key not in ("breakfast", "lunch", "dinner", "snacks"):
                continue
            memory.update_today(**{
                meal_key: m.get("description", ""),
                f"{meal_key}_kcal": int(m.get("kcal", 0))
            })
            log.info(f"Saved {meal_key}: {m.get('description')} ({m.get('kcal')} kcal)")
    except Exception as e:
        log.warning(f"Meal extraction failed: {e} — raw: {raw[:100]}")


# ── Message handler ───────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global cross_trainer_done_today
    if update.effective_user.id not in AUTHORIZED_IDS:
        return
    text = update.message.text or ""
    if not text:
        return

    log.info(f"Message from Neha: {text[:80]}")
    text_lower = text.lower()

    # Cross trainer auto-detection
    if any(w in text_lower for w in ["cross trainer", "crosstrainer", "training", "sport", "workout"]):
        if any(w in text_lower for w in ["yes", "ja", "done", "did", "finished", "gemacht", "made"]):
            mins_match = re.search(r"(\d+)\s*(?:min|minute)", text_lower)
            minutes = int(mins_match.group(1)) if mins_match else 30
            memory.update_today(cross_trainer=True, cross_trainer_minutes=minutes)
            cross_trainer_done_today = True

    # Weight auto-detection (e.g. "I'm 86kg" or "86.5 kg")
    weight_match = re.search(r"\b(\d{2,3}(?:[.,]\d)?)\s*kg\b", text_lower)
    if weight_match and not any(w in text_lower for w in ["goal", "target", "ziel", "wanna", "want"]):
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

    # Extract and save meal data in background
    asyncio.create_task(extract_and_save_meals(text, response))


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = memory.load_day(memory.today_str())
    msg = (
        f"Today ({today['date']}):\n"
        f"Breakfast: {today.get('breakfast') or '—'} ({today.get('breakfast_kcal', 0)} kcal)\n"
        f"Lunch: {today.get('lunch') or '—'} ({today.get('lunch_kcal', 0)} kcal)\n"
        f"Dinner: {today.get('dinner') or '—'} ({today.get('dinner_kcal', 0)} kcal)\n"
        f"Snacks: {today.get('snacks') or '—'} ({today.get('snacks_kcal', 0)} kcal)\n"
        f"Total: {today.get('total_kcal', 0)} / 1400 kcal\n"
        f"Cross trainer: {'✅ ' + str(today.get('cross_trainer_minutes', 0)) + 'min' if today.get('cross_trainer') else '❌'}\n"
        f"Weight: {today.get('weight_kg') or '—'} kg"
    )
    await update.message.reply_text(msg)


# ── Main ──────────────────────────────────────────────────────────

scheduler = AsyncIOScheduler(timezone=BERLIN)


async def post_init(app):
    scheduler.start()
    log.info("Diet bot started")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("log", cmd_log))

    scheduler.add_job(morning_checkin, "cron", hour=9, minute=0, args=[app])
    scheduler.add_job(afternoon_checkin, "cron", hour=16, minute=0, args=[app])
    scheduler.add_job(evening_checkin, "cron", hour=22, minute=0, args=[app])
    scheduler.add_job(monday_weighin, "cron", day_of_week="mon", hour=8, minute=0, args=[app])

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
