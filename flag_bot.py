"""
Flag Guessing Discord Bot
--------------------------
Slash command: /flag
The bot posts a random country flag emoji. The first person to type the
country's name in chat (English or Arabic, any capitalization, with or
without "the"/"ال") gets a ✅ reaction on their message.

Setup:
    1. pip install -r requirements.txt
    2. Set your bot token in the DISCORD_TOKEN environment variable
       (or paste it into TOKEN below — not recommended for shared code).
    3. Run: python flag_bot.py

Make sure "MESSAGE CONTENT INTENT" is enabled for your bot in the
Discord Developer Portal (Bot tab) or the bot won't be able to read
guesses in chat.
"""

import os
import re
import json
import time
import random
import asyncio
import unicodedata
from datetime import date

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------

TOKEN = os.environ.get("DISCORD_TOKEN", "PASTE_YOUR_TOKEN_HERE")

# Code required to use /cheat to manually edit the leaderboard
CHEAT_CODE = "123123"

# Discord username (not nickname/display name) that gets a "(the dev)" tag
# on the leaderboard. Usernames are lowercase-compared.
DEV_USERNAME = "1d_d1"

# Easter egg: replying with just ".", "..", or "..." to a message from this
# specific user posts a gif in response.
DOT_REPLY_TARGET_USER_ID = 1264549467495989269
DOT_REPLY_GIF_URL = "https://cdn.discordapp.com/attachments/805840493011140678/1097885486414045204/1632856392703811584.gif"
DOT_REPLY_TRIGGERS = {".", "..", "..."}

# Optional: your server's ID, for instant slash-command sync to that specific
# server instead of waiting up to ~1hr for a global sync to propagate everywhere.
# Right-click your server icon in Discord (with Developer Mode on) → Copy Server ID.
SYNC_GUILD_ID = os.environ.get("SYNC_GUILD_ID", "")
SYNC_GUILD_ID = int(SYNC_GUILD_ID) if SYNC_GUILD_ID.strip().isdigit() else None

SCORES_FILE = "scores.json"

# ----------------------------------------------------------------------
# PRESENCE / RICH PRESENCE CONFIG
# ----------------------------------------------------------------------
# The "large" and "small" image keys below must match the asset keys you upload
# in the Discord Developer Portal under your app's Rich Presence > Art Assets tab.
# See the README for full setup steps.
PRESENCE_STATUS_TEXT = "just watching :3"
PRESENCE_DETAILS = "Hollow Knight: Silksong"
PRESENCE_STATE = "Exploring Pharloom"
PRESENCE_LARGE_IMAGE_KEY = "silksong_cover"
PRESENCE_LARGE_IMAGE_TEXT = "Hollow Knight: Silksong"
PRESENCE_SMALL_IMAGE_KEY = "hornet_sketch"
PRESENCE_SMALL_IMAGE_TEXT = "Hornet"

# Free API key from https://aistudio.google.com/apikey — no credit card needed.
# Powers /ask. Without it, /ask will tell users it's not configured.
# ----------------------------------------------------------------------
# MUSIC CONFIG
# ----------------------------------------------------------------------

YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch1",
    "source_address": "0.0.0.0",
    # YouTube frequently blocks requests from cloud/datacenter IPs (Railway, AWS, etc.)
    # with a "Sign in to confirm you're not a bot" error. The android client is less
    # likely to trigger that check than the default web client.
    "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
}

# Optional: cookies from a real, logged-in YouTube session, needed when YouTube
# blocks the bot's server with a "Sign in to confirm you're not a bot" error.
#
# Two ways to provide this:
#   1. (Recommended) Set YTDLP_COOKIES_CONTENT to the full contents of a cookies.txt
#      file as an environment variable. The bot writes it to a local file at startup.
#      This keeps the actual cookie data out of your GitHub repo entirely.
#   2. Set YTDLP_COOKIES_FILE to a path to a cookies.txt file already on disk.
#
# See README for how to export cookies.txt from your browser.
YTDLP_COOKIES_CONTENT = os.environ.get("YTDLP_COOKIES_CONTENT", "")
YTDLP_COOKIES_FILE = os.environ.get("YTDLP_COOKIES_FILE", "")

if YTDLP_COOKIES_CONTENT:
    YTDLP_COOKIES_FILE = "/tmp/yt_cookies.txt"
    with open(YTDLP_COOKIES_FILE, "w", encoding="utf-8") as f:
        f.write(YTDLP_COOKIES_CONTENT)

if YTDLP_COOKIES_FILE and os.path.exists(YTDLP_COOKIES_FILE):
    YTDL_OPTS["cookiefile"] = YTDLP_COOKIES_FILE
    print("Using YouTube cookies file for yt-dlp requests.")
else:
    print("No YouTube cookies configured — requests may get blocked by YouTube's bot detection.")

FFMPEG_BEFORE_OPTS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTS = "-vn"

# Default 24/7 lofi livestream (Lofi Girl's long-running stream). Can be overridden
# per-use via the /lofi command's optional "link" parameter.
DEFAULT_LOFI_STREAM = "https://www.youtube.com/watch?v=jfKfPfyJRdk"

# Free API key from https://developers.giphy.com (instant approval for a
# personal/test key) needed for /osaka to pull gifs. Without it, /osaka will
# tell users it's not configured.
GIPHY_API_KEY = os.environ.get("GIPHY_API_KEY", "")
OSAKA_SEARCH_TERMS = ["Osaka Azumanga Daioh", "Ayumu Kasuga anime"]

# ----------------------------------------------------------------------
# COUNTRY DATA: flag emoji -> accepted English names, accepted Arabic names
# ----------------------------------------------------------------------

