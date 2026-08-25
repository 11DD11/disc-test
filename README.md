# Flag Guessing Discord Bot

## What it does
Type `/flag` and the bot posts a random country flag emoji. The first person
to type the correct country name in chat — in **English or Arabic**, any
capitalization, with or without "the"/"ال" — gets a ✅ reaction on their
message and the bot announces the winner.

## Setup

1. **Create a bot application**
   - Go to https://discord.com/developers/applications → New Application
   - Go to the "Bot" tab → click "Reset Token" → copy the token (keep it secret!)
   - Under "Privileged Gateway Intents", enable **MESSAGE CONTENT INTENT** (required to read guesses in chat)

2. **Invite the bot to your server**
   - Go to OAuth2 → URL Generator
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Add Reactions`, `Read Message History`
   - Open the generated URL and add the bot to your server

3. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

4. **Set your token**
   ```
   # Mac/Linux
   export DISCORD_TOKEN="your-token-here"

   # Windows (PowerShell)
   $env:DISCORD_TOKEN="your-token-here"
   ```
   (Or paste it directly into the `TOKEN` variable in `flag_bot.py` — not recommended if you share the file.)

5. **Run it**
   ```
   python flag_bot.py
   ```

6. In Discord, type `/flag` in any channel the bot can see.

## Customizing
- Add/remove countries in the `COUNTRIES` list near the top of `flag_bot.py` — each entry needs a flag emoji, a list of accepted English answers, and a list of accepted Arabic answers.
- Only one round runs per channel at a time; a new `/flag` can't start until the current one is answered.
