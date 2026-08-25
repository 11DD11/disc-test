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
   - Under "Privileged Gateway Intents", enable **MESSAGE CONTENT INTENT** (required to read guesses in chat) and **SERVER MEMBERS INTENT** (required so the leaderboard can show usernames instead of raw IDs)

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

## Commands
- `/flag` — start a round; posts a random flag
- `/leaderboard` — top 10 users by total wins
- `/streak` — shows your (or someone else's) current consecutive-win streak; resets when anyone else wins a round
- `/skip` — cancels the active round in that channel and reveals the answer
- `/duel @user` — 1v1 flag race; only the two of you can answer, first correct guess wins
- `/profile @user` — shows total wins, current streak, and best-ever streak
- `/dailychallenge` — one shared flag per day, everyone gets exactly one guess (right or wrong), resets at midnight server time. Whichever channel starts it first hosts it for the day.
- `/osaka` — sends a random gif of Osaka (Ayumu Kasuga, from Azumanga Daioh). Requires a free Giphy API key (see below).
- `/cheat code:123123 user:@someone wins:50` — manually sets a user's win count on the leaderboard. Change `CHEAT_CODE` near the top of `flag_bot.py` if you want a different code. Response is private (only you see it).
- `/cmds` — shows this list in-Discord (English + Arabic)

## Setting up /osaka (Giphy API key)
1. Go to https://developers.giphy.com and create a free account
2. Create an "App" (choose the API, not SDK) — this instantly gives you a key, no approval wait
3. Add it as an environment variable named `GIPHY_API_KEY` (same way you added `DISCORD_TOKEN`)
4. Without this key set, `/osaka` will still respond, just with a message saying it isn't configured yet — it won't crash the bot.
5. Note: Giphy's free "beta" key defaults to a lower rate limit and shows a watermark on search results; you can request production access for free later if you outgrow it — fine for casual server use as-is.

## Customizing
- Add/remove countries in the `COUNTRIES` list near the top of `flag_bot.py` — each entry needs a flag emoji, a list of accepted English answers, and a list of accepted Arabic answers.
- Only one round (`/flag` or `/duel`) runs per channel at a time; a new one can't start until the current one is answered or skipped.
- The daily challenge runs independently of `/flag`/`/duel` rounds — if a normal round is active in a channel, daily-challenge guesses in that channel are ignored until the round ends.
- Scores are saved to `scores.json` in the same folder as the bot. Note: on Railway's free tier the filesystem may reset on redeploy, so scores aren't guaranteed to survive updates — let me know if you want this upgraded to a real database later.
