# Diet Coach Bot — Design Spec
**Date:** 2026-04-22  
**Product:** diet-bot (separate product, ~/products/diet-bot/)

---

## User Profile

- **Name:** Neha (Niharika)
- **Telegram ID:** 8701918489
- **Age:** 28 (March 19)
- **Height:** 169cm | **Current weight:** 88kg | **Goal:** 65kg
- **Deadline:** August 10, 2026 (~15 weeks)
- **Daily calorie target:** 1400 kcal, low-carb
- **Cross trainer goal:** 1x per day

---

## Architecture

```
~/products/diet-bot/
├── bot.py          ← Telegram bot + APScheduler + claude -p calls
├── memory.py       ← read/write daily JSON, build compact context block
├── push_data.py    ← git commit + push data/ to GitHub
├── start.sh
├── .env
├── CLAUDE.md
└── REFERENCES.md

~/products/diet-bot/data/
├── YYYY-MM-DD.json     ← daily meal/exercise log
└── YYYY-MM-DD-summary.txt  ← compact context block injected each session
```

**GitHub repo:** `testclaw97/diet-tracker`  
- `data/` folder synced from VPS after each evening session  
- `index.html` + `data.js` served via GitHub Pages  
- **URL:** `https://testclaw97.github.io/diet-tracker/`

**PM2 process:** `diet-bot`

---

## Claude Integration

Same pattern as the private claude-bot — uses `claude -p` (TJ's subscription, no extra API cost).

**System prompt injected per session (loaded from memory.py, ~80 tokens):**
```
You are a warm, encouraging dietitian helping Neha lose weight.
Goal: 88kg → 65kg by Aug 10, 2026. Age 28, 169cm. 1400 kcal/day, low-carb.
[Yesterday: Breakfast: X (kcal). Lunch: X (kcal). Dinner: X (kcal). Snacks: X. Cross trainer: X min. Total: X kcal.]
[Week avg: X kcal/day. Cross trainer: X/7 days this week.]
Be concise, friendly, motivating. No bullet lists in responses.
```

**In-session memory:** 5 message pairs (same as private bot). Resets on restart.  
**Cross-session memory:** Daily summary file, regenerated each morning from previous day's JSON.

---

## Daily Schedule (Europe/Berlin)

| Time | Check-in |
|---|---|
| **09:00** | Morning: 1 specific diet tip based on recent logs + ask today's meal plan + cross trainer plan |
| **16:00** | Afternoon: lunch done? any snacks? free chat for questions/suggestions |
| **22:00** | Evening: dinner check + cross trainer done today? (if not asked yet) → generate summary → push to GitHub |
| **Mon 08:00** | Weekly weigh-in request |

---

## Cross Trainer Tracking

- Bot asks once per day — either at 09:00 (planned?) or 22:00 (did you do it?)
- If answered at 16:00 during free chat, mark done — don't ask again at 22:00
- Stored as: `{ "cross_trainer": true, "cross_trainer_minutes": 35 }`

---

## Data Schema — daily JSON

```json
{
  "date": "2026-04-22",
  "breakfast": "oats with banana",
  "breakfast_kcal": 380,
  "lunch": "chicken salad",
  "lunch_kcal": 450,
  "dinner": "grilled fish + vegetables",
  "dinner_kcal": 520,
  "snacks": "1 biscuit, apple",
  "snacks_kcal": 150,
  "total_kcal": 1500,
  "cross_trainer": true,
  "cross_trainer_minutes": 40,
  "weight_kg": null,
  "notes": ""
}
```

Weight only populated on Mondays after weigh-in.

---

## Dashboard (GitHub Pages)

**Theme:** Pink, floral, soft feminine aesthetic  
**Tech:** Pure HTML + Chart.js + vanilla JS reading JSON from same repo

**Sections:**
1. Today's meals + estimated kcal + cross trainer status
2. 7-day calorie bar chart (pink bars, 1400 kcal goal line)
3. Cross trainer streak + this week count
4. Weight progress: 88kg → 65kg, countdown to Aug 10
5. Last 7 days log table

**Data flow:** Bot writes `data/YYYY-MM-DD.json` → pushes to GitHub at 22:00 → GitHub Pages JS fetches latest JSON on page load.

---

## .env

```
TELEGRAM_TOKEN=REDACTED
NEHA_CHAT_ID=8701918489
```

---

## Out of Scope

- Multi-user support
- Recipe suggestions (just meal tracking + kcal estimates)
- Stripe / payments
- Admin dashboard for Tejas