COUNTRIES = [
    {"flag": "🇧🇭", "en": ["bahrain"], "ar": ["البحرين", "بحرين"]},
    {"flag": "🇸🇦", "en": ["saudi arabia", "saudi", "ksa"], "ar": ["السعودية", "المملكة العربية السعودية", "السعوديه"]},
    {"flag": "🇦🇪", "en": ["united arab emirates", "uae", "emirates"], "ar": ["الإمارات", "الامارات", "الإمارات العربية المتحدة"]},
    {"flag": "🇰🇼", "en": ["kuwait"], "ar": ["الكويت", "كويت"]},
    {"flag": "🇶🇦", "en": ["qatar"], "ar": ["قطر"]},
    {"flag": "🇴🇲", "en": ["oman"], "ar": ["عمان", "عُمان"]},
    {"flag": "🇾🇪", "en": ["yemen"], "ar": ["اليمن", "يمن"]},
    {"flag": "🇮🇶", "en": ["iraq"], "ar": ["العراق", "عراق"]},
    {"flag": "🇯🇴", "en": ["jordan"], "ar": ["الأردن", "الاردن"]},
    {"flag": "🇱🇧", "en": ["lebanon"], "ar": ["لبنان"]},
    {"flag": "🇸🇾", "en": ["syria"], "ar": ["سوريا", "سوريه", "سورية"]},
    {"flag": "🇵🇸", "en": ["palestine"], "ar": ["فلسطين"]},
    {"flag": "🇪🇬", "en": ["egypt"], "ar": ["مصر"]},
    {"flag": "🇱🇾", "en": ["libya"], "ar": ["ليبيا"]},
    {"flag": "🇹🇳", "en": ["tunisia"], "ar": ["تونس"]},
    {"flag": "🇩🇿", "en": ["algeria"], "ar": ["الجزائر", "جزائر"]},
    {"flag": "🇲🇦", "en": ["morocco"], "ar": ["المغرب", "مغرب"]},
    {"flag": "🇸🇩", "en": ["sudan"], "ar": ["السودان", "سودان"]},
    {"flag": "🇸🇴", "en": ["somalia"], "ar": ["الصومال", "صومال"]},
    {"flag": "🇩🇯", "en": ["djibouti"], "ar": ["جيبوتي"]},
    {"flag": "🇲🇷", "en": ["mauritania"], "ar": ["موريتانيا"]},
    {"flag": "🇰🇲", "en": ["comoros"], "ar": ["جزر القمر", "القمر"]},
    {"flag": "🇺🇸", "en": ["united states", "usa", "us", "america"], "ar": ["أمريكا", "امريكا", "الولايات المتحدة"]},
    {"flag": "🇨🇦", "en": ["canada"], "ar": ["كندا"]},
    {"flag": "🇲🇽", "en": ["mexico"], "ar": ["المكسيك", "مكسيك"]},
    {"flag": "🇧🇷", "en": ["brazil"], "ar": ["البرازيل", "برازيل"]},
    {"flag": "🇦🇷", "en": ["argentina"], "ar": ["الأرجنتين", "الارجنتين"]},
    {"flag": "🇬🇧", "en": ["united kingdom", "uk", "britain", "england"], "ar": ["بريطانيا", "المملكة المتحدة", "انجلترا"]},
    {"flag": "🇫🇷", "en": ["france"], "ar": ["فرنسا"]},
    {"flag": "🇩🇪", "en": ["germany"], "ar": ["ألمانيا", "المانيا"]},
    {"flag": "🇮🇹", "en": ["italy"], "ar": ["إيطاليا", "ايطاليا"]},
    {"flag": "🇪🇸", "en": ["spain"], "ar": ["إسبانيا", "اسبانيا"]},
    {"flag": "🇵🇹", "en": ["portugal"], "ar": ["البرتغال", "برتغال"]},
    {"flag": "🇳🇱", "en": ["netherlands", "holland"], "ar": ["هولندا"]},
    {"flag": "🇧🇪", "en": ["belgium"], "ar": ["بلجيكا"]},
    {"flag": "🇨🇭", "en": ["switzerland"], "ar": ["سويسرا"]},
    {"flag": "🇸🇪", "en": ["sweden"], "ar": ["السويد", "سويد"]},
    {"flag": "🇳🇴", "en": ["norway"], "ar": ["النرويج", "نرويج"]},
    {"flag": "🇩🇰", "en": ["denmark"], "ar": ["الدنمارك", "دنمارك"]},
    {"flag": "🇫🇮", "en": ["finland"], "ar": ["فنلندا"]},
    {"flag": "🇵🇱", "en": ["poland"], "ar": ["بولندا"]},
    {"flag": "🇬🇷", "en": ["greece"], "ar": ["اليونان", "يونان"]},
    {"flag": "🇹🇷", "en": ["turkey", "turkiye"], "ar": ["تركيا"]},
    {"flag": "🇷🇺", "en": ["russia"], "ar": ["روسيا"]},
    {"flag": "🇺🇦", "en": ["ukraine"], "ar": ["أوكرانيا", "اوكرانيا"]},
    {"flag": "🇮🇪", "en": ["ireland"], "ar": ["أيرلندا", "ايرلندا"]},
    {"flag": "🇦🇹", "en": ["austria"], "ar": ["النمسا", "نمسا"]},
    {"flag": "🇨🇳", "en": ["china"], "ar": ["الصين", "صين"]},
    {"flag": "🇯🇵", "en": ["japan"], "ar": ["اليابان", "يابان"]},
    {"flag": "🇰🇷", "en": ["south korea", "korea"], "ar": ["كوريا الجنوبية", "كوريا"]},
    {"flag": "🇮🇳", "en": ["india"], "ar": ["الهند", "هند"]},
    {"flag": "🇵🇰", "en": ["pakistan"], "ar": ["باكستان"]},
    {"flag": "🇧🇩", "en": ["bangladesh"], "ar": ["بنغلاديش"]},
    {"flag": "🇮🇩", "en": ["indonesia"], "ar": ["إندونيسيا", "اندونيسيا"]},
    {"flag": "🇲🇾", "en": ["malaysia"], "ar": ["ماليزيا"]},
    {"flag": "🇸🇬", "en": ["singapore"], "ar": ["سنغافورة"]},
    {"flag": "🇹🇭", "en": ["thailand"], "ar": ["تايلاند", "تايلند"]},
    {"flag": "🇻🇳", "en": ["vietnam"], "ar": ["فيتنام"]},
    {"flag": "🇵🇭", "en": ["philippines"], "ar": ["الفلبين", "فلبين"]},
    {"flag": "🇮🇷", "en": ["iran"], "ar": ["إيران", "ايران"]},
    {"flag": "🇦🇫", "en": ["afghanistan"], "ar": ["أفغانستان", "افغانستان"]},
    {"flag": "🇮🇱", "en": ["israel"], "ar": ["إسرائيل", "اسرائيل"]},
    {"flag": "🇿🇦", "en": ["south africa"], "ar": ["جنوب أفريقيا", "جنوب افريقيا"]},
    {"flag": "🇳🇬", "en": ["nigeria"], "ar": ["نيجيريا"]},
    {"flag": "🇰🇪", "en": ["kenya"], "ar": ["كينيا"]},
    {"flag": "🇪🇹", "en": ["ethiopia"], "ar": ["إثيوبيا", "اثيوبيا"]},
    {"flag": "🇬🇭", "en": ["ghana"], "ar": ["غانا"]},
    {"flag": "🇦🇺", "en": ["australia"], "ar": ["أستراليا", "استراليا"]},
    {"flag": "🇳🇿", "en": ["new zealand"], "ar": ["نيوزيلندا"]},
    {"flag": "🇨🇺", "en": ["cuba"], "ar": ["كوبا"]},
    {"flag": "🇨🇴", "en": ["colombia"], "ar": ["كولومبيا"]},
    {"flag": "🇨🇱", "en": ["chile"], "ar": ["تشيلي"]},
    {"flag": "🇵🇪", "en": ["peru"], "ar": ["بيرو"]},
    {"flag": "🇻🇪", "en": ["venezuela"], "ar": ["فنزويلا"]},
    {"flag": "🇮🇸", "en": ["iceland"], "ar": ["آيسلندا", "ايسلندا"]},
    {"flag": "🇨🇿", "en": ["czech republic", "czechia"], "ar": ["التشيك", "تشيك"]},
    {"flag": "🇭🇺", "en": ["hungary"], "ar": ["المجر", "مجر"]},
    {"flag": "🇷🇴", "en": ["romania"], "ar": ["رومانيا"]},
]

