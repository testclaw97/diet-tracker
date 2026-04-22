# diet-bot HANDOFF

## Quick State
**Last session:** 2026-04-22
**Status:** Live and running. Neha's first day logged (1660 kcal). Bot responding in group.
**Active branch:** main
**Open todos:** none

## What it is
Telegram diet coaching bot for Neha (TJ's wife). Runs in a private Telegram group with TJ and Neha.

## Key details
- **Bot token:** REDACTED
- **Neha's Telegram ID:** 8701918489
- **TJ's Telegram ID:** 7635405143
- **Group chat ID:** -5116726428
- **PM2 name:** diet-bot (id 8)
- **Dashboard:** https://testclaw97.github.io/diet-tracker/
- **GitHub repo:** git@github.com:testclaw97/diet-tracker.git

## Neha's profile
Age 28, 169cm, 88kg → 65kg by Aug 10 2026. 1400 kcal/day, low-carb. Cross trainer 1x/day.

## Schedule (Europe/Berlin)
- 09:00 — morning check-in (diet tip + meal plan ask + cross trainer ask)
- 16:00 — afternoon check-in (lunch + snacks check)
- 22:00 — evening check-in (dinner + CT check) + git push data to GitHub
- Mon 08:00 — weekly weigh-in request

## Architecture
- bot.py — main bot, APScheduler, claude -p calls, meal extraction
- memory.py — daily JSON read/write, compact context builder
- push_data.py — git push data/ to GitHub at 22:00
- data/YYYY-MM-DD.json — daily meal/exercise logs
- index.html — GitHub Pages dashboard (pink/floral, Chart.js)

## How meal data is saved
After each Neha message, extract_and_save_meals() runs in background:
- Calls claude -p to extract meal/kcal from conversation
- Saves to data/YYYY-MM-DD.json via memory.update_today()
- Cross trainer + weight also auto-detected from keywords

## In-session memory
5 message pairs per session. Resets at 09:00 each morning.
Cross-session: compact daily summary injected into every prompt (~80 tokens).
