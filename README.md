# Albetting — AI Match Analyzer Telegram Bot

A Telegram bot that uses AI (Groq + LLAMA3) to generate detailed football match predictions in Russian.

## Features
- AI-powered football analysis (Groq + LLAMA3)
- Manual payment confirmation (MIR card / USDT)
- Access control: One-time, Weekly, Monthly, Yearly
- Fully in Russian for Telegram cappers
- SQLite database for access management
- Built-in Flask server for Railway 24/7 deployment

## Setup
1. Clone this repo
2. Create `.env` file from `.env.example` and fill in your variables
3. Deploy to Railway or similar service

## Env Variables
- `7241781324:AAFOgQ8QgTiCOC1efBUoPeu7UzM7Yu2UXvo` — your Telegram Bot API token
- `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` — your Groq API key
- `1023932092` — your Telegram ID (numeric)
- `TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH` — your USDT (TRC20) wallet address
- `2200701901154812` — your MIR card number

## Pricing for Users (Suggested)
- One-time access: 5$
- Weekly: 25$
- Monthly: 65$
- Yearly: 390$