# ----------------------------------------------------------------------
# NORMALIZATION HELPERS
# ----------------------------------------------------------------------

ARABIC_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")


def normalize_arabic(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = ARABIC_DIACRITICS.sub("", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه")
    text = text.replace("ى", "ي")
    text = text.replace("ـ", "")  # tatweel
    text = text.strip()
    # strip leading "ال" (the) so "البحرين" and "بحرين" both match
    if text.startswith("ال") and len(text) > 2:
        text = text[2:]
    return text


def normalize_english(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"^\s*the\s+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def build_answer_key(country: dict) -> dict:
    """Precompute normalized accepted answers for fast matching."""
    en_norm = {normalize_english(a) for a in country["en"]}
    ar_norm = {normalize_arabic(a) for a in country["ar"]}
    return {"en": en_norm, "ar": ar_norm}


for c in COUNTRIES:
    c["_norm"] = build_answer_key(c)


def is_correct_guess(message_content: str, country: dict) -> bool:
    norm_en = normalize_english(message_content)
    if norm_en in country["_norm"]["en"]:
        return True
    norm_ar = normalize_arabic(message_content)
    if norm_ar in country["_norm"]["ar"]:
        return True
    return False


def find_country_by_name(name: str) -> dict:
    """Looks up a country by English or Arabic name, reusing the same matching
    logic as guesses. Used by /flag's optional cheat-code override."""
    norm_en = normalize_english(name)
    norm_ar = normalize_arabic(name)
    for country in COUNTRIES:
        if norm_en in country["_norm"]["en"] or norm_ar in country["_norm"]["ar"]:
            return country
    return None


# ----------------------------------------------------------------------
# BOT SETUP
# ----------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Safety net: ensures a command never leaves the user stuck on 'thinking...' forever."""
    print(f"Command error in /{interaction.command.name if interaction.command else '?'}: {error}")
    message = "Something went wrong running that command. Please try again."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass

# channel_id -> currently active country dict (or None if no round running)
active_rounds: dict[int, dict] = {}

# guild_id -> list of {"title": str, "url": str, "requester": str} waiting to play
song_queues: dict[int, list] = {}

# guild_id -> {"title": str, "requester": str} currently playing, or None
now_playing: dict[int, dict] = {}

# guild_id -> True while 24/7 lofi mode is active for that guild
lofi_mode: dict[int, bool] = {}

# guild_id -> the stream link currently used for that guild's lofi mode
lofi_stream_link: dict[int, str] = {}

# guild_id -> volume multiplier, 0.0 to 2.0 (default 1.0 = 100%)
guild_volume: dict[int, float] = {}

# Global daily challenge state (one shared challenge across the bot, hosted
# in whichever channel first ran /dailychallenge that day)
daily_challenge = {
    "date": None,
    "country": None,
    "channel_id": None,
    "winner_id": None,
    "attempted": set(),
}

# ----------------------------------------------------------------------
# SCORE / STREAK PERSISTENCE
# ----------------------------------------------------------------------
# scores structure:
# {
#   "user_id_str": {"wins": int, "streak": int}
# }
# "streak" = that user's current number of consecutive round wins.
# Note: on most free hosts (Railway included) the filesystem is not
# guaranteed to persist across redeploys. For permanent storage across
# restarts/redeploys, swap this out for a small database later.


def load_scores() -> dict:
    if os.path.exists(SCORES_FILE):
        try:
            with open(SCORES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_scores(scores: dict) -> None:
    try:
        with open(SCORES_FILE, "w", encoding="utf-8") as f:
            json.dump(scores, f, indent=2)
    except OSError as e:
        print(f"Failed to save scores: {e}")


scores: dict = load_scores()


def record_win(user_id: int) -> None:
    """Increment the winner's wins + streak, and reset everyone else's streak."""
    uid = str(user_id)
    for other_id, data in scores.items():
        if other_id != uid:
            data["streak"] = 0

    entry = scores.setdefault(uid, {"wins": 0, "streak": 0, "best_streak": 0})
    entry.setdefault("best_streak", 0)
    entry["wins"] += 1
    entry["streak"] += 1
    entry["best_streak"] = max(entry["best_streak"], entry["streak"])
    save_scores(scores)


@bot.event
async def on_ready():
    try:
        # A global sync (bot.tree.sync() with no guild) can take up to an hour to
        # reach every member's client — this is why newly added commands like
        # /tictactoe sometimes don't show up for everyone right away, even though
        # the bot itself is running fine. If SYNC_GUILD_ID is set, we additionally
        # copy commands to that specific server for near-instant propagation there.
        synced = await bot.tree.sync()
        print(f"Globally synced {len(synced)} slash command(s) (can take up to ~1hr to reach all clients).")

        if SYNC_GUILD_ID:
            guild_obj = discord.Object(id=SYNC_GUILD_ID)
            bot.tree.copy_global_to(guild=guild_obj)
            guild_synced = await bot.tree.sync(guild=guild_obj)
            print(f"Instantly synced {len(guild_synced)} command(s) to guild {SYNC_GUILD_ID}.")
    except Exception as e:
        print(f"Slash command sync failed: {e}")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    try:
        app_id = bot.application_id or (await bot.application_info()).id
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=PRESENCE_STATUS_TEXT,
            details=PRESENCE_DETAILS,
            state=PRESENCE_STATE,
            application_id=app_id,
            assets={
                "large_image": PRESENCE_LARGE_IMAGE_KEY,
                "large_text": PRESENCE_LARGE_IMAGE_TEXT,
                "small_image": PRESENCE_SMALL_IMAGE_KEY,
                "small_text": PRESENCE_SMALL_IMAGE_TEXT,
            },
        )
        await bot.change_presence(status=discord.Status.online, activity=activity)
    except Exception as e:
        print(f"Failed to set presence: {e}")


@bot.tree.command(name="flag", description="Guess the country's flag! First correct answer wins.")
@app_commands.describe(code="psst", country="psst (only works with the code)")
async def flag_command(interaction: discord.Interaction, code: str = None, country: str = None):
    channel_id = interaction.channel_id

    if active_rounds.get(channel_id):
        await interaction.response.send_message(
            "A flag round is already in progress in this channel! 🏳️", ephemeral=True
        )
        return

    chosen_country = None
    if code == CHEAT_CODE and country:
        chosen_country = find_country_by_name(country)
        if chosen_country is None:
            await interaction.response.send_message(
                f"Couldn't find a country matching '{country}'.", ephemeral=True
            )
            return
    elif code is not None and code != CHEAT_CODE:
        await interaction.response.send_message("❌ Incorrect code.", ephemeral=True)
        return

    if chosen_country is None:
        chosen_country = random.choice(COUNTRIES)

    active_rounds[channel_id] = chosen_country

    await interaction.response.send_message(
        f"**Guess the flag!** 🌍 (English or Arabic)\n\n# {chosen_country['flag']}"
    )


@bot.tree.command(name="leaderboard", description="Show the top flag-guessers.")
async def leaderboard_command(interaction: discord.Interaction):
    if not scores:
        await interaction.response.send_message("No one has scored yet — start a round with `/flag`!")
        return

    ranked = sorted(scores.items(), key=lambda kv: kv[1]["wins"], reverse=True)[:10]

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, data) in enumerate(ranked):
        member = None
        if interaction.guild:
            member = interaction.guild.get_member(int(uid))
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(int(uid))
                except discord.HTTPException:
                    member = None

        if member:
            name = member.display_name
            if member.name.lower() == DEV_USERNAME:
                name += " (the dev)"
        else:
            name = f"User {uid}"

        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{prefix} **{name}** — {data['wins']} win(s)")

    embed = discord.Embed(title="🏆 Flag Leaderboard", description="\n".join(lines), color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="streak", description="Show the current top winning streak, or your own.")
@app_commands.describe(user="Check someone else's streak (optional)")
async def streak_command(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    entry = scores.get(str(target.id))

    if not entry or entry["streak"] == 0:
        await interaction.response.send_message(f"{target.display_name} doesn't have an active streak.")
        return

    await interaction.response.send_message(f"🔥 {target.display_name}'s current streak: **{entry['streak']}**")


@bot.tree.command(name="skip", description="Cancel the current flag round and reveal the answer.")
async def skip_command(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    country = active_rounds.get(channel_id)

    if not country:
        await interaction.response.send_message("There's no active flag round to skip.", ephemeral=True)
        return

    active_rounds[channel_id] = None
    en_name = country["en"][0].title()
    ar_name = country["ar"][0]
    await interaction.response.send_message(
        f"⏭️ Round skipped. {country['flag']} was **{en_name}** ({ar_name})"
    )


@bot.tree.command(name="duel", description="Challenge someone to a 1v1 flag race — only you two can answer.")
@app_commands.describe(opponent="Who you want to duel")
async def duel_command(interaction: discord.Interaction, opponent: discord.Member):
    channel_id = interaction.channel_id

    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You can't duel yourself!", ephemeral=True)
        return
    if opponent.bot:
        await interaction.response.send_message("You can't duel a bot!", ephemeral=True)
        return

    if active_rounds.get(channel_id):
        await interaction.response.send_message(
            "A round is already in progress in this channel! 🏳️", ephemeral=True
        )
        return

    country = dict(random.choice(COUNTRIES))
    country["_duel_players"] = {interaction.user.id, opponent.id}
    active_rounds[channel_id] = country

    await interaction.response.send_message(
        f"⚔️ **Duel!** {interaction.user.mention} vs {opponent.mention}\n"
        f"Only you two can answer. First correct guess wins!\n\n# {country['flag']}"
    )


@bot.tree.command(name="profile", description="Show a player's flag-game stats.")
@app_commands.describe(user="Whose profile to check (optional)")
async def profile_command(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    entry = scores.get(str(target.id), {"wins": 0, "streak": 0, "best_streak": 0})

    embed = discord.Embed(title=f"📊 {target.display_name}'s Profile", color=discord.Color.blue())
    if target.display_avatar:
        embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Total Wins", value=str(entry.get("wins", 0)), inline=True)
    embed.add_field(name="Current Streak", value=str(entry.get("streak", 0)), inline=True)
    embed.add_field(name="Best Streak", value=str(entry.get("best_streak", 0)), inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="dailychallenge", description="Play today's shared flag challenge — one guess per person.")
async def dailychallenge_command(interaction: discord.Interaction):
    today = date.today().isoformat()

    if daily_challenge["date"] != today:
        # New day: generate a fresh challenge, same for everyone regardless of
        # which channel starts it, using the date as a deterministic seed.
        seeded_random = random.Random(today)
        daily_challenge["date"] = today
        daily_challenge["country"] = seeded_random.choice(COUNTRIES)
        daily_challenge["channel_id"] = interaction.channel_id
        daily_challenge["winner_id"] = None
        daily_challenge["attempted"] = set()

        await interaction.response.send_message(
            "🌅 **Today's Daily Challenge!** Everyone gets ONE guess (English or Arabic). "
            f"Resets at midnight.\n\n# {daily_challenge['country']['flag']}"
        )
        return

    # Same day, challenge already exists somewhere
    if daily_challenge["winner_id"] is not None:
        winner = interaction.guild.get_member(daily_challenge["winner_id"]) if interaction.guild else None
        winner_name = winner.display_name if winner else f"User {daily_challenge['winner_id']}"
        country = daily_challenge["country"]
        await interaction.response.send_message(
            f"Today's challenge is already solved! {country['flag']} was **{country['en'][0].title()}** "
            f"({country['ar'][0]}) — guessed first by **{winner_name}**. Come back tomorrow!"
        )
        return

    if interaction.channel_id != daily_challenge["channel_id"]:
        channel_mention = f"<#{daily_challenge['channel_id']}>"
        await interaction.response.send_message(
            f"Today's challenge is already running in {channel_mention} — head over there to guess!",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"Today's challenge is still open here! You get one guess.\n\n# {daily_challenge['country']['flag']}"
    )


@bot.tree.command(name="osaka", description="Get a random Osaka (Ayumu Kasuga) gif!")
async def osaka_command(interaction: discord.Interaction):
    if not GIPHY_API_KEY:
        await interaction.response.send_message(
            "The bot owner hasn't set up a Giphy API key yet, so `/osaka` isn't available. "
            "(Free key at developers.giphy.com — add it as the GIPHY_API_KEY variable.)",
            ephemeral=True,
        )
        return

    await interaction.response.defer()

    query = random.choice(OSAKA_SEARCH_TERMS)
    url = "https://api.giphy.com/v1/gifs/search"
    params = {
        "api_key": GIPHY_API_KEY,
        "q": query,
        "limit": 30,
        "rating": "g",  # safe-for-work only
        "lang": "en",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    await interaction.followup.send("Couldn't reach Giphy right now, try again in a bit.")
                    return
                data = await resp.json()
    except (aiohttp.ClientError, TimeoutError):
        await interaction.followup.send("Couldn't reach Giphy right now, try again in a bit.")
        return

    results = data.get("data", [])
    if not results:
        await interaction.followup.send("Couldn't find an Osaka gif right now, try again!")
        return

    choice = random.choice(results)
    gif_url = choice.get("images", {}).get("original", {}).get("url")

    if not gif_url:
        await interaction.followup.send("Couldn't find an Osaka gif right now, try again!")
        return

    await interaction.followup.send(gif_url)


@bot.tree.command(name="ask", description="Ask the bot's AI a question.")
@app_commands.describe(question="What do you want to ask?")
async def ask_command(interaction: discord.Interaction, question: str):
    await interaction.response.send_message("its under development still", ephemeral=True)


@bot.tree.command(name="cheat", description="Admin only: manually edit a user's leaderboard wins with a code.")
@app_commands.describe(code="The access code", user="User to edit", wins="New win count to set for this user")
async def cheat_command(interaction: discord.Interaction, code: str, user: discord.Member, wins: int):
    if code != CHEAT_CODE:
        await interaction.response.send_message("❌ Incorrect code.", ephemeral=True)
        return

    if wins < 0:
        await interaction.response.send_message("Wins can't be negative.", ephemeral=True)
        return

    uid = str(user.id)
    entry = scores.setdefault(uid, {"wins": 0, "streak": 0})
    entry["wins"] = wins
    save_scores(scores)

    await interaction.response.send_message(
        f"✅ Set **{user.display_name}**'s wins to **{wins}**.", ephemeral=True
    )


# ----------------------------------------------------------------------
# QUOTE COMMAND
# ----------------------------------------------------------------------

QUOTES = [
    {"text": "Believe it!", "source": "Naruto Uzumaki, Naruto"},
    {"text": "I am going to be the King of the Pirates!", "source": "Monkey D. Luffy, One Piece"},
    {"text": "Plus Ultra!", "source": "All Might, My Hero Academia"},
    {"text": "It's not the size of your power, but how you use it.", "source": "Izuku Midoriya, My Hero Academia"},
    {"text": "People's lives don't end when they die.", "source": "Itachi Uchiha, Naruto"},
    {"text": "I'll take a potato chip... and eat it!", "source": "Light Yagami, Death Note"},
    {"text": "A lesson without pain is meaningless.", "source": "Edward Elric, Fullmetal Alchemist"},
    {"text": "Whatever happens, happens.", "source": "Spike Spiegel, Cowboy Bebop"},
    {"text": "Hard work is worthless for those that don't believe in themselves.", "source": "Naruto Uzumaki, Naruto"},
    {"text": "The only ones who should kill are those prepared to be killed.", "source": "Lelouch Lamperouge, Code Geass"},
    {"text": "In this world, wherever there is light, there are also shadows.", "source": "Yuki Ashikaga, Fate/stay night"},
    {"text": "If you don't take risks, you can't create a future.", "source": "Monkey D. Luffy, One Piece"},
    {"text": "I don't want to conquer anything. I just think the guy with the most freedom is the Pirate King!", "source": "Monkey D. Luffy, One Piece"},
    {"text": "Fear is not evil. It tells you what your weakness is.", "source": "Gildarts Clive, Fairy Tail"},
    {"text": "The world isn't perfect, but it's there for us, doing the best it can.", "source": "Roy Mustang, Fullmetal Alchemist"},
    {"text": "It's OK to cry, everyone needs to cry sometimes.", "source": "Nanako Dojima, Persona 4"},
    {"text": "War, war never changes.", "source": "Narrator, Fallout"},
    {"text": "It's dangerous to go alone! Take this.", "source": "Old Man, The Legend of Zelda"},
    {"text": "Stay determined.", "source": "Undertale"},
    {"text": "The flame that burns twice as bright burns half as long.", "source": "Nyx Ulric, Final Fantasy XV"},
    {"text": "You've died. Would you like to know why?", "source": "Sans, Undertale"},
    {"text": "Hey, listen!", "source": "Navi, The Legend of Zelda: Ocarina of Time"},
    {"text": "A man chooses, a slave obeys.", "source": "Andrew Ryan, BioShock"},
    {"text": "Praise the sun!", "source": "Solaire of Astora, Dark Souls"},
    {"text": "It's dangerous business, going out your front door.", "source": "Bilbo Baggins-style, Fantasy Trope"},
    {"text": "Do you even science, bro?", "source": "Senku Ishigami, Dr. Stone"},
    {"text": "Ten years from now, I'll still remember this.", "source": "Kirito, Sword Art Online"},
    {"text": "The world's not perfect, but there are things worth protecting.", "source": "Roy Mustang, Fullmetal Alchemist"},
    {"text": "I refuse.", "source": "Emma, The Promised Neverland"},
    {"text": "Get a grip, and move forward.", "source": "Simon, Gurren Lagann"},
    {"text": "Row row, fight the power!", "source": "Gurren Lagann"},
    {"text": "This is the police! Nobody move!", "source": "Osaka, Azumanga Daioh"},
]


@bot.tree.command(name="quote", description="Get a random anime or video game quote.")
async def quote_command(interaction: discord.Interaction):
    quote = random.choice(QUOTES)
    await interaction.response.send_message(f'*"{quote["text"]}"*\n— {quote["source"]}')


# ----------------------------------------------------------------------
# TIC-TAC-TOE
# ----------------------------------------------------------------------

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: "TicTacToeView" = self.view

        if interaction.user.id not in (view.player_x.id, view.player_o.id):
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        if interaction.user.id != view.current_player.id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        if view.board[self.y][self.x] != 0:
            await interaction.response.send_message("That spot's already taken!", ephemeral=True)
            return

        mark = 1 if interaction.user.id == view.player_x.id else 2
        view.board[self.y][self.x] = mark
        self.label = "❌" if mark == 1 else "⭕"
        self.style = discord.ButtonStyle.danger if mark == 1 else discord.ButtonStyle.primary
        self.disabled = True

        winner = view.check_winner()
        if winner:
            for child in view.children:
                child.disabled = True
            winner_user = view.player_x if winner == 1 else view.player_o
            await interaction.response.edit_message(content=f"🎉 {winner_user.mention} wins!", view=view)
            view.stop()
            return

        if view.is_draw():
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content="🤝 It's a draw!", view=view)
            view.stop()
            return

        view.current_player = view.player_o if view.current_player.id == view.player_x.id else view.player_x
        turn_mark = "❌" if view.current_player.id == view.player_x.id else "⭕"
        await interaction.response.edit_message(
            content=f"{view.current_player.mention}'s turn ({turn_mark})", view=view
        )


class TicTacToeView(discord.ui.View):
    def __init__(self, player_x: discord.Member, player_o: discord.Member):
        super().__init__(timeout=300)
        self.player_x = player_x
        self.player_o = player_o
        self.current_player = player_x
        self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        self.message: discord.Message = None

        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_winner(self):
        b = self.board
        lines = list(b)  # rows
        lines += [[b[r][c] for r in range(3)] for c in range(3)]  # columns
        lines.append([b[i][i] for i in range(3)])  # diagonal
        lines.append([b[i][2 - i] for i in range(3)])  # anti-diagonal

        for line in lines:
            if line[0] != 0 and line[0] == line[1] == line[2]:
                return line[0]
        return None

    def is_draw(self) -> bool:
        return all(cell != 0 for row in self.board for cell in row)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="⏱️ Game timed out.", view=self)
            except discord.HTTPException:
                pass


@bot.tree.command(name="tictactoe", description="Challenge someone to a game of Tic-Tac-Toe.")
@app_commands.describe(opponent="Who you want to play against")
async def tictactoe_command(interaction: discord.Interaction, opponent: discord.Member):
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You can't play against yourself!", ephemeral=True)
        return
    if opponent.bot:
        await interaction.response.send_message("You can't play against a bot!", ephemeral=True)
        return

    view = TicTacToeView(interaction.user, opponent)
    await interaction.response.send_message(
        f"❌ {interaction.user.mention} vs ⭕ {opponent.mention}\n{interaction.user.mention}'s turn (❌)",
        view=view,
    )
    view.message = await interaction.original_response()


# ----------------------------------------------------------------------
# CHESS
# ----------------------------------------------------------------------
# Uses the python-chess library for move legality, check/checkmate/stalemate
# detection, etc. — writing correct chess rules from scratch (castling, en
# passant, promotion, check detection) is a project in itself, and this is a
# well-tested standard library for it.
#
# UI note: a chess board has 64 squares, but Discord caps a message at 25
# total components, so a button-per-square grid (like /tictactoe) isn't
# possible here. Instead, moves are made via two chained dropdowns:
# "pick a piece to move" -> "pick where to move it".

import chess as chesslib

# Classic brown/tan checkerboard tiles for the board display. Discord has no
# dedicated "tan" square emoji, so orange stands in for the light squares.
LIGHT_SQUARE = "🟧"
DARK_SQUARE = "🟫"

CHESS_PIECE_SYMBOLS = {
    (chesslib.PAWN, True): "♙", (chesslib.PAWN, False): "♟",
    (chesslib.KNIGHT, True): "♘", (chesslib.KNIGHT, False): "♞",
    (chesslib.BISHOP, True): "♗", (chesslib.BISHOP, False): "♝",
    (chesslib.ROOK, True): "♖", (chesslib.ROOK, False): "♜",
    (chesslib.QUEEN, True): "♕", (chesslib.QUEEN, False): "♛",
    (chesslib.KING, True): "♔", (chesslib.KING, False): "♚",
}

FILE_LABELS = ["🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭"]

# channel_id -> ChessView, so only one game runs per channel at a time
chess_games: dict[int, "ChessView"] = {}


class ChessFromSelect(discord.ui.Select):
    def __init__(self, game: "ChessView"):
        super().__init__(placeholder="Select a piece to move...", min_values=1, max_values=1,
                          options=[discord.SelectOption(label="Loading...", value="none")])
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        game = self.game
        if interaction.user.id != game.current_player.id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        value = self.values[0]
        if value == "none":
            await interaction.response.send_message("No legal moves available.", ephemeral=True)
            return

        origin_square = chesslib.parse_square(value)
        game.selected_origin = origin_square

        dest_options = []
        seen = set()
        for move in game.board.legal_moves:
            if move.from_square == origin_square:
                dest_name = chesslib.square_name(move.to_square)
                if dest_name in seen:
                    continue  # collapse duplicate promotion-choice moves to the same square
                seen.add(dest_name)
                captured = game.board.piece_at(move.to_square)
                label = f"→ {dest_name}" + (f" (captures {captured.symbol().upper()})" if captured else "")
                dest_options.append(discord.SelectOption(label=label[:100], value=dest_name))

        game.to_select.options = dest_options[:25]
        game.to_select.disabled = False
        game.to_select.placeholder = f"Move {value} to..."

        await game.refresh_message(interaction)


class ChessToSelect(discord.ui.Select):
    def __init__(self, game: "ChessView"):
        super().__init__(placeholder="Pick a piece first", min_values=1, max_values=1,
                          options=[discord.SelectOption(label="Pick a piece first", value="none")], disabled=True)
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        game = self.game
        if interaction.user.id != game.current_player.id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        if game.selected_origin is None or self.values[0] == "none":
            await interaction.response.send_message("Pick a piece to move first.", ephemeral=True)
            return

        dest_square = chesslib.parse_square(self.values[0])
        move = chesslib.Move(game.selected_origin, dest_square)

        if move not in game.board.legal_moves:
            # Auto-promote to queen if this move is only legal as a promotion.
            promo_move = chesslib.Move(game.selected_origin, dest_square, promotion=chesslib.QUEEN)
            if promo_move in game.board.legal_moves:
                move = promo_move
            else:
                await interaction.response.send_message("That's not a legal move.", ephemeral=True)
                return

        game.board.push(move)
        game.selected_origin = None
        game.to_select.disabled = True
        game.to_select.options = [discord.SelectOption(label="Pick a piece first", value="none")]
        game.to_select.placeholder = "Pick a piece first"

        if game.board.is_checkmate():
            winner = game.white if game.board.turn == chesslib.BLACK else game.black
            await game.end_game(interaction, f"🏆 Checkmate! {winner.mention} wins!")
            return
        if game.board.is_stalemate() or game.board.is_insufficient_material():
            await game.end_game(interaction, "🤝 Draw.")
            return

        game.refresh_from_options()
        await game.refresh_message(interaction)


class ChessResignButton(discord.ui.Button):
    def __init__(self, game: "ChessView"):
        super().__init__(label="Resign", style=discord.ButtonStyle.danger, row=2)
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        game = self.game
        if interaction.user.id not in (game.white.id, game.black.id):
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        winner = game.black if interaction.user.id == game.white.id else game.white
        await game.end_game(interaction, f"🏳️ {interaction.user.mention} resigned. {winner.mention} wins!")


class ChessView(discord.ui.View):
    def __init__(self, white: discord.Member, black: discord.Member, channel_id: int):
        super().__init__(timeout=1800)  # 30 min — chess games run long
        self.board = chesslib.Board()
        self.white = white
        self.black = black
        self.channel_id = channel_id
        self.message: discord.Message = None
        self.selected_origin = None

        self.from_select = ChessFromSelect(self)
        self.to_select = ChessToSelect(self)
        self.add_item(self.from_select)
        self.add_item(self.to_select)
        self.add_item(ChessResignButton(self))

        self.refresh_from_options()

    @property
    def current_player(self) -> discord.Member:
        return self.white if self.board.turn == chesslib.WHITE else self.black

    def refresh_from_options(self):
        options = []
        for square in chesslib.SQUARES:
            piece = self.board.piece_at(square)
            if piece and piece.color == self.board.turn:
                if any(m.from_square == square for m in self.board.legal_moves):
                    name = chesslib.square_name(square)
                    options.append(discord.SelectOption(label=f"{piece.unicode_symbol()} {name}", value=name))
        if not options:
            options = [discord.SelectOption(label="No moves available", value="none")]
        self.from_select.options = options[:25]
        self.from_select.placeholder = "Select a piece to move..."

    def board_display(self) -> str:
        file_header = "⬛" + "".join(FILE_LABELS)
        rows = [file_header]

        for rank in range(7, -1, -1):
            cells = []
            for file in range(8):
                square = chesslib.square(file, rank)
                is_light = (rank + file) % 2 == 1
                tile = LIGHT_SQUARE if is_light else DARK_SQUARE
                piece = self.board.piece_at(square)
                if piece:
                    tile += CHESS_PIECE_SYMBOLS[(piece.piece_type, piece.color)]
                cells.append(tile)
            rank_label = f"{rank + 1}️⃣"
            rows.append(rank_label + "".join(cells))

        return "\n".join(rows)

    def status_line(self) -> str:
        turn_name = "White" if self.board.turn == chesslib.WHITE else "Black"
        check_note = " — Check!" if self.board.is_check() else ""
        return f"**{turn_name}'s turn** ({self.current_player.mention}){check_note}"

    def header(self) -> str:
        return f"♟️ {self.white.mention} (White) vs {self.black.mention} (Black)"

    async def refresh_message(self, interaction: discord.Interaction):
        content = f"{self.header()}\n{self.board_display()}\n{self.status_line()}"
        await interaction.response.edit_message(content=content, view=self)

    async def end_game(self, interaction: discord.Interaction, result_text: str):
        for child in self.children:
            child.disabled = True
        content = f"{self.header()}\n{self.board_display()}\n{result_text}"
        await interaction.response.edit_message(content=content, view=self)
        chess_games.pop(self.channel_id, None)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content=self.message.content + "\n\n⏱️ Game timed out from inactivity.", view=self)
            except discord.HTTPException:
                pass
        chess_games.pop(self.channel_id, None)


@bot.tree.command(name="chess", description="Challenge someone to a game of chess.")
@app_commands.describe(opponent="Who you want to play against")
async def chess_command(interaction: discord.Interaction, opponent: discord.Member):
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You can't play against yourself!", ephemeral=True)
        return
    if opponent.bot:
        await interaction.response.send_message("You can't play against a bot!", ephemeral=True)
        return
    if interaction.channel_id in chess_games:
        await interaction.response.send_message(
            "There's already a chess game running in this channel!", ephemeral=True
        )
        return

    game = ChessView(interaction.user, opponent, interaction.channel_id)
    chess_games[interaction.channel_id] = game

    content = f"{game.header()}\n{game.board_display()}\n{game.status_line()}"
    await interaction.response.send_message(content=content, view=game)
    game.message = await interaction.original_response()


# ----------------------------------------------------------------------
# ROCK PAPER SCISSORS
# ----------------------------------------------------------------------
# Both players pick secretly and simultaneously: the challenger gets a private
# (ephemeral) picker right away, and the opponent gets one after clicking a
# public "make your choice" button. Neither sees the other's pick until both
# have chosen, at which point the public message reveals the result.

RPS_BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
RPS_EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}


class RPSGame:
    def __init__(self, player1: discord.Member, player2: discord.Member):
        self.player1 = player1
        self.player2 = player2
        self.choices: dict[int, str] = {}
        self.public_message: discord.Message = None

    def both_chosen(self) -> bool:
        return self.player1.id in self.choices and self.player2.id in self.choices

    async def reveal_result(self):
        c1 = self.choices[self.player1.id]
        c2 = self.choices[self.player2.id]

        if c1 == c2:
            result_text = f"🤝 It's a tie! Both chose {RPS_EMOJI[c1]} {c1.title()}."
        else:
            winner = self.player1 if RPS_BEATS[c1] == c2 else self.player2
            result_text = (
                f"{self.player1.mention} chose {RPS_EMOJI[c1]} {c1.title()}\n"
                f"{self.player2.mention} chose {RPS_EMOJI[c2]} {c2.title()}\n\n"
                f"🎉 {winner.mention} wins!"
            )

        if self.public_message:
            try:
                await self.public_message.edit(
                    content=f"✊✋✌️ Rock Paper Scissors\n\n{result_text}", view=None
                )
            except discord.HTTPException:
                pass


class RPSChoiceView(discord.ui.View):
    def __init__(self, game: RPSGame, player: discord.Member):
        super().__init__(timeout=120)
        self.game = game
        self.player = player

    async def handle_choice(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("This isn't your choice to make!", ephemeral=True)
            return
        if self.player.id in self.game.choices:
            await interaction.response.send_message("You already chose!", ephemeral=True)
            return

        self.game.choices[self.player.id] = choice
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=f"You chose {RPS_EMOJI[choice]} {choice.title()}! Waiting for the other player...",
            view=self,
        )

        if self.game.both_chosen():
            await self.game.reveal_result()

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.secondary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.secondary)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.secondary)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "scissors")


