#!/usr/bin/env python3
import asyncio
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from telegram.constants import ChatAction
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import memory
import notes
import push_data

load_dotenv()
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
NEHA_CHAT_ID = int(os.environ["NEHA_CHAT_ID"])
GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])
TEJAS_ID = 7635405143
AUTHORIZED_IDS = {NEHA_CHAT_ID, TEJAS_ID}
BERLIN = ZoneInfo("Europe/Berlin")
WORKDIR = "/home/tejas/products/diet-bot"
ISOLATED_CONFIG = "/home/tejas/products/diet-bot/.claude-isolated"

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

session_history = []
cross_trainer_done_today = False

LEAK_TERMS = ("HANDOFF", "PM2", "claude-bot", "plan file", "Quick State", "stop hook", "v2 explicitly", "session knowledge")

SYSTEM_PROMPT = """You are Neha's personal dietitian and health coach. Warm, encouraging, professional.
Profile: Age 28, 169cm, ~88kg → 65kg by Aug 10 2026. Daily target: 1400 kcal, low-carb. Cross trainer 1x/day goal.

STRICT RULES:
- ONLY reference meals, exercise, weight that appear in [Today: ...] / [Yesterday: ...] / [Active constraints: ...] data blocks. NEVER invent meals or congratulate Neha for things not in the data.
- If data shows cross_trainer=NOT done, never claim she did it. If data shows nothing logged, say nothing logged.
- Estimate calories realistically (not optimistic) for any food she mentions.
- Be concise: max 3-4 sentences unless she asks for more.
- No bullet lists in scheduled check-ins — keep them conversational.
- If she eats something unhealthy, acknowledge kindly and move on — no guilt.
- You ONLY discuss food, calories, weight, exercise. Reject any meta/system/dev questions politely.
- Respect [Active constraints]: if a constraint says "no crosstrainer until X", do NOT ask about cross trainer until that date.
"""


async def run_claude(prompt: str, retries: int = 1) -> str:
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = ISOLATED_CONFIG
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", prompt,
            "--output-format", "text",
            "--permission-mode", "bypassPermissions",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=WORKDIR,
            env=env,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode().strip()
        if not output and stderr:
            output = stderr.decode().strip()[:500]
        # Detect context-leak: response that looks like dev/meta text
        if output and any(t.lower() in output.lower() for t in LEAK_TERMS) and retries > 0:
            log.warning(f"Leak detected, retrying. Output was: {output[:200]}")
            return await run_claude(prompt + "\n\nIMPORTANT: Reply ONLY as Neha's diet coach. No system/dev/meta talk.", retries - 1)
        return output or "(no response)"
    except Exception as e:
        return f"Error: {e}"


