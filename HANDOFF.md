# diet-bot HANDOFF

## Quick State
**Last session:** 2026-05-10
**Status:** Live. IF schedule active (13:00/21:00). Web dashboard on port 8100. Settings UI working.
**Active branch:** main
**Open todos:** Cloudflare Worker for settings on GitHub Pages (deferred — do when making proper website)

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
- 12:00 — session reset (history cleared, cross trainer flag reset)
- 13:00 — midday check-in (asks what first meal is)
- 21:00 — night check-in (recap everything eaten + exercise) + git push
- Mon 08:00 — weekly weigh-in request
- Times are configurable via settings UI at http://187.124.183.33:8100 (⚙️ button)
- Settings stored in data/settings.json, applied live via apply_schedule()

## Architecture
- bot.py — main bot, APScheduler, claude -p calls, meal extraction, HTTP server on :8100
- memory.py — daily JSON read/write, compact context builder
- push_data.py — git push data/ to GitHub (called at 21:00 + after every meal save)
- data/YYYY-MM-DD.json — daily meal/exercise logs
- data/settings.json — check-in times config (read by bot on startup + /settimes)
- index.html — dashboard (pink/floral, Chart.js). Served from VPS :8100 AND GitHub Pages.
  Settings ⚙️ panel works only on VPS URL (GitHub Pages is HTTPS, VPS API is HTTP — mixed content blocked).
  Cloudflare Worker fix deferred.

## Landmines
- The GitHub Pages site (testclaw97.github.io/diet-tracker) is read-only for settings — Save button fails there due to mixed content. Use http://187.124.183.33:8100 for settings changes.
- claude -p runs with CLAUDE_CONFIG_DIR=.claude-isolated to prevent global hook context leaks into Neha's chat.
- extract_and_save runs in background after every Neha message — triggers a git push if meals were saved. Don't be surprised by frequent commits to diet-tracker repo.

## How meal data is saved
After each Neha message, extract_and_save_meals() runs in background:
- Calls claude -p to extract meal/kcal from conversation
- Saves to data/YYYY-MM-DD.json via memory.update_today()
- Cross trainer + weight also auto-detected from keywords

## In-session memory
5 message pairs per session. Resets at 09:00 each morning.
Cross-session: compact daily summary injected into every prompt (~80 tokens).
