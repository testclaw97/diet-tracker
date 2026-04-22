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
