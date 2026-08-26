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
- `/ask <question>` — ask the bot's AI anything. Requires a free Google Gemini API key (see below). Has an 8-second per-user cooldown to avoid burning through the free daily quota.
- `/queue` — shows the current song and up to 10 upcoming
- `/nowplaying` — shows the currently playing song
- `/cheat code:123123 user:@someone wins:50` — manually sets a user's win count on the leaderboard. Change `CHEAT_CODE` near the top of `flag_bot.py` if you want a different code. Response is private (only you see it).
- `/cmds` — shows this list in-Discord (English + Arabic)

## Music commands
- `/play <link or search>` — joins your voice channel and plays a YouTube link, a Spotify **track** link, or a plain search term (e.g. "bohemian rhapsody"). If something's already playing, it queues instead.
- `/vskip` — skips the current song
- `/stop` — stops playback, clears the queue, and leaves the voice channel
- `/queue` / `/nowplaying` — see above
- `/join <channel>` — moves the bot into a specific voice channel directly. This also stops any active 24/7 lofi loop and clears the queue.
- `/lofi <channel> [link]` — starts a 24/7 lofi radio loop in the given voice channel. Plays a default lofi livestream (or your own YouTube link if you pass one) on repeat indefinitely, until you move the bot with `/join` or interrupt it with `/play`.
- `/panel` — posts an interactive control panel with buttons: ⏯️ Play/Pause, ⏭️ Skip, 🔉/🔊 Volume, ⏹️ Stop. Volume adjusts live without restarting the current track. Note: this panel only works while the bot process stays running — if Railway redeploys, run `/panel` again to get a fresh working one.

**How Spotify links work:** Spotify doesn't allow any app to stream actual audio through its API — only official Spotify apps can do that. So `/play` reads the track's public title from Spotify's embed metadata (no API key needed) and searches YouTube for that title, then plays the best match. This works well for popular/official tracks but occasionally picks a cover or lyric video if the exact original isn't easy to find. Only single-track links are supported, not playlists or albums.

**Required setup for music to work:**
1. **Bot permissions** — when generating your invite URL (OAuth2 → URL Generator), make sure `Connect` and `Speak` are checked under Bot Permissions, in addition to the ones from step 2 in Setup above.
2. **System dependencies** — voice playback needs `ffmpeg` and `libopus0` installed on the host, which pip can't provide. If you're on Railway, the included `nixpacks.toml` file handles this automatically — just make sure it's uploaded to your repo alongside the other files. If running locally, install ffmpeg yourself (e.g. `sudo apt install ffmpeg libopus0` on Linux, `brew install ffmpeg opus` on Mac).
3. **A quick legal note:** pulling audio from YouTube this way (via `yt-dlp`) is technically against YouTube's Terms of Service, even though it's extremely common practice for hobby Discord bots. Worth knowing if you ever run this at a larger scale.

## Setting up /osaka (Giphy API key)
1. Go to https://developers.giphy.com and create a free account
2. Create an "App" (choose the API, not SDK) — this instantly gives you a key, no approval wait
3. Add it as an environment variable named `GIPHY_API_KEY` (same way you added `DISCORD_TOKEN`)
4. Without this key set, `/osaka` will still respond, just with a message saying it isn't configured yet — it won't crash the bot.
5. Note: Giphy's free "beta" key defaults to a lower rate limit and shows a watermark on search results; you can request production access for free later if you outgrow it — fine for casual server use as-is.

## Setting up /ask (Google Gemini API key)
1. Go to https://aistudio.google.com/apikey and sign in with a Google account
2. Click "Create API key" — it's instant, no card required, and the free tier doesn't expire
3. Add it as an environment variable named `GEMINI_API_KEY`
4. Free tier gives you 1,500 requests/day on the model this bot uses (`gemini-2.5-flash`) — plenty for a personal server
5. Without this key set, `/ask` will still respond, just with a message saying it isn't configured yet
6. Note: on the free tier, Google may use your prompts to improve their models. If that matters to you, this is documented on their pricing page.

## Customizing
- Add/remove countries in the `COUNTRIES` list near the top of `flag_bot.py` — each entry needs a flag emoji, a list of accepted English answers, and a list of accepted Arabic answers.
- Only one round (`/flag` or `/duel`) runs per channel at a time; a new one can't start until the current one is answered or skipped.
- The daily challenge runs independently of `/flag`/`/duel` rounds — if a normal round is active in a channel, daily-challenge guesses in that channel are ignored until the round ends.
- Scores are saved to `scores.json` in the same folder as the bot. Note: on Railway's free tier the filesystem may reset on redeploy, so scores aren't guaranteed to survive updates — let me know if you want this upgraded to a real database later.
