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
- `/flag` — start a round; posts a random flag. Has hidden optional `code`/`country` parameters: entering the correct code (same as `/cheat`'s) alongside a country name lets you pick that flag yourself instead of getting a random one. Wrong code shows a private error; no code just behaves normally.
- `/leaderboard` — top 10 users by total wins
- `/streak` — shows your (or someone else's) current consecutive-win streak; resets when anyone else wins a round
- `/skip` — cancels the active round in that channel and reveals the answer
- `/duel @user` — 1v1 flag race; only the two of you can answer, first correct guess wins
- `/profile @user` — shows total wins, current streak, and best-ever streak
- `/dailychallenge` — one shared flag per day, everyone gets exactly one guess (right or wrong), resets at midnight server time. Whichever channel starts it first hosts it for the day.
- `/osaka` — sends a random gif of Osaka (Ayumu Kasuga, from Azumanga Daioh). Requires a free Giphy API key (see below).
- `/ask <question>` — currently a placeholder; replies "its under development still" regardless of what's asked.
- `/quote` — sends a random short anime or video game quote from a curated list.
- `/tictactoe @user` — challenges another member to Tic-Tac-Toe with a clickable 3x3 button grid. Only the two players can click; the game times out after 5 minutes of inactivity.
- `/chess @user` — challenges another member to a full game of chess. Moves are made via two dropdown menus: pick a piece, then pick where to move it (a chess board has 64 squares, more than Discord's 25-component-per-message limit, so a button grid like Tic-Tac-Toe isn't possible here — dropdowns are the workaround). Handles check, checkmate, stalemate, castling, en passant, and promotion (auto-promotes to queen, no under-promotion choice). Includes a Resign button. Games time out after 30 minutes of inactivity.
- `/rps @user` — challenges another member to Rock Paper Scissors. Both players pick secretly and simultaneously: the challenger gets a private picker immediately, and the opponent gets one after clicking a public "Make Your Choice" button. Neither sees the other's pick until both have chosen. Expires after 2 minutes if someone doesn't respond.
- `/cheat code:123123 user:@someone wins:50` — manually sets a user's win count on the leaderboard. Change `CHEAT_CODE` near the top of `flag_bot.py` if you want a different code. Response is private (only you see it).
- `/cmds` — shows this list in-Discord (English + Arabic)

## Bot status / Rich Presence

The bot shows a custom "Watching just watching :3" status, and clicking on its profile shows an expanded Rich Presence card with Silksong artwork and details.

**Important limitation:** bots can only broadcast one activity at a time — there's no way to show a separate status text and a separate "Playing X" line simultaneously. What this setup actually does is attach the Silksong images/details to the *same* activity as the "just watching :3" text, so the one-line status under the bot's name reads "Watching just watching :3", while the expanded profile card (what people see when they click on the bot) shows the Silksong cover art, the Hornet sketch, and the details/state lines.

**Setup (required, takes ~2 minutes):**
1. Go to https://discord.com/developers/applications and open your bot's application
2. Go to **Rich Presence → Art Assets** in the left sidebar
3. Click **Add Image(s)** and upload both files from the `rich_presence_assets` folder:
   - `silksong_cover.jpg` → give it the asset key **`silksong_cover`** (must match exactly, lowercase)
   - `hornet_sketch.webp` → give it the asset key **`hornet_sketch`** (must match exactly, lowercase)
4. Save. No code changes needed — the keys are already set in `flag_bot.py` under the `PRESENCE_*` constants near the top, so if you want different key names, update them there too.
5. Restart the bot. It sets its presence automatically on startup (in `on_ready`).

If you ever want to change the status text, game title, or swap the images, everything lives in the `PRESENCE_*` constants near the top of `flag_bot.py` — no need to touch the rest of the code.

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

## If some members can't see a command (e.g. /tictactoe)

This is a Discord platform quirk, not a bug in the bot. Global slash-command syncing (which happens automatically on every bot startup) can take **up to an hour** to reach every member's client after a command is added or changed — some people will see it instantly, others won't until their client refreshes.

**To make new commands appear instantly for your own server instead of waiting:**
1. Turn on Developer Mode in Discord: Settings → Advanced → Developer Mode
2. Right-click your server's icon → **Copy Server ID**
3. Add an environment variable `SYNC_GUILD_ID` with that ID as the value
4. Redeploy — the bot will now sync commands to that specific server instantly on every startup, in addition to the normal (slower) global sync for any other servers it's in

If commands still don't show up for someone after that, have them fully restart their Discord app (not just switch servers) — the client caches the command list locally.

## Easter egg: dot-reply gif
If anyone replies with just `.`, `..`, or `...` to a message from the user with ID `1264549467495989269`, the bot posts a specific gif in response. The target user ID and gif URL are set via `DOT_REPLY_TARGET_USER_ID` and `DOT_REPLY_GIF_URL` near the top of `flag_bot.py` if you ever want to change them. This triggers for anyone's reply, not just a specific person's — let me know if you'd rather restrict who can trigger it.

## Easter egg: voice message on mention
Whenever the user with ID `764457716110327809` is @mentioned by anyone in a message, the bot responds with a real **voice message** — the blue waveform bubble you can play back, not a regular audio file attachment.

**Technical note:** Discord's own API supports voice messages (it's documented behavior — a message flag plus `duration_secs`/`waveform` fields on the attachment), but discord.py doesn't have built-in high-level support for *sending* them yet. So this feature makes a raw HTTP request directly to Discord's API using the bot's own token, bypassing discord.py's normal `send()` method. This is legitimate use of a documented Discord feature, not a workaround of anything restricted.

**Setup:** the audio clip is bundled at `assets/dev_voice_clip.ogg` — already converted to match Discord's exact spec (mono, 48kHz, Opus) with a real waveform preview pre-computed from the actual audio (not fake/random data). Nothing to configure; just make sure that file is uploaded to your repo alongside the code. To change the clip or the target user, edit `VOICE_MENTION_TARGET_USER_ID` and `VOICE_CLIP_PATH` near the top of `flag_bot.py` — note that swapping the audio file also means recomputing `VOICE_CLIP_DURATION_SECS` and `VOICE_CLIP_WAVEFORM_B64` to match (ask if you want a new clip converted).

## Removed features
Voice/music commands (`/play`, `/vskip`, `/stop`, `/queue`, `/nowplaying`, `/join`, `/lofi`, `/panel`) have been removed, along with their dependencies (`yt-dlp`, `PyNaCl`, `davey`) and the `nixpacks.toml` file that installed `ffmpeg`/`libopus0` for them. If you want voice features back later, this is recoverable — just ask.
