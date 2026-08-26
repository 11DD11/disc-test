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
import yt_dlp
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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
ASK_COOLDOWN_SECONDS = 8  # per-user cooldown to avoid burning through the free daily quota

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
}

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


# ----------------------------------------------------------------------
# BOT SETUP
# ----------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

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

# user_id -> unix timestamp of their last /ask call, for cooldown enforcement
ask_last_used: dict[int, float] = {}

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
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
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
async def flag_command(interaction: discord.Interaction):
    channel_id = interaction.channel_id

    if active_rounds.get(channel_id):
        await interaction.response.send_message(
            "A flag round is already in progress in this channel! 🏳️", ephemeral=True
        )
        return

    country = random.choice(COUNTRIES)
    active_rounds[channel_id] = country

    await interaction.response.send_message(
        f"**Guess the flag!** 🌍 (English or Arabic)\n\n# {country['flag']}"
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
    if not GEMINI_API_KEY:
        await interaction.response.send_message(
            "The bot owner hasn't set up a Gemini API key yet, so `/ask` isn't available. "
            "(Free key at aistudio.google.com/apikey — add it as the GEMINI_API_KEY variable.)",
            ephemeral=True,
        )
        return

    now = time.time()
    last_used = ask_last_used.get(interaction.user.id, 0)
    remaining = ASK_COOLDOWN_SECONDS - (now - last_used)
    if remaining > 0:
        await interaction.response.send_message(
            f"Slow down a bit! Try again in {remaining:.0f}s.", ephemeral=True
        )
        return
    ask_last_used[interaction.user.id] = now

    await interaction.response.defer()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    payload = {
        "contents": [{"parts": [{"text": question}]}],
        "generationConfig": {"maxOutputTokens": 500},
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, params=params, json=payload,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    err_msg = data.get("error", {}).get("message", "Unknown error")
                    await interaction.followup.send(f"AI request failed: {err_msg}")
                    return
    except (aiohttp.ClientError, TimeoutError):
        await interaction.followup.send("Couldn't reach the AI right now, try again in a bit.")
        return

    try:
        answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        await interaction.followup.send("The AI didn't return a usable answer — try rephrasing your question.")
        return

    if len(answer) > 1900:
        answer = answer[:1900] + "…"

    await interaction.followup.send(f"**{interaction.user.display_name} asked:** {question}\n\n{answer}")


# ----------------------------------------------------------------------
# MUSIC HELPERS
# ----------------------------------------------------------------------

SPOTIFY_URL_RE = re.compile(r"open\.spotify\.com/(?:intl-\w+/)?track/")
YOUTUBE_URL_RE = re.compile(r"(youtube\.com|youtu\.be)/")


async def resolve_search_query(raw_query: str) -> str:
    """Turn a Spotify track link into a searchable title; pass everything else through."""
    if SPOTIFY_URL_RE.search(raw_query):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://open.spotify.com/oembed",
                    params={"url": raw_query},
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        title = data.get("title")
                        if title:
                            return title
        except (aiohttp.ClientError, TimeoutError):
            pass
        # Fall back to just letting yt-dlp try the raw link, though it likely won't work.
        return raw_query
    return raw_query


async def extract_track_info(query: str) -> dict | None:
    """Run yt-dlp (blocking) in a thread and return info about the best match."""
    loop = asyncio.get_running_loop()

    def _extract():
        with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
            info = ydl.extract_info(query, download=False)
            if info and "entries" in info:
                entries = [e for e in info["entries"] if e]
                if not entries:
                    return None
                info = entries[0]
            return info

    try:
        return await loop.run_in_executor(None, _extract)
    except yt_dlp.utils.DownloadError:
        return None


def get_volume(guild_id: int) -> float:
    return guild_volume.get(guild_id, 1.0)


def make_source(stream_url: str, guild_id: int) -> discord.PCMVolumeTransformer:
    raw = discord.FFmpegPCMAudio(stream_url, before_options=FFMPEG_BEFORE_OPTS, options=FFMPEG_OPTS)
    return discord.PCMVolumeTransformer(raw, volume=get_volume(guild_id))


def after_callback_factory(guild_id: int, voice_client: discord.VoiceClient, text_channel: discord.abc.Messageable):
    def after_callback(error):
        if error:
            print(f"Player error: {error}")
        if lofi_mode.get(guild_id):
            fut = asyncio.run_coroutine_threadsafe(play_lofi(guild_id, voice_client, text_channel), bot.loop)
        else:
            fut = asyncio.run_coroutine_threadsafe(play_next(guild_id, voice_client, text_channel), bot.loop)
        try:
            fut.result()
        except Exception as e:
            print(f"Error advancing playback: {e}")
    return after_callback


async def play_next(guild_id: int, voice_client: discord.VoiceClient, text_channel: discord.abc.Messageable):
    queue = song_queues.get(guild_id, [])

    if not queue:
        now_playing[guild_id] = None
        return

    track = queue.pop(0)
    now_playing[guild_id] = track

    source = make_source(track["stream_url"], guild_id)
    voice_client.play(source, after=after_callback_factory(guild_id, voice_client, text_channel))

    try:
        await text_channel.send(f"🎶 Now playing: **{track['title']}** (requested by {track['requester']})")
    except discord.HTTPException:
        pass


async def play_lofi(guild_id: int, voice_client: discord.VoiceClient, text_channel: discord.abc.Messageable):
    """(Re)starts the 24/7 lofi stream for a guild. Called on /lofi and to loop after it ends."""
    stream_link = lofi_stream_link.get(guild_id, DEFAULT_LOFI_STREAM)
    info = await extract_track_info(stream_link)

    if not info or "url" not in info:
        lofi_mode[guild_id] = False
        try:
            await text_channel.send("⚠️ Couldn't load the lofi stream — turning lofi mode off.")
        except discord.HTTPException:
            pass
        return

    track = {
        "title": info.get("title", "Lofi Radio"),
        "stream_url": info["url"],
        "requester": "24/7 Lofi Radio",
    }
    now_playing[guild_id] = track

    source = make_source(track["stream_url"], guild_id)
    voice_client.play(source, after=after_callback_factory(guild_id, voice_client, text_channel))


# ----------------------------------------------------------------------
# MUSIC COMMANDS
# ----------------------------------------------------------------------

@bot.tree.command(name="play", description="Play a YouTube or Spotify link (or search term) in your voice channel.")
@app_commands.describe(query="A YouTube link, Spotify track link, or search text")
async def play_command(interaction: discord.Interaction, query: str):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("Join a voice channel first!", ephemeral=True)
        return

    await interaction.response.defer()

    voice_channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client

    try:
        if voice_client is None:
            voice_client = await voice_channel.connect(timeout=15, reconnect=True)
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
    except asyncio.TimeoutError:
        await interaction.followup.send(
            "⚠️ Timed out connecting to voice. This usually means the server hosting the bot "
            "is blocking the UDP traffic Discord voice needs — common on some free hosting tiers. "
            "Try again, or check your host's networking docs for UDP support."
        )
        return
    except Exception as e:
        await interaction.followup.send(f"Couldn't join your voice channel: {e}")
        return

    try:
        search_query = await resolve_search_query(query.strip())
        if not (YOUTUBE_URL_RE.search(search_query) or search_query.startswith("http")):
            search_query = f"ytsearch1:{search_query}"

        info = await extract_track_info(search_query)
    except Exception as e:
        await interaction.followup.send(f"Something went wrong looking that up: {e}")
        return

    if not info or "url" not in info:
        await interaction.followup.send("Couldn't find or play that — try a different link or search term.")
        return

    track = {
        "title": info.get("title", "Unknown title"),
        "stream_url": info["url"],
        "requester": interaction.user.display_name,
    }

    guild_id = interaction.guild_id
    song_queues.setdefault(guild_id, [])

    # An explicit /play takes priority over an ongoing 24/7 lofi loop.
    was_lofi = lofi_mode.get(guild_id, False)
    lofi_mode[guild_id] = False

    if not was_lofi and (voice_client.is_playing() or voice_client.is_paused()):
        song_queues[guild_id].append(track)
        await interaction.followup.send(f"➕ Added to queue: **{track['title']}**")
    else:
        song_queues[guild_id].append(track)
        if was_lofi:
            voice_client.stop()  # cuts the lofi stream; after-callback will now pull from the queue
            await interaction.followup.send(f"🔎 Lofi paused — now playing: **{track['title']}**")
        else:
            await interaction.followup.send(f"🔎 Found: **{track['title']}**")
            await play_next(guild_id, voice_client, interaction.channel)


@bot.tree.command(name="vskip", description="Skip the currently playing song.")
async def vskip_command(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if not voice_client or not (voice_client.is_playing() or voice_client.is_paused()):
        await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
        return

    voice_client.stop()  # triggers the 'after' callback, which advances the queue
    await interaction.response.send_message("⏭️ Skipped.")


@bot.tree.command(name="stop", description="Stop playback, clear the queue, and leave the voice channel.")
async def stop_command(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if not voice_client:
        await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)
        return

    guild_id = interaction.guild_id
    song_queues[guild_id] = []
    now_playing[guild_id] = None
    lofi_mode[guild_id] = False
    voice_client.stop()
    await voice_client.disconnect()
    await interaction.response.send_message("⏹️ Stopped and left the voice channel.")


@bot.tree.command(name="queue", description="Show what's up next.")
async def queue_command(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    current = now_playing.get(guild_id)
    upcoming = song_queues.get(guild_id, [])

    if not current and not upcoming:
        await interaction.response.send_message("Nothing playing and nothing queued.")
        return

    lines = []
    if current:
        lines.append(f"**Now Playing:** {current['title']} (requested by {current['requester']})")
    if upcoming:
        lines.append("\n**Up Next:**")
        for i, t in enumerate(upcoming[:10], start=1):
            lines.append(f"{i}. {t['title']} (requested by {t['requester']})")

    await interaction.response.send_message("\n".join(lines))


@bot.tree.command(name="nowplaying", description="Show the currently playing song.")
async def nowplaying_command(interaction: discord.Interaction):
    current = now_playing.get(interaction.guild_id)
    if not current:
        await interaction.response.send_message("Nothing is playing right now.")
        return
    await interaction.response.send_message(f"🎶 **{current['title']}** — requested by {current['requester']}")


@bot.tree.command(name="join", description="Move the bot to a specific voice channel (stops any 24/7 lofi loop).")
@app_commands.describe(channel="Voice channel to join")
async def join_command(interaction: discord.Interaction, channel: discord.VoiceChannel):
    guild_id = interaction.guild_id
    voice_client = interaction.guild.voice_client

    await interaction.response.defer()

    lofi_mode[guild_id] = False
    song_queues[guild_id] = []
    now_playing[guild_id] = None

    try:
        if voice_client is None:
            await channel.connect(timeout=15, reconnect=True)
        else:
            voice_client.stop()
            await voice_client.move_to(channel)
    except asyncio.TimeoutError:
        await interaction.followup.send(
            "⚠️ Timed out connecting to voice. This usually means the server hosting the bot "
            "is blocking the UDP traffic Discord voice needs — common on some free hosting tiers."
        )
        return
    except Exception as e:
        await interaction.followup.send(f"Couldn't join {channel.mention}: {e}")
        return

    await interaction.followup.send(f"👋 Joined {channel.mention}.")


@bot.tree.command(name="lofi", description="Play 24/7 lofi radio in a voice channel until moved elsewhere.")
@app_commands.describe(
    channel="Voice channel to play lofi in",
    link="Optional: your own YouTube livestream/link instead of the default lofi radio",
)
async def lofi_command(interaction: discord.Interaction, channel: discord.VoiceChannel, link: str = None):
    guild_id = interaction.guild_id
    voice_client = interaction.guild.voice_client

    await interaction.response.defer()

    try:
        if voice_client is None:
            voice_client = await channel.connect(timeout=15, reconnect=True)
        elif voice_client.channel != channel:
            voice_client.stop()
            await voice_client.move_to(channel)
        else:
            voice_client.stop()
    except asyncio.TimeoutError:
        await interaction.followup.send(
            "⚠️ Timed out connecting to voice. This usually means the server hosting the bot "
            "is blocking the UDP traffic Discord voice needs — common on some free hosting tiers."
        )
        return
    except Exception as e:
        await interaction.followup.send(f"Couldn't join {channel.mention}: {e}")
        return

    lofi_mode[guild_id] = True
    lofi_stream_link[guild_id] = link.strip() if link else DEFAULT_LOFI_STREAM
    song_queues[guild_id] = []

    await interaction.followup.send(
        f"🌙 Starting 24/7 lofi radio in {channel.mention}. Use `/join` to move me elsewhere, "
        f"or `/play` to interrupt with a specific song."
    )

    try:
        await play_lofi(guild_id, voice_client, interaction.channel)
    except Exception as e:
        await interaction.channel.send(f"⚠️ Couldn't start the lofi stream: {e}")


# ----------------------------------------------------------------------
# CONTROL PANEL
# ----------------------------------------------------------------------

def build_panel_embed(guild_id: int) -> discord.Embed:
    guild = bot.get_guild(guild_id)
    voice_client = guild.voice_client if guild else None
    current = now_playing.get(guild_id)
    vol_pct = int(get_volume(guild_id) * 100)
    mode = "🌙 24/7 Lofi" if lofi_mode.get(guild_id) else "🎵 Normal queue"
    queue_len = len(song_queues.get(guild_id, []))

    if current:
        state = "⏸️ Paused" if voice_client and voice_client.is_paused() else "▶️ Playing"
        description = f"{state}: **{current['title']}**\nRequested by {current['requester']}"
    else:
        description = "Nothing is playing."

    embed = discord.Embed(title="🎛️ Music Control Panel", description=description, color=discord.Color.purple())
    embed.add_field(name="Volume", value=f"{vol_pct}%", inline=True)
    embed.add_field(name="Mode", value=mode, inline=True)
    embed.add_field(name="Queue", value=f"{queue_len} waiting", inline=True)
    return embed


class MusicControlView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    async def refresh(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=build_panel_embed(self.guild_id), view=self)

    @discord.ui.button(label="Play/Pause", emoji="⏯️", style=discord.ButtonStyle.primary)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.response.send_message("Not connected to a voice channel.", ephemeral=True)
            return
        if voice_client.is_playing():
            voice_client.pause()
        elif voice_client.is_paused():
            voice_client.resume()
        else:
            await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
            return
        await self.refresh(interaction)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()
            await asyncio.sleep(0.75)  # let the after-callback update now_playing first
        await self.refresh(interaction)

    @discord.ui.button(label="Vol −", emoji="🔉", style=discord.ButtonStyle.secondary)
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_vol = max(0.0, get_volume(self.guild_id) - 0.1)
        guild_volume[self.guild_id] = new_vol
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.source:
            voice_client.source.volume = new_vol
        await self.refresh(interaction)

    @discord.ui.button(label="Vol +", emoji="🔊", style=discord.ButtonStyle.secondary)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_vol = min(2.0, get_volume(self.guild_id) + 0.1)
        guild_volume[self.guild_id] = new_vol
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.source:
            voice_client.source.volume = new_vol
        await self.refresh(interaction)

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        guild_id = self.guild_id
        song_queues[guild_id] = []
        now_playing[guild_id] = None
        lofi_mode[guild_id] = False
        if voice_client:
            voice_client.stop()
            await voice_client.disconnect()
        await self.refresh(interaction)


@bot.tree.command(name="panel", description="Show an interactive music control panel (volume, play/pause, skip, stop).")
async def panel_command(interaction: discord.Interaction):
    view = MusicControlView(interaction.guild_id)
    await interaction.response.send_message(embed=build_panel_embed(interaction.guild_id), view=view)


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
        value="Ask the bot's AI anything and get a response.",
        inline=False,
    )
    embed_en.add_field(
        name="/play",
        value="Plays a YouTube link, Spotify track link, or search term in your voice channel. Joins your VC automatically.",
        inline=False,
    )
    embed_en.add_field(
        name="/vskip",
        value="Skips the currently playing song.",
        inline=False,
    )
    embed_en.add_field(
        name="/stop",
        value="Stops playback, clears the queue, and leaves the voice channel.",
        inline=False,
    )
    embed_en.add_field(
        name="/queue",
        value="Shows the current song and what's coming up next.",
        inline=False,
    )
    embed_en.add_field(
        name="/nowplaying",
        value="Shows the currently playing song.",
        inline=False,
    )
    embed_en.add_field(
        name="/join",
        value="Moves the bot into a specific voice channel (stops any 24/7 lofi loop and clears the queue).",
        inline=False,
    )
    embed_en.add_field(
        name="/lofi",
        value="Plays 24/7 lofi radio in a chosen voice channel — keeps looping until moved with /join or interrupted with /play.",
        inline=False,
    )
    embed_en.add_field(
        name="/panel",
        value="Shows an interactive control panel with play/pause, skip, volume, and stop buttons.",
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
        value="اسأل ذكاء البوت الاصطناعي أي سؤال واحصل على إجابة.",
        inline=False,
    )
    embed_ar.add_field(
        name="/play",
        value="يشغّل رابط يوتيوب أو رابط أغنية من سبوتيفاي أو كلمة بحث في قناتك الصوتية. ينضم البوت تلقائياً.",
        inline=False,
    )
    embed_ar.add_field(
        name="/vskip",
        value="يتخطى الأغنية الحالية.",
        inline=False,
    )
    embed_ar.add_field(
        name="/stop",
        value="يوقف التشغيل، يمسح قائمة الانتظار، ويغادر القناة الصوتية.",
        inline=False,
    )
    embed_ar.add_field(
        name="/queue",
        value="يعرض الأغنية الحالية والأغاني القادمة.",
        inline=False,
    )
    embed_ar.add_field(
        name="/nowplaying",
        value="يعرض الأغنية التي تُشغَّل حالياً.",
        inline=False,
    )
    embed_ar.add_field(
        name="/join",
        value="ينقل البوت إلى قناة صوتية محددة (يوقف أي تشغيل لوفاي دائم ويمسح قائمة الانتظار).",
        inline=False,
    )
    embed_ar.add_field(
        name="/lofi",
        value="يشغّل إذاعة لوفاي على مدار الساعة في القناة الصوتية المختارة — يستمر حتى يُنقل البوت بـ /join أو يُقاطَع بـ /play.",
        inline=False,
    )
    embed_ar.add_field(
        name="/panel",
        value="يعرض لوحة تحكم تفاعلية بأزرار تشغيل/إيقاف مؤقت، تخطي، مستوى الصوت، وإيقاف.",
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


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

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