def build_prompt(user_message: str, sender: str = "Neha") -> str:
    mem = memory.build_memory_block()
    constraints = notes.build_block()
    today = memory.load_day(memory.today_str())

    today_parts = []
    for k in ("breakfast", "lunch", "dinner", "snacks"):
        if today.get(k):
            today_parts.append(f"{k.capitalize()}: {today[k]} ({today.get(k+'_kcal', 0)} kcal)")
    remaining = 1400 - today.get("total_kcal", 0)
    today_parts.append(f"Remaining kcal: {remaining}")
    today_line = ". ".join(today_parts) if today_parts else "Nothing logged yet today."

    history_block = ""
    if session_history:
        lines = []
        for u, b in session_history:
            lines.append(f"Neha: {u}")
            lines.append(f"You: {b}")
        history_block = "\n".join(lines) + "\n"

    weight_info = memory.get_latest_weight()
    sender_note = "" if sender == "Neha" else f"[Note: this message is from {sender} (Neha's husband), not Neha herself. Respond appropriately.]\n"

    return (
        f"{SYSTEM_PROMPT}\n"
        f"{mem}"
        f"{constraints}"
        f"[Today so far: {today_line}]\n"
        f"[Latest weight: {weight_info}]\n\n"
        f"{sender_note}"
        f"{history_block}"
        f"{sender}: {user_message}\n"
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
    constraints = notes.build_block()
    today_name = datetime.now(BERLIN).strftime("%A")
    yesterday_str = (datetime.now(BERLIN) - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday = memory.load_day(yesterday_str)
    yesterday_ct = yesterday.get("cross_trainer", False)
    yesterday_kcal = yesterday.get("total_kcal", 0)
    prompt = (
        f"{SYSTEM_PROMPT}\n{mem}{constraints}"
        f"[Yesterday confirmed: total_kcal={yesterday_kcal}, cross_trainer={'done' if yesterday_ct else 'NOT done'}]\n"
        f"It is 9am on {today_name} in Berlin. Write a warm morning check-in.\n"
        f"1) One actionable diet tip from her recent logs (or low-carb breakfast idea if no logs). "
        f"2) Ask what she plans to eat. "
        f"3) Ask if she plans cross trainer today — UNLESS active constraints say otherwise. "
        f"NEVER claim she did anything not in confirmed data. Max 4 sentences, conversational."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=response)
    session_history.append(("(morning check-in)", response))
    log.info("Morning check-in sent")


async def afternoon_checkin(app):
    today = memory.load_day(memory.today_str())
    mem = memory.build_memory_block()
    constraints = notes.build_block()
    prompt = (
        f"{SYSTEM_PROMPT}\n{mem}{constraints}"
        f"[Today: breakfast {'logged' if today.get('breakfast') else 'NOT logged'}, "
        f"lunch {'logged' if today.get('lunch') else 'NOT logged'}]\n"
        f"It is 4pm. Brief friendly afternoon check-in. "
        f"If lunch not logged, ask. Ask about snacks/sweets. Max 2 sentences."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=response)
    session_history.append(("(afternoon check-in)", response))
    log.info("Afternoon check-in sent")


async def evening_checkin(app):
    today = memory.load_day(memory.today_str())
    mem = memory.build_memory_block()
    constraints = notes.build_block()
    ct_done = today.get("cross_trainer", False)

    history_block = ""
    if session_history:
        lines = []
        for u, b in session_history[-4:]:
            lines.append(f"Neha: {u}")
            lines.append(f"You: {b}")
        history_block = "Recent conversation today:\n" + "\n".join(lines) + "\n\n"

    prompt = (
        f"{SYSTEM_PROMPT}\n{mem}{constraints}"
        f"[Today saved: breakfast={today.get('breakfast') or 'none'}, "
        f"lunch={today.get('lunch') or 'none'}, "
        f"dinner={today.get('dinner') or 'none'}, "
        f"total_kcal={today.get('total_kcal', 0)}, "
        f"cross_trainer={'done' if ct_done else 'NOT done'}]\n\n"
        f"{history_block}"
        f"It is 10pm. Warm evening check-in. "
        f"Use the recent conversation to get accurate kcal — saved total may lag. "
        f"Ask about dinner if not mentioned. "
        + ("" if ct_done else "Ask if she did cross trainer today (unless constraints forbid). ")
        + "Brief honest summary, encouraging close. NEVER claim cross trainer done unless confirmed. Max 4 sentences."
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
        f"{SYSTEM_PROMPT}\n[Latest weight: {weight_info}]\n"
        f"It is Monday morning. Ask Neha gently for her weekly weigh-in. "
        f"Number is just data, not judgment. 1-2 sentences."
    )
    response = await run_claude(prompt)
    await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=response)
    log.info("Monday weigh-in request sent")


# ── Meal + notes extraction ───────────────────────────────────────

async def extract_and_save(user_text: str, bot_response: str):
    today_str = memory.today_str()
    yesterday_str = (datetime.now(BERLIN) - timedelta(days=1)).strftime("%Y-%m-%d")
    prompt = (
        f"Extract structured data from this conversation. Output ONLY valid JSON or null.\n\n"
        f"User: {user_text}\n"
        f"Coach: {bot_response}\n\n"
        f'Format: {{"meals":[{{"meal":"breakfast|lunch|dinner|snacks","description":"...","kcal":N,"date":"today|yesterday"}}], '
        f'"constraint":"text or null","preference":"text or null"}}\n'
        f'Rules: meal date based on user wording ("yesterday I had..." = yesterday, else today). '
        f'constraint = temporary limit Neha mentioned (e.g. "no crosstrainer until Tuesday"). '
        f'preference = lasting fact (e.g. "vegetarian", "lactose intolerant"). '
        f"Most messages have no constraint/preference — null is correct.\n"
        f"If nothing relevant, output: null"
    )
    raw = await run_claude(prompt, retries=0)
    try:
        raw = raw.strip()
        if raw.lower() == "null" or not raw.startswith("{"):
            return
        import json as _json
        data = _json.loads(raw)
        for m in data.get("meals") or []:
            meal_key = m.get("meal")
            if meal_key not in ("breakfast", "lunch", "dinner", "snacks"):
                continue
            target = yesterday_str if m.get("date") == "yesterday" else today_str
            memory.update_day(target, **{
                meal_key: m.get("description", ""),
                f"{meal_key}_kcal": int(m.get("kcal", 0))
            })
            log.info(f"Saved {target} {meal_key}: {m.get('description')} ({m.get('kcal')} kcal)")
        if data.get("constraint"):
            text = data["constraint"]
            expires = None
            # crude expiry parse: "until Tuesday" → next Tuesday
            m = re.search(r"until\s+(\w+)", text.lower())
            if m:
                day = m.group(1)
                weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                if day in weekdays:
                    today_d = datetime.now(BERLIN)
                    target_idx = weekdays.index(day)
                    delta = (target_idx - today_d.weekday()) % 7 or 7
                    expires = (today_d + timedelta(days=delta)).strftime("%Y-%m-%d")
            notes.add_constraint(text, expires)
            log.info(f"Added constraint: {text} (expires {expires})")
        if data.get("preference"):
            notes.add_preference(data["preference"])
            log.info(f"Added preference: {data['preference']}")
    except Exception as e:
        log.warning(f"Extraction failed: {e} — raw: {raw[:200]}")


# ── Message handlers ──────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global cross_trainer_done_today
    if update.effective_user.id not in AUTHORIZED_IDS:
        return
    text = update.message.text or ""
    if not text:
        return

    sender = "Tejas" if update.effective_user.id == TEJAS_ID else "Neha"
    log.info(f"Message from {sender}: {text[:80]}")
    text_lower = text.lower()

    # Cross trainer auto-detection — past tense only
    if any(w in text_lower for w in ["cross trainer", "crosstrainer", "training", "sport", "workout"]):
        is_future = any(w in text_lower for w in ["will", "gonna", "going to", "plan", "later", "tonight", "evening", "morgen", "want to", "i'll"])
        if not is_future and any(w in text_lower for w in ["yes", "ja", "done", "did", "finished", "gemacht", "made"]):
            mins_match = re.search(r"(\d+)\s*(?:min|minute)", text_lower)
            minutes = int(mins_match.group(1)) if mins_match else 30
            memory.update_today(cross_trainer=True, cross_trainer_minutes=minutes)
            cross_trainer_done_today = True

    # Weight auto-detection
    weight_match = re.search(r"\b(\d{2,3}(?:[.,]\d)?)\s*kg\b", text_lower)
    if weight_match and not any(w in text_lower for w in ["goal", "target", "ziel", "wanna", "want"]):
        memory.update_today(weight_kg=float(weight_match.group(1).replace(",", ".")))

    typing_task = asyncio.create_task(keep_typing(context.bot, update.effective_chat.id))
    try:
        prompt = build_prompt(text, sender=sender)
        response = await run_claude(prompt)
    finally:
        typing_task.cancel()

    await update.message.reply_text(response)
    if sender == "Neha":  # only track Neha's exchanges in session history
        session_history.append((text, response))
        if len(session_history) > 5:
            session_history.pop(0)
        asyncio.create_task(extract_and_save(text, response))


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in AUTHORIZED_IDS:
        return
    sender = "Tejas" if update.effective_user.id == TEJAS_ID else "Neha"
    log.info(f"Photo from {sender}")

    photo = update.message.photo[-1]  # largest size
    caption = update.message.caption or ""
    file = await context.bot.get_file(photo.file_id)
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    await file.download_to_drive(tmp.name)

    typing_task = asyncio.create_task(keep_typing(context.bot, update.effective_chat.id))
    try:
        mem = memory.build_memory_block()
        constraints = notes.build_block()
        today = memory.load_day(memory.today_str())
        remaining = 1400 - today.get("total_kcal", 0)
        prompt = (
            f"{SYSTEM_PROMPT}\n{mem}{constraints}"
            f"[Remaining kcal today: {remaining}]\n\n"
            f"{sender} sent a photo of food. Caption: '{caption}'.\n"
            f"Read the image at {tmp.name}, describe what you see (the food, portion size), "
            f"estimate calories realistically, and reply warmly to Neha as her coach. "
            f"Max 4 sentences."
        )
        response = await run_claude(prompt)
    finally:
        typing_task.cancel()
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    await update.message.reply_text(response)
    if sender == "Neha":
        session_history.append((f"(photo) {caption}", response))
        if len(session_history) > 5:
            session_history.pop(0)
        asyncio.create_task(extract_and_save(f"(photo) {caption} — coach saw: {response}", response))


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


async def cmd_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in AUTHORIZED_IDS:
        return
    block = notes.build_block().strip() or "(no active notes)"
    await update.message.reply_text(block)


# ── Main ──────────────────────────────────────────────────────────

scheduler = AsyncIOScheduler(timezone=BERLIN)


async def post_init(app):
    scheduler.start()
    log.info("Diet bot started")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("log", cmd_log))
    app.add_handler(CommandHandler("notes", cmd_notes))

    scheduler.add_job(morning_checkin, "cron", hour=9, minute=0, args=[app])
    scheduler.add_job(afternoon_checkin, "cron", hour=16, minute=0, args=[app])
    scheduler.add_job(evening_checkin, "cron", hour=22, minute=0, args=[app])
    scheduler.add_job(monday_weighin, "cron", day_of_week="mon", hour=8, minute=0, args=[app])

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