class RPSStartView(discord.ui.View):
    """Public message view — the opponent clicks this to get their own private picker."""

    def __init__(self, game: RPSGame):
        super().__init__(timeout=120)
        self.game = game

    @discord.ui.button(label="Make Your Choice", style=discord.ButtonStyle.primary, emoji="🎮")
    async def choose(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.player2.id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        if self.game.player2.id in self.game.choices:
            await interaction.response.send_message("You already made your choice!", ephemeral=True)
            return

        view = RPSChoiceView(self.game, self.game.player2)
        await interaction.response.send_message("Pick your move:", view=view, ephemeral=True)


@bot.tree.command(name="rps", description="Challenge someone to Rock Paper Scissors.")
@app_commands.describe(opponent="Who you want to challenge")
async def rps_command(interaction: discord.Interaction, opponent: discord.Member):
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
        return
    if opponent.bot:
        await interaction.response.send_message("You can't challenge a bot!", ephemeral=True)
        return

    game = RPSGame(interaction.user, opponent)

    challenger_view = RPSChoiceView(game, interaction.user)
    await interaction.response.send_message("Pick your move:", view=challenger_view, ephemeral=True)

    start_view = RPSStartView(game)
    public_msg = await interaction.followup.send(
        f"✊✋✌️ {interaction.user.mention} has challenged {opponent.mention} to Rock Paper Scissors!\n"
        f"{opponent.mention}, click below to make your secret choice.",
        view=start_view,
    )
    game.public_message = public_msg


@bot.tree.command(name="cmds", description="Show all available commands.")
async def cmds_command(interaction: discord.Interaction):
    embed_en = discord.Embed(
        title="📜 Available Commands",
        color=discord.Color.blurple(),
    )
    embed_en.add_field(
        name="/flag",
        value="Starts a round! The bot posts a random flag — first person to type the country name (English or Arabic) wins.",
        inline=False,
    )
    embed_en.add_field(
        name="/leaderboard",
        value="Shows the top 10 players by total wins.",
        inline=False,
    )
    embed_en.add_field(
        name="/streak",
        value="Shows your (or someone else's) current win streak. Streaks reset when someone else wins a round.",
        inline=False,
    )
    embed_en.add_field(
        name="/skip",
        value="Cancels the current round in this channel and reveals the answer.",
        inline=False,
    )
    embed_en.add_field(
        name="/duel",
        value="Challenge another user to a 1v1 flag race — only you two can answer.",
        inline=False,
    )
    embed_en.add_field(
        name="/profile",
        value="Shows a player's total wins, current streak, and best streak ever.",
        inline=False,
    )
    embed_en.add_field(
        name="/dailychallenge",
        value="One shared flag challenge per day — everyone gets a single guess. Resets at midnight.",
        inline=False,
    )
    embed_en.add_field(
        name="/osaka",
        value="Sends a random Osaka (Ayumu Kasuga) gif.",
        inline=False,
    )
    embed_en.add_field(
        name="/ask",
        value="its under development still",
        inline=False,
    )
    embed_en.add_field(
        name="/quote",
        value="Sends a random anime or video game quote.",
        inline=False,
    )
    embed_en.add_field(
        name="/tictactoe",
        value="Challenge another user to Tic-Tac-Toe with clickable buttons.",
        inline=False,
    )
    embed_en.add_field(
        name="/chess",
        value="Challenge another user to a full game of chess using dropdown menus to move pieces.",
        inline=False,
    )
    embed_en.add_field(
        name="/rps",
        value="Challenge another user to Rock Paper Scissors. Both pick secretly and simultaneously.",
        inline=False,
    )
    embed_en.add_field(
        name="/cheat",
        value="shhh...youre not supposed to use this only for me :3",
        inline=False,
    )
    embed_en.add_field(
        name="/cmds",
        value="Shows this list.",
        inline=False,
    )

    embed_ar = discord.Embed(
        title="📜 الأوامر المتاحة",
        color=discord.Color.blurple(),
    )
    embed_ar.add_field(
        name="/flag",
        value="يبدأ جولة جديدة! يرسل البوت علماً عشوائياً — أول شخص يكتب اسم الدولة (بالإنجليزية أو العربية) يفوز.",
        inline=False,
    )
    embed_ar.add_field(
        name="/leaderboard",
        value="يعرض أفضل 10 لاعبين حسب عدد الفوز.",
        inline=False,
    )
    embed_ar.add_field(
        name="/streak",
        value="يعرض سلسلة انتصاراتك الحالية (أو سلسلة شخص آخر). تُعاد السلسلة إلى الصفر عند فوز شخص آخر بجولة.",
        inline=False,
    )
    embed_ar.add_field(
        name="/skip",
        value="يلغي الجولة الحالية في هذه القناة ويكشف الإجابة.",
        inline=False,
    )
    embed_ar.add_field(
        name="/duel",
        value="تحدَّ شخصاً آخر في مبارزة أعلام 1 ضد 1 — أنتما فقط تستطيعان الإجابة.",
        inline=False,
    )
    embed_ar.add_field(
        name="/profile",
        value="يعرض إجمالي فوز اللاعب، سلسلته الحالية، وأفضل سلسلة حققها.",
        inline=False,
    )
    embed_ar.add_field(
        name="/dailychallenge",
        value="تحدي علم مشترك يومياً — كل شخص له محاولة واحدة فقط. يتجدد كل منتصف ليل.",
        inline=False,
    )
    embed_ar.add_field(
        name="/osaka",
        value="يرسل صورة متحركة عشوائية لشخصية أوساكا (أيومو كاسوغا).",
        inline=False,
    )
    embed_ar.add_field(
        name="/ask",
        value="لا يزال قيد التطوير",
        inline=False,
    )
    embed_ar.add_field(
        name="/quote",
        value="يرسل اقتباساً عشوائياً من الأنمي أو ألعاب الفيديو.",
        inline=False,
    )
    embed_ar.add_field(
        name="/tictactoe",
        value="تحدَّ شخصاً آخر في لعبة إكس-أو بأزرار قابلة للنقر.",
        inline=False,
    )
    embed_ar.add_field(
        name="/chess",
        value="تحدَّ شخصاً آخر في لعبة شطرنج كاملة باستخدام القوائم المنسدلة لتحريك القطع.",
        inline=False,
    )
    embed_ar.add_field(
        name="/rps",
        value="تحدَّ شخصاً آخر في لعبة حجر ورقة مقص. كل لاعب يختار بسرية وفي نفس الوقت.",
        inline=False,
    )
    embed_ar.add_field(
        name="/cheat",
        value="ششش... ما يفترض تستخدمه، بس لي أنا :3",
        inline=False,
    )
    embed_ar.add_field(
        name="/cmds",
        value="يعرض هذه القائمة.",
        inline=False,
    )

    await interaction.response.send_message(embed=embed_en)
    await interaction.followup.send(embed=embed_ar)


async def handle_dot_reply_easter_egg(message: discord.Message):
    """If someone replies with just '.', '..', or '...' to a message from
    DOT_REPLY_TARGET_USER_ID, post the configured gif."""
    if message.content.strip() not in DOT_REPLY_TRIGGERS:
        return
    if not message.reference:
        return

    replied_to = message.reference.resolved
    if replied_to is None:
        try:
            replied_to = await message.channel.fetch_message(message.reference.message_id)
        except (discord.NotFound, discord.HTTPException):
            return

    if isinstance(replied_to, discord.DeletedReferencedMessage):
        return

    if replied_to.author.id == DOT_REPLY_TARGET_USER_ID:
        try:
            await message.channel.send(DOT_REPLY_GIF_URL)
        except discord.HTTPException:
            pass


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    await handle_dot_reply_easter_egg(message)

    channel_id = message.channel.id
    country = active_rounds.get(channel_id)

    if country:
        duel_players = country.get("_duel_players")
        if duel_players and message.author.id not in duel_players:
            # Ignore chatter from anyone not in the duel — don't react at all.
            pass
        elif is_correct_guess(message.content, country):
            active_rounds[channel_id] = None
            try:
                await message.add_reaction("✅")
            except discord.HTTPException:
                pass

            record_win(message.author.id)
            new_streak = scores[str(message.author.id)]["streak"]

            en_name = country["en"][0].title()
            ar_name = country["ar"][0]
            streak_note = f" 🔥 Streak: {new_streak}" if new_streak > 1 else ""
            await message.channel.send(
                f"🎉 {message.author.mention} got it! {country['flag']} was **{en_name}** ({ar_name}){streak_note}"
            )
        else:
            try:
                await message.add_reaction("❌")
            except discord.HTTPException:
                pass
    else:
        # No normal/duel round active here — check the daily challenge instead.
        today = date.today().isoformat()
        if (
            daily_challenge["date"] == today
            and daily_challenge["channel_id"] == channel_id
            and daily_challenge["winner_id"] is None
            and message.author.id not in daily_challenge["attempted"]
        ):
            daily_challenge["attempted"].add(message.author.id)
            dc_country = daily_challenge["country"]

            if is_correct_guess(message.content, dc_country):
                daily_challenge["winner_id"] = message.author.id
                try:
                    await message.add_reaction("✅")
                except discord.HTTPException:
                    pass

                record_win(message.author.id)
                en_name = dc_country["en"][0].title()
                ar_name = dc_country["ar"][0]
                await message.channel.send(
                    f"🌟 {message.author.mention} solved today's Daily Challenge! "
                    f"{dc_country['flag']} was **{en_name}** ({ar_name})"
                )
            else:
                try:
                    await message.add_reaction("❌")
                except discord.HTTPException:
                    pass

    await bot.process_commands(message)


if __name__ == "__main__":
    if TOKEN == "PASTE_YOUR_TOKEN_HERE":
        print("⚠️  Set the DISCORD_TOKEN environment variable or edit TOKEN in this file.")
    bot.run(TOKEN)
