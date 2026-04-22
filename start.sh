#!/bin/bash
cd /home/tejas/products/diet-bot
source .env
export TELEGRAM_TOKEN NEHA_CHAT_ID
python3 bot.py
