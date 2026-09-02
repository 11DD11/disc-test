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
import base64
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

# Easter egg: mentioning this specific user posts a real voice message
# (the blue waveform bubble, not a regular audio attachment).
VOICE_MENTION_TARGET_USER_ID = 764457716110327809

# ----------------------------------------------------------------------
# AUTO-MODERATION
# ----------------------------------------------------------------------
# Automatically deletes messages containing a middle finger emoji (any skin
# tone) or certain banned phrases, then DMs the dev with details about what
# was removed. Requires the bot to have "Manage Messages" permission in the
# server — see README for setup.

MOD_ALERT_USER_ID = 764457716110327809  # same person as the voice-mention easter egg

# Matches 🖕 with or without a skin-tone modifier (U+1F3FB–U+1F3FF)
MIDDLE_FINGER_PATTERN = re.compile("\U0001F595[\U0001F3FB-\U0001F3FF]?")

# Starting list of banned phrases (case-insensitive substring match). Add more
# as needed — this isn't meant to be exhaustive, just a reasonable baseline.
BANNED_PHRASES = [
    "fuck you", "fuck u", "fuk you", "fck you", "f u c k you",
]
# Matches only an explicit typed @mention (e.g. <@764...> or <@!764...>).
# Deliberately does NOT use message.mentions, since Discord also populates
# that list when someone replies with the ping toggle on, even without an
# actual @mention in the text — this keeps the trigger to direct mentions only.
VOICE_MENTION_PATTERN = re.compile(rf"<@!?{VOICE_MENTION_TARGET_USER_ID}>")
VOICE_CLIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "dev_voice_clip.ogg")
VOICE_CLIP_DURATION_SECS = 2.491042
VOICE_CLIP_WAVEFORM_B64 = "AAAAAgUHCQsTCgoLDxolRFGLxbTCwb7CwaWzpKKenKynnaKgnqeco56jnZ1/YkMOCAoHBgUGBlaNipqpt7azrraYlJmYlJuZi42KhIaHf3+GfYB+fn92dn2BgouQhYGmj5CRqpCmpKGepJ+SjXtBLCAeHB8dHyAhJSAgIB8fHiIiIBZVY5ORlZ+enaKYjH9uZGBiYDQsHRAMCw0NDQ8RHSMrMDAvLi4wLy05NS0pLzQtLjAuLCkwKicmHyQlHx0eIB8bGxwXGxcZFRQTFBUTExITERARDxAQFA8NDQwNDA4LCAsLCAkKCQcIBgkJBgcJCAgGBQYEBwgIBwYEBwoHBA=="

# Easter egg: explicitly @mentioning the bot itself posts a different voice clip.
BOT_MENTION_VOICE_CLIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "bot_mention_voice_clip.ogg")
BOT_MENTION_VOICE_CLIP_DURATION_SECS = 7.190188
BOT_MENTION_VOICE_CLIP_WAVEFORM_B64 = "AAAFGhYaGBYrLCEhHxASFA4PDQwhLBsdGB1EbnM2MFJkYko4RWxjWjIVIWuLhYhuZ0Vja2ZgeHxsdWNea1xUTD87OTo0Ih8eFxgXEA0nJUJbX19hW1U5JVNOSk5QUVZWWlVVUFtVYF5NUUwmMxcMEiwhFxITFzuYhH94kWh9dW9Rcn94eHZ8bHWMZ29cdWdgZkg0LRwMCwooFyYqOFBshGxbamlbcXFxb3tkYV9eWVZeR0RFPUA0KCIWDxsVGBQWKjAsX01iXmFnX11fb3JxcHxfWl5lTUZVSEM4NClAKCYYHxgaFxAVITZcZnNpXV57bGhsYGmJWGVjUl5SXktHAg=="

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
PRESENCE_STATUS_TEXT = "Hollow Knight: Silksong"
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
DINO_SEARCH_TERMS = ["dinosaur", "dinosaurs fighting", "t-rex", "dinosaur battle"]
FRIES_SEARCH_TERMS = ["french fries", "fries gif", "fries", "potato", "french fries funny"]

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


# ----------------------------------------------------------------------
# CURRENCY
# ----------------------------------------------------------------------
# Reuses the same scores.json entries, just with an added "coins" field.

STARTING_BALANCE = 100


def get_balance(user_id: int) -> int:
    entry = scores.setdefault(str(user_id), {"wins": 0, "streak": 0, "best_streak": 0})
    if "coins" not in entry:
        entry["coins"] = STARTING_BALANCE
        save_scores(scores)
    return entry["coins"]


def add_balance(user_id: int, amount: int) -> int:
    """Adds (or subtracts, if negative) coins and returns the new balance."""
    get_balance(user_id)  # ensures the entry + starting balance exist first
    entry = scores[str(user_id)]
    entry["coins"] = max(0, entry["coins"] + amount)
    save_scores(scores)
    return entry["coins"]


def format_coins(amount: int) -> str:
    return f"🪙 {amount:,}"


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
        from PIL import features as _pil_features
        has_raqm = _pil_features.check("raqm")
        print(f"Pillow raqm text-shaping engine available: {has_raqm}")
        if not has_raqm:
            print(
                "WARNING: raqm is unavailable, so /npc's Arabic text will render without "
                "proper letter-joining or right-to-left ordering. This usually means libfribidi "
                "isn't installed on this host — check that nixpacks.toml is present in the repo "
                "and that Railway's build log shows it installing libfribidi0."
            )
    except Exception as e:
        print(f"Could not check Pillow raqm support: {e}")

    try:
        app_id = bot.application_id or (await bot.application_info()).id
        activity = discord.Activity(
            type=discord.ActivityType.playing,
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


class LeaderboardView(discord.ui.LayoutView):
    def __init__(self, ranked: list, member_lookup: dict):
        super().__init__(timeout=None)
        medals = ["🥇", "🥈", "🥉"]

        items = [discord.ui.TextDisplay(content="# 🏆 Flag Leaderboard")]
        items.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        for i, (uid, data) in enumerate(ranked):
            member = member_lookup.get(uid)
            if member:
                name = member.display_name
                if member.name.lower() == DEV_USERNAME:
                    name += " (the dev)"
                avatar_url = member.display_avatar.url
            else:
                name = f"User {uid}"
                avatar_url = None

            prefix = medals[i] if i < 3 else f"**{i + 1}.**"
            text = f"{prefix} **{name}**\n{data['wins']} win(s) · best streak {data.get('best_streak', 0)}"

            if avatar_url:
                section = discord.ui.Section(
                    discord.ui.TextDisplay(content=text),
                    accessory=discord.ui.Thumbnail(url=avatar_url),
                )
            else:
                section = discord.ui.Section(discord.ui.TextDisplay(content=text))

            items.append(section)
            if i < len(ranked) - 1:
                items.append(discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small))

        container = discord.ui.Container(*items, accent_color=discord.Color.gold())
        self.add_item(container)


@bot.tree.command(name="leaderboard", description="Show the top flag-guessers.")
async def leaderboard_command(interaction: discord.Interaction):
    if not scores:
        await interaction.response.send_message("No one has scored yet — start a round with `/flag`!")
        return

    ranked = sorted(scores.items(), key=lambda kv: kv[1]["wins"], reverse=True)[:10]

    member_lookup = {}
    if interaction.guild:
        for uid, _ in ranked:
            member = interaction.guild.get_member(int(uid))
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(int(uid))
                except discord.HTTPException:
                    member = None
            if member:
                member_lookup[uid] = member

    await interaction.response.send_message(view=LeaderboardView(ranked, member_lookup))


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


class ProfileView(discord.ui.LayoutView):
    def __init__(self, target: discord.Member, entry: dict, is_dev: bool, balance: int):
        super().__init__(timeout=None)

        name_line = f"# 📊 {target.display_name}'s Profile"
        if is_dev:
            name_line += " *(the dev)*"

        stats_text = (
            f"**Total Wins:** {entry.get('wins', 0)}\n"
            f"**Current Streak:** {entry.get('streak', 0)} 🔥\n"
            f"**Best Streak:** {entry.get('best_streak', 0)}\n"
            f"**Balance:** {format_coins(balance)}"
        )

        section = discord.ui.Section(
            discord.ui.TextDisplay(content=name_line),
            discord.ui.TextDisplay(content=stats_text),
            accessory=discord.ui.Thumbnail(url=target.display_avatar.url),
        )

        container = discord.ui.Container(section, accent_color=discord.Color.blue())
        self.add_item(container)


@bot.tree.command(name="profile", description="Show a player's flag-game stats.")
@app_commands.describe(user="Whose profile to check (optional)")
async def profile_command(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    entry = scores.get(str(target.id), {"wins": 0, "streak": 0, "best_streak": 0})
    is_dev = target.name.lower() == DEV_USERNAME
    balance = get_balance(target.id)

    await interaction.response.send_message(view=ProfileView(target, entry, is_dev, balance))


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


@bot.tree.command(name="dino", description="Get a random dinosaur gif (sometimes two of them fighting)!")
async def dino_command(interaction: discord.Interaction):
    if not GIPHY_API_KEY:
        await interaction.response.send_message(
            "The bot owner hasn't set up a Giphy API key yet, so `/dino` isn't available. "
            "(Free key at developers.giphy.com — add it as the GIPHY_API_KEY variable.)",
            ephemeral=True,
        )
        return

    await interaction.response.defer()

    query = random.choice(DINO_SEARCH_TERMS)
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
        await interaction.followup.send("Couldn't find a dinosaur gif right now, try again!")
        return

    choice = random.choice(results)
    gif_url = choice.get("images", {}).get("original", {}).get("url")

    if not gif_url:
        await interaction.followup.send("Couldn't find a dinosaur gif right now, try again!")
        return

    await interaction.followup.send(gif_url)


@bot.tree.command(name="fries", description="Get a random fries (or potato) gif!")
async def fries_command(interaction: discord.Interaction):
    if not GIPHY_API_KEY:
        await interaction.response.send_message(
            "The bot owner hasn't set up a Giphy API key yet, so `/fries` isn't available. "
            "(Free key at developers.giphy.com — add it as the GIPHY_API_KEY variable.)",
            ephemeral=True,
        )
        return

    await interaction.response.defer()

    query = random.choice(FRIES_SEARCH_TERMS)
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
        await interaction.followup.send("Couldn't find a fries gif right now, try again!")
        return

    choice = random.choice(results)
    gif_url = choice.get("images", {}).get("original", {}).get("url")

    if not gif_url:
        await interaction.followup.send("Couldn't find a fries gif right now, try again!")
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
#
# The board itself is rendered as an actual PNG image (not emoji/text) —
# emoji-based boards run into two real problems: adjacent flag-letter emoji
# combine into unrelated country flags, and rows wrap unpredictably on
# narrow (mobile) screens since they aren't in a monospace context. An
# image sidesteps both entirely and looks like an actual chessboard.

import io
import math
import chess as chesslib
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CHESS_SQUARE_PX = 80
CHESS_MARGIN_PX = 30
CHESS_LIGHT_COLOR = (240, 190, 120)   # tan
CHESS_DARK_COLOR = (140, 90, 50)      # brown
CHESS_BG_COLOR = (30, 20, 15)
CHESS_LABEL_COLOR = (255, 255, 255)
CHESS_WHITE_PIECE_FILL = (255, 255, 255)
CHESS_WHITE_PIECE_OUTLINE = (0, 0, 0)
CHESS_BLACK_PIECE_FILL = (20, 20, 20)
CHESS_BLACK_PIECE_OUTLINE = (255, 255, 255)

# Bundled font so rendering works on any host without relying on system fonts
# being installed. DejaVu Sans supports the Unicode chess piece glyphs.
_CHESS_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "DejaVuSans.ttf")
try:
    CHESS_PIECE_FONT = ImageFont.truetype(_CHESS_FONT_PATH, 56)
    CHESS_LABEL_FONT = ImageFont.truetype(_CHESS_FONT_PATH, 20)
except OSError:
    print(f"Warning: chess font not found at {_CHESS_FONT_PATH}, falling back to default font.")
    CHESS_PIECE_FONT = ImageFont.load_default()
    CHESS_LABEL_FONT = ImageFont.load_default()

CHESS_PIECE_SYMBOLS = {
    (chesslib.PAWN, True): "♙", (chesslib.PAWN, False): "♟",
    (chesslib.KNIGHT, True): "♘", (chesslib.KNIGHT, False): "♞",
    (chesslib.BISHOP, True): "♗", (chesslib.BISHOP, False): "♝",
    (chesslib.ROOK, True): "♖", (chesslib.ROOK, False): "♜",
    (chesslib.QUEEN, True): "♕", (chesslib.QUEEN, False): "♛",
    (chesslib.KING, True): "♔", (chesslib.KING, False): "♚",
}


def render_chess_board_image(board: chesslib.Board) -> io.BytesIO:
    """Renders the board as a PNG image and returns it as an in-memory buffer."""
    board_px = CHESS_SQUARE_PX * 8
    img_size = board_px + CHESS_MARGIN_PX * 2
    img = Image.new("RGB", (img_size, img_size), CHESS_BG_COLOR)
    draw = ImageDraw.Draw(img)

    for rank in range(8):
        for file in range(8):
            is_light = (rank + file) % 2 == 1
            color = CHESS_LIGHT_COLOR if is_light else CHESS_DARK_COLOR
            x0 = CHESS_MARGIN_PX + file * CHESS_SQUARE_PX
            y0 = CHESS_MARGIN_PX + (7 - rank) * CHESS_SQUARE_PX
            draw.rectangle([x0, y0, x0 + CHESS_SQUARE_PX, y0 + CHESS_SQUARE_PX], fill=color)

            piece = board.piece_at(chesslib.square(file, rank))
            if piece:
                symbol = CHESS_PIECE_SYMBOLS[(piece.piece_type, piece.color)]
                fill = CHESS_WHITE_PIECE_FILL if piece.color else CHESS_BLACK_PIECE_FILL
                outline = CHESS_WHITE_PIECE_OUTLINE if piece.color else CHESS_BLACK_PIECE_OUTLINE
                cx, cy = x0 + CHESS_SQUARE_PX // 2, y0 + CHESS_SQUARE_PX // 2
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    draw.text((cx + dx, cy + dy), symbol, font=CHESS_PIECE_FONT, fill=outline, anchor="mm")
                draw.text((cx, cy), symbol, font=CHESS_PIECE_FONT, fill=fill, anchor="mm")

    files = "abcdefgh"
    for file in range(8):
        x = CHESS_MARGIN_PX + file * CHESS_SQUARE_PX + CHESS_SQUARE_PX // 2
        draw.text((x, CHESS_MARGIN_PX // 2), files[file], font=CHESS_LABEL_FONT, fill=CHESS_LABEL_COLOR, anchor="mm")
        draw.text((x, img_size - CHESS_MARGIN_PX // 2), files[file], font=CHESS_LABEL_FONT, fill=CHESS_LABEL_COLOR, anchor="mm")
    for rank in range(8):
        y = CHESS_MARGIN_PX + (7 - rank) * CHESS_SQUARE_PX + CHESS_SQUARE_PX // 2
        draw.text((CHESS_MARGIN_PX // 2, y), str(rank + 1), font=CHESS_LABEL_FONT, fill=CHESS_LABEL_COLOR, anchor="mm")
        draw.text((img_size - CHESS_MARGIN_PX // 2, y), str(rank + 1), font=CHESS_LABEL_FONT, fill=CHESS_LABEL_COLOR, anchor="mm")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


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

    def status_line(self) -> str:
        turn_name = "White" if self.board.turn == chesslib.WHITE else "Black"
        check_note = " — Check!" if self.board.is_check() else ""
        return f"**{turn_name}'s turn** ({self.current_player.mention}){check_note}"

    def header(self) -> str:
        return f"♟️ {self.white.mention} (White) vs {self.black.mention} (Black)"

    def board_file(self) -> discord.File:
        buffer = render_chess_board_image(self.board)
        return discord.File(fp=buffer, filename="board.png")

    async def refresh_message(self, interaction: discord.Interaction):
        content = f"{self.header()}\n{self.status_line()}"
        await interaction.response.edit_message(content=content, attachments=[self.board_file()], view=self)

    async def end_game(self, interaction: discord.Interaction, result_text: str):
        for child in self.children:
            child.disabled = True
        content = f"{self.header()}\n{result_text}"
        await interaction.response.edit_message(content=content, attachments=[self.board_file()], view=self)
        chess_games.pop(self.channel_id, None)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                content = f"{self.header()}\n⏱️ Game timed out from inactivity."
                await self.message.edit(content=content, attachments=[self.board_file()], view=self)
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

    content = f"{game.header()}\n{game.status_line()}"
    await interaction.response.send_message(content=content, file=game.board_file(), view=game)
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


# ----------------------------------------------------------------------
# GAMBLING
# ----------------------------------------------------------------------
# Games are rendered as actual images (not plain text/emoji) using a
# consistent "casino" visual style — dark felt background, gold trim,
# hand-drawn icons. Full-color emoji (🍒🍋💎 etc.) can't be rendered through
# a regular font, so each symbol is drawn from scratch with PIL primitives.

CASINO_BG_COLOR = (10, 51, 33)
CASINO_BORDER_COLOR = (212, 175, 55)
CASINO_PANEL_BG = (250, 248, 240)
CASINO_WIN_COLOR = (255, 215, 60)
CASINO_LOSE_COLOR = (230, 90, 90)
CASINO_PUSH_COLOR = (200, 200, 200)
CASINO_SUPERSAMPLE = 3  # render at 3x then downscale for anti-aliased edges/text

_CASINO_FONT_BOLD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "DejaVuSans-Bold.ttf")
_CASINO_FONT_REGULAR_PATH = _CHESS_FONT_PATH  # same bundled font already used for chess
_casino_font_warned = False
_font_cmap_cache = {}


def _get_font_cmap(path: str) -> set:
    """Returns the set of Unicode codepoints a font file can actually render,
    used to strip glyphs the font doesn't support (e.g. decorative symbols in
    Discord nicknames) instead of letting them show up as empty "tofu" boxes."""
    if path not in _font_cmap_cache:
        try:
            from fontTools.ttLib import TTFont
            tt = TTFont(path)
            _font_cmap_cache[path] = set(tt.getBestCmap().keys())
        except Exception as e:
            print(f"Could not read font cmap for {path}: {e}")
            _font_cmap_cache[path] = None  # None = "couldn't check, allow everything"
    return _font_cmap_cache[path]


def sanitize_for_font(text: str, bold: bool = True) -> str:
    """Strips characters the bundled font can't render, preventing empty
    'tofu' box glyphs (common with decorative Discord nicknames using
    symbols like ꧁꧂). Falls back to returning the text unchanged if the
    font's coverage can't be determined."""
    path = _CASINO_FONT_BOLD_PATH if bold else _CASINO_FONT_REGULAR_PATH
    cmap = _get_font_cmap(path)
    if cmap is None:
        return text
    return "".join(c for c in text if ord(c) in cmap or c.isspace())


def _casino_font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    """Loads the bold or regular casino font at the given size. If the bold
    font file is missing, falls back to the regular font at the same large
    size (still readable) rather than PIL's tiny fixed-size default font,
    which is what caused illegible/invisible text in earlier versions."""
    global _casino_font_warned
    path = _CASINO_FONT_BOLD_PATH if bold else _CASINO_FONT_REGULAR_PATH
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        if bold:
            if not _casino_font_warned:
                print(
                    f"WARNING: {_CASINO_FONT_BOLD_PATH} not found — gambling images will use the "
                    f"regular font instead of bold. Upload DejaVuSans-Bold.ttf to your assets folder to fix this."
                )
                _casino_font_warned = True
            try:
                return ImageFont.truetype(_CASINO_FONT_REGULAR_PATH, size)
            except OSError:
                pass
        print(f"WARNING: font file not found at all ({path}) — falling back to a tiny placeholder font.")
        return ImageFont.load_default()


def _radial_gradient(size, inner_color, outer_color) -> Image.Image:
    """Cheap radial gradient: compute at low-res then upscale with smoothing."""
    w, h = size
    small_w, small_h = max(1, w // 8), max(1, h // 8)
    small = Image.new("RGB", (small_w, small_h))
    px = small.load()
    max_r = math.hypot(small_w / 2, small_h / 2)
    for y in range(small_h):
        for x in range(small_w):
            dist = min(1.0, math.hypot(x - small_w / 2, y - small_h / 2) / max_r)
            px[x, y] = tuple(int(inner_color[i] + (outer_color[i] - inner_color[i]) * dist) for i in range(3))
    return small.resize((w, h), Image.BILINEAR)


def _drop_shadow(base_img: Image.Image, box, radius, blur=8, offset=(0, 4), opacity=120):
    """Pastes a soft blurred shadow of a rounded-rect shape onto base_img in place."""
    shadow = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    x0, y0, x1, y1 = box
    sdraw.rounded_rectangle(
        [x0 + offset[0], y0 + offset[1], x1 + offset[0], y1 + offset[1]],
        radius=radius, fill=(0, 0, 0, opacity),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    composited = Image.alpha_composite(base_img.convert("RGBA"), shadow).convert("RGB")
    base_img.paste(composited, (0, 0))


def _casino_frame(width: int, height: int, title: str) -> tuple:
    """Creates the shared supersampled canvas + gold double-border + title used
    by all three gambling images. Returns (ss_image, draw, ss_factor)."""
    ss = CASINO_SUPERSAMPLE
    ss_img = Image.new("RGB", (width * ss, height * ss))
    ss_img.paste(_radial_gradient((width * ss, height * ss), (18, 75, 48), (6, 30, 20)), (0, 0))
    draw = ImageDraw.Draw(ss_img)

    draw.rounded_rectangle(
        [8 * ss, 8 * ss, (width - 8) * ss, (height - 8) * ss],
        radius=26 * ss, outline=CASINO_BORDER_COLOR, width=7 * ss,
    )
    draw.rounded_rectangle(
        [16 * ss, 16 * ss, (width - 16) * ss, (height - 16) * ss],
        radius=20 * ss, outline=(150, 120, 40), width=2 * ss,
    )

    title_size = 34 if len(title) > 8 else 42
    f_title = _casino_font(True, title_size * ss)
    title_y = 45 * ss if len(title) > 8 else 50 * ss
    # subtle drop-shadow text (offset lighter copy behind) for a glossy engraved look
    draw.text((width * ss / 2, title_y + 4 * ss), title, font=f_title, fill=(255, 225, 110), anchor="mm")
    draw.text((width * ss / 2, title_y), title, font=f_title, fill=CASINO_BORDER_COLOR, anchor="mm")

    return ss_img, draw, ss


def _casino_banner(ss_img: Image.Image, draw: ImageDraw.ImageDraw, cy: int, text: str, color, font_size: int = 30):
    font = _casino_font(True, font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    pad = 22
    draw.rounded_rectangle([ss_img.width/2 - w/2 - pad, cy-30, ss_img.width/2 + w/2 + pad, cy+30], radius=16, fill=(0, 0, 0))
    draw.rounded_rectangle([ss_img.width/2 - w/2 - pad, cy-30, ss_img.width/2 + w/2 + pad, cy+30], radius=16, outline=color, width=2)
    draw.text((ss_img.width/2, cy), text, font=font, fill=color, anchor="mm")


# --- hand-drawn icons with gloss highlights (each takes draw, center x/y, radius) ---

def _icon_cherry(draw, cx, cy, r):
    off = r * 0.35
    for dx in (-off, off):
        draw.ellipse([cx+dx-r*0.55, cy+off-r*0.4, cx+dx+r*0.55, cy+off+r*0.75], fill=(200,20,40), outline=(110,0,15), width=3)
        draw.ellipse([cx+dx-r*0.28, cy+off-r*0.22, cx+dx-r*0.05, cy+off+r*0.05], fill=(255,140,150))
    draw.line([cx-off, cy+off-r*0.3, cx, cy-r*0.9], fill=(60,120,40), width=5)
    draw.line([cx+off, cy+off-r*0.3, cx, cy-r*0.9], fill=(60,120,40), width=5)
    draw.ellipse([cx-r*0.32, cy-r*1.15, cx+r*0.38, cy-r*0.72], fill=(70,165,70), outline=(30,90,30), width=2)


def _icon_lemon(draw, cx, cy, r):
    draw.ellipse([cx-r*0.8, cy-r*0.6, cx+r*0.8, cy+r*0.6], fill=(245,210,40), outline=(175,145,10), width=3)
    draw.ellipse([cx-r*0.95, cy-r*0.12, cx-r*0.65, cy+r*0.12], fill=(245,210,40), outline=(175,145,10), width=2)
    draw.ellipse([cx+r*0.65, cy-r*0.12, cx+r*0.95, cy+r*0.12], fill=(245,210,40), outline=(175,145,10), width=2)
    draw.ellipse([cx-r*0.4, cy-r*0.35, cx, cy-r*0.05], fill=(255,240,150))


def _icon_grape(draw, cx, cy, r):
    positions = [(-0.4,-0.5),(0.4,-0.5),(0,-0.1),(-0.7,0.2),(0.7,0.2),(-0.35,0.55),(0.35,0.55),(0,0.9)]
    for dx, dy in positions:
        x, y = cx + dx*r*0.9, cy + dy*r*0.9
        draw.ellipse([x-r*0.32, y-r*0.32, x+r*0.32, y+r*0.32], fill=(125,45,155), outline=(65,15,95), width=2)
        draw.ellipse([x-r*0.14, y-r*0.18, x-r*0.02, y-r*0.06], fill=(190,130,210))
    draw.line([cx, cy-r*1.1, cx, cy-r*0.6], fill=(60,120,40), width=3)


def _icon_diamond(draw, cx, cy, r):
    pts = [(cx, cy-r), (cx+r*0.75, cy-r*0.15), (cx, cy+r), (cx-r*0.75, cy-r*0.15)]
    draw.polygon(pts, fill=(70,210,230), outline=(15,130,150), width=2)
    draw.polygon([(cx,cy-r),(cx+r*0.75,cy-r*0.15),(cx,cy-r*0.15)], fill=(170,240,250))
    draw.line([cx, cy-r, cx, cy+r], fill=(255,255,255), width=2)
    draw.line([cx-r*0.75, cy-r*0.15, cx+r*0.75, cy-r*0.15], fill=(255,255,255), width=2)


def _icon_seven(draw, cx, cy, r):
    font = _casino_font(True, int(r*2.2))
    for dx, dy in [(-2,-2),(-2,2),(2,-2),(2,2)]:
        draw.text((cx+dx, cy+dy), "7", font=font, fill=(110,0,0), anchor="mm")
    draw.text((cx, cy), "7", font=font, fill=(235,40,40), anchor="mm")
    draw.text((cx-r*0.15, cy-r*0.25), "7", font=font, fill=(255,140,140), anchor="mm")


def _icon_clover(draw, cx, cy, r):
    off = r*0.42
    for dx, dy in [(-off,-off),(off,-off),(-off,off),(off,off)]:
        draw.ellipse([cx+dx-r*0.45, cy+dy-r*0.45, cx+dx+r*0.45, cy+dy+r*0.45], fill=(55,165,75), outline=(20,100,40), width=2)
        draw.ellipse([cx+dx-r*0.2, cy+dy-r*0.28, cx+dx, cy+dy-r*0.1], fill=(140,220,140))
    draw.line([cx, cy+r*0.3, cx, cy+r*1.15], fill=(40,110,40), width=4)


def _icon_star(draw, cx, cy, r):
    pts = []
    for i in range(10):
        angle = math.pi/2 + i*math.pi/5
        rad = r if i % 2 == 0 else r*0.42
        pts.append((cx + rad*math.cos(angle), cy - rad*math.sin(angle)))
    draw.polygon(pts, fill=(252,205,50), outline=(180,130,10), width=2)
    draw.ellipse([cx-r*0.15, cy-r*0.4, cx+r*0.1, cy-r*0.15], fill=(255,240,180))


def _icon_moneybag(draw, cx, cy, r):
    draw.ellipse([cx-r*0.85, cy-r*0.2, cx+r*0.85, cy+r*0.95], fill=(155,115,65), outline=(90,60,25), width=3)
    draw.ellipse([cx-r*0.6, cy-r*0.05, cx-r*0.1, cy+r*0.35], fill=(180,140,85))
    draw.polygon([(cx-r*0.4, cy-r*0.15),(cx+r*0.4, cy-r*0.15),(cx+r*0.15,cy-r*0.7),(cx-r*0.15,cy-r*0.7)], fill=(155,115,65), outline=(90,60,25))
    draw.line([cx-r*0.15, cy-r*0.68, cx-r*0.35, cy-r*0.95], fill=(90,60,25), width=4)
    draw.line([cx+r*0.15, cy-r*0.68, cx+r*0.35, cy-r*0.95], fill=(90,60,25), width=4)
    font = _casino_font(True, int(r*0.7))
    draw.text((cx, cy+r*0.35), "$", font=font, fill=(255,235,160), anchor="mm")


def _icon_crown(draw, cx, cy, r):
    base_y = cy + r*0.5
    pts = [
        (cx-r*0.9, base_y), (cx-r*0.9, cy),
        (cx-r*0.45, cy+r*0.3), (cx, cy-r*0.9),
        (cx+r*0.45, cy+r*0.3), (cx+r*0.9, cy),
        (cx+r*0.9, base_y),
    ]
    draw.polygon(pts, fill=(252,213,65), outline=(180,140,10), width=3)
    draw.polygon([(cx-r*0.8,base_y-r*0.15),(cx+r*0.8,base_y-r*0.15),(cx+r*0.8,cy+r*0.15),(cx-r*0.8,cy+r*0.15)], fill=(255,235,150))


CASINO_ICON_DRAWERS = {
    "cherry": _icon_cherry, "lemon": _icon_lemon, "grape": _icon_grape,
    "diamond": _icon_diamond, "seven": _icon_seven,
    "clover": _icon_clover, "star": _icon_star, "moneybag": _icon_moneybag, "crown": _icon_crown,
}

# (symbol_key, weight, payout_multiplier) — higher weight = more common.
SLOT_SYMBOLS = [
    ("cherry", 30, 2),
    ("lemon", 25, 3),
    ("grape", 20, 4),
    ("diamond", 10, 10),
    ("seven", 5, 25),
]

SCRATCH_COST = 50
# (symbol_key, weight, payout_multiplier_of_cost) — 0 payout = a "miss" symbol.
# Tuned to roughly 50% RTP (return-to-player) — see simulation notes in README.
SCRATCH_SYMBOLS = [
    ("clover", 60, 0),
    ("star", 22, 1),
    ("moneybag", 12, 2),
    ("diamond", 5, 4),
    ("crown", 1, 10),
]


def weighted_choice(options: list):
    """options: list of (value, weight, ...) tuples. Returns one full tuple."""
    total = sum(o[1] for o in options)
    r = random.uniform(0, total)
    upto = 0
    for option in options:
        upto += option[1]
        if r <= upto:
            return option
    return options[-1]


def render_slots_image(symbols: list, bet: int, payout: int, outcome: str) -> discord.File:
    W, H = 500, 420
    ss_img, draw, ss = _casino_frame(W, H, "SLOTS")

    body_top, body_bottom = 92 * ss, 262 * ss
    _drop_shadow(ss_img, [42*ss, body_top, (W-42)*ss, body_bottom], radius=20*ss, blur=10*ss, offset=(0, 6*ss))
    draw.rounded_rectangle([40*ss, body_top, (W-40)*ss, body_bottom], radius=18*ss, fill=(35, 22, 13), outline=CASINO_BORDER_COLOR, width=4*ss)

    reel_w = (W - 120) / 3
    for i, sym in enumerate(symbols):
        x0 = (60 + i * (reel_w + 10)) * ss
        x1 = x0 + reel_w * ss
        y0, y1 = (body_top/ss + 20) * ss, (body_bottom/ss - 20) * ss
        _drop_shadow(ss_img, [x0, y0, x1, y1], radius=10*ss, blur=6*ss, offset=(0, 3*ss))
        draw.rounded_rectangle([x0, y0, x1, y1], radius=10*ss, fill=CASINO_PANEL_BG, outline=(90, 60, 30), width=3*ss)
        cx, cy = (x0+x1)/2, (y0+y1)/2
        CASINO_ICON_DRAWERS[sym](draw, cx, cy, reel_w * ss * 0.32)

    draw.text((W*ss/2, 290*ss), f"Bet: {bet} coins", font=_casino_font(False, 20*ss), fill=(225, 225, 225), anchor="mm")

    if outcome == "jackpot":
        _casino_banner(ss_img, draw, 340*ss, f"JACKPOT! +{payout}", CASINO_WIN_COLOR, 32*ss)
    elif outcome == "push":
        _casino_banner(ss_img, draw, 340*ss, "Two matched — refunded", CASINO_PUSH_COLOR, 24*ss)
    else:
        _casino_banner(ss_img, draw, 340*ss, f"No match — lost {bet}", CASINO_LOSE_COLOR, 26*ss)

    final = ss_img.resize((W, H), Image.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(fp=buffer, filename="slots.png")


def render_scratch_card_image(symbols: list, revealed: bool, cost: int, payout: int = None, winning_symbol: str = None) -> discord.File:
    W, H = 420, 500
    ss_img, draw, ss = _casino_frame(W, H, "SCRATCH CARD")

    grid_top, cell, gap = 80, 100, 12
    grid_w = cell*3 + gap*2
    start_x = (W - grid_w) / 2

    for i in range(9):
        row, col = divmod(i, 3)
        x0 = (start_x + col*(cell+gap)) * ss
        y0 = (grid_top + row*(cell+gap)) * ss
        x1, y1 = x0 + cell*ss, y0 + cell*ss

        _drop_shadow(ss_img, [x0, y0, x1, y1], radius=10*ss, blur=5*ss, offset=(0, 3*ss))

        if revealed:
            is_winning_cell = winning_symbol and symbols[i] == winning_symbol
            border_color = CASINO_WIN_COLOR if is_winning_cell else (90, 60, 30)
            border_width = 5 if is_winning_cell else 3
            draw.rounded_rectangle([x0, y0, x1, y1], radius=10*ss, fill=CASINO_PANEL_BG, outline=border_color, width=border_width*ss)
            CASINO_ICON_DRAWERS[symbols[i]](draw, (x0+x1)/2, (y0+y1)/2, cell*ss*0.34)
        else:
            # Foil cell with a gradient sheen + diagonal hatch, drawn on its own
            # canvas (with a rounded-corner mask) then pasted — keeps effects
            # clipped to the cell instead of bleeding across the image.
            cell_size = int(cell * ss)
            cell_img = Image.new("RGB", (cell_size, cell_size), (0, 0, 0))
            cell_img.paste(_radial_gradient((cell_size, cell_size), (200, 200, 210), (140, 140, 155)), (0, 0))
            cdraw = ImageDraw.Draw(cell_img)
            for k in range(-cell_size, cell_size, 9*ss):
                cdraw.line([k, cell_size, k+cell_size, 0], fill=(170, 170, 185), width=3*ss)
            cdraw.rounded_rectangle([0, 0, cell_size-1, cell_size-1], radius=10*ss, outline=(90, 60, 30), width=3*ss)
            cdraw.text((cell_size/2, cell_size/2), "?", font=_casino_font(True, int(cell_size*0.36)), fill=(210, 210, 220), anchor="mm")

            mask = Image.new("L", (cell_size, cell_size), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, cell_size-1, cell_size-1], radius=10*ss, fill=255)
            ss_img.paste(cell_img, (int(x0), int(y0)), mask)

    draw.text((W*ss/2, (grid_top + 3*(cell+gap) + 15)*ss), f"Cost: {cost} coins", font=_casino_font(False, 18*ss), fill=(225, 225, 225), anchor="mm")

    if revealed:
        if payout:
            _casino_banner(ss_img, draw, (H-70)*ss, f"WINNER! +{payout}", CASINO_WIN_COLOR, 28*ss)
        else:
            _casino_banner(ss_img, draw, (H-70)*ss, "No matches this time", CASINO_LOSE_COLOR, 24*ss)
    else:
        _casino_banner(ss_img, draw, (H-70)*ss, "Click Scratch to reveal!", CASINO_PUSH_COLOR, 22*ss)

    final = ss_img.resize((W, H), Image.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(fp=buffer, filename="scratch.png")


def render_coinflip_image(result_side: str, win: bool, bet: int, payout: int) -> discord.File:
    W, H = 400, 400
    ss_img, draw, ss = _casino_frame(W, H, "COINFLIP")

    cx, cy, r = W*ss/2, 190*ss, 110*ss
    _drop_shadow(ss_img, [cx-r, cy-r, cx+r, cy+r], radius=int(r), blur=8*ss, offset=(0, 5*ss))

    coin_size = int(r * 2)
    coin_grad = _radial_gradient((coin_size, coin_size), (250, 215, 110), (190, 140, 40))
    mask = Image.new("L", (coin_size, coin_size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, coin_size-1, coin_size-1], fill=255)
    ss_img.paste(coin_grad, (int(cx-r), int(cy-r)), mask)

    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(150, 110, 20), width=6*ss)
    draw.ellipse([cx-r+14*ss, cy-r+14*ss, cx+r-14*ss, cy+r-14*ss], outline=(180, 140, 40), width=3*ss)

    letter = "H" if result_side == "heads" else "T"
    f_coin = _casino_font(True, 90*ss)
    draw.text((cx+3*ss, cy+3*ss), letter, font=f_coin, fill=(140, 100, 20), anchor="mm")
    draw.text((cx, cy), letter, font=f_coin, fill=(90, 60, 10), anchor="mm")

    draw.text((W*ss/2, 320*ss), f"Result: {result_side.title()}  |  Bet: {bet}", font=_casino_font(False, 18*ss), fill=(225, 225, 225), anchor="mm")

    if win:
        _casino_banner(ss_img, draw, 360*ss, f"YOU WON +{payout}", CASINO_WIN_COLOR, 26*ss)
    else:
        _casino_banner(ss_img, draw, 360*ss, f"You lost {bet}", CASINO_LOSE_COLOR, 26*ss)

    final = ss_img.resize((W, H), Image.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(fp=buffer, filename="coinflip.png")


class GamblingHubView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your gambling menu — run `/gambling` yourself!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Slots", emoji="🎰", style=discord.ButtonStyle.primary)
    async def slots_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SlotsBetModal(self.user_id))

    @discord.ui.button(label="Coinflip", emoji="🪙", style=discord.ButtonStyle.primary)
    async def coinflip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CoinflipModal(self.user_id))

    @discord.ui.button(label="Scratch Card", emoji="🎫", style=discord.ButtonStyle.primary)
    async def scratch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        balance = get_balance(self.user_id)
        if balance < SCRATCH_COST:
            await interaction.response.send_message(
                f"You need {format_coins(SCRATCH_COST)} to buy a scratch card — you have {format_coins(balance)}.",
                ephemeral=True,
            )
            return
        add_balance(self.user_id, -SCRATCH_COST)

        view = ScratchCardView(self.user_id)
        image_file = render_scratch_card_image(view.symbols, revealed=False, cost=SCRATCH_COST)
        await interaction.response.send_message(
            f"🎫 Card purchased for {format_coins(SCRATCH_COST)}! Click Scratch to reveal.",
            file=image_file,
            view=view,
            ephemeral=True,
        )


class SlotsBetModal(discord.ui.Modal, title="🎰 Slots"):
    bet_amount = discord.ui.TextInput(label="Bet amount", placeholder="e.g. 50", required=True, max_length=10)

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet = int(self.bet_amount.value)
        except ValueError:
            await interaction.response.send_message("Enter a whole number.", ephemeral=True)
            return
        if bet <= 0:
            await interaction.response.send_message("Bet must be positive.", ephemeral=True)
            return

        balance = get_balance(self.user_id)
        if bet > balance:
            await interaction.response.send_message(f"You only have {format_coins(balance)}.", ephemeral=True)
            return

        add_balance(self.user_id, -bet)
        await interaction.response.send_message("🎰 Spinning...", ephemeral=True)

        reels = [weighted_choice(SLOT_SYMBOLS) for _ in range(3)]
        symbols = [r[0] for r in reels]

        if symbols[0] == symbols[1] == symbols[2]:
            payout = bet * reels[0][2]
            add_balance(self.user_id, payout)
            outcome = "jackpot"
        elif symbols[0] == symbols[1] or symbols[1] == symbols[2] or symbols[0] == symbols[2]:
            add_balance(self.user_id, bet)  # break even
            payout = 0
            outcome = "push"
        else:
            payout = 0
            outcome = "lose"

        new_balance = get_balance(self.user_id)
        image_file = render_slots_image(symbols, bet, payout, outcome)
        await interaction.edit_original_response(
            content=f"Balance: {format_coins(new_balance)}", attachments=[image_file]
        )


class CoinflipModal(discord.ui.Modal, title="🪙 Coinflip"):
    bet_amount = discord.ui.TextInput(label="Bet amount", placeholder="e.g. 50", required=True, max_length=10)
    choice = discord.ui.TextInput(label="Heads or Tails?", placeholder="heads / tails", required=True, max_length=10)

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet = int(self.bet_amount.value)
        except ValueError:
            await interaction.response.send_message("Enter a whole number for the bet.", ephemeral=True)
            return
        if bet <= 0:
            await interaction.response.send_message("Bet must be positive.", ephemeral=True)
            return

        guess = self.choice.value.strip().lower()
        if guess not in ("heads", "tails"):
            await interaction.response.send_message("Type either 'heads' or 'tails'.", ephemeral=True)
            return

        balance = get_balance(self.user_id)
        if bet > balance:
            await interaction.response.send_message(f"You only have {format_coins(balance)}.", ephemeral=True)
            return

        add_balance(self.user_id, -bet)
        result_flip = random.choice(["heads", "tails"])
        win = guess == result_flip
        payout = bet * 2 if win else 0
        if win:
            add_balance(self.user_id, payout)

        new_balance = get_balance(self.user_id)
        image_file = render_coinflip_image(result_flip, win, bet, payout)
        await interaction.response.send_message(
            content=f"Balance: {format_coins(new_balance)}", file=image_file, ephemeral=True
        )


class ScratchCardRevealButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Scratch!", emoji="🪙", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        view: "ScratchCardView" = self.view
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("This isn't your scratch card!", ephemeral=True)
            return
        if view.revealed:
            await interaction.response.send_message("Already scratched!", ephemeral=True)
            return

        view.revealed = True
        self.disabled = True

        counts = {}
        for s in view.symbols:
            counts[s] = counts.get(s, 0) + 1

        best_mult, winning_symbol = 0, None
        for symbol, count in counts.items():
            if count >= 3:
                mult = next((m for sym, w, m in SCRATCH_SYMBOLS if sym == symbol), 0)
                if mult > best_mult:
                    best_mult, winning_symbol = mult, symbol

        payout = SCRATCH_COST * best_mult if winning_symbol and best_mult > 0 else 0
        if payout > 0:
            add_balance(view.user_id, payout)

        new_balance = get_balance(view.user_id)
        image_file = render_scratch_card_image(
            view.symbols, revealed=True, cost=SCRATCH_COST,
            payout=payout if payout > 0 else None, winning_symbol=winning_symbol,
        )
        await interaction.response.edit_message(
            content=f"Balance: {format_coins(new_balance)}", attachments=[image_file], view=view
        )


class ScratchCardView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.symbols = [weighted_choice(SCRATCH_SYMBOLS)[0] for _ in range(9)]
        self.revealed = False
        self.add_item(ScratchCardRevealButton())


@bot.tree.command(name="gambling", description="Open the gambling menu — slots, coinflip, and scratch cards.")
async def gambling_command(interaction: discord.Interaction):
    balance = get_balance(interaction.user.id)
    view = GamblingHubView(interaction.user.id)
    await interaction.response.send_message(
        f"🎲 **Gambling Hub**\nYour balance: {format_coins(balance)}\n\nPick a game:",
        view=view,
        ephemeral=True,
    )


@bot.tree.command(name="balance", description="Check your (or someone else's) coin balance.")
@app_commands.describe(user="Whose balance to check (optional)")
async def balance_command(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    balance = get_balance(target.id)
    await interaction.response.send_message(f"{target.display_name}'s balance: {format_coins(balance)}")


@bot.tree.command(name="give", description="Give some of your coins to another user.")
@app_commands.describe(user="Who to give coins to", amount="How many coins to give")
async def give_command(interaction: discord.Interaction, user: discord.Member, amount: int):
    if user.id == interaction.user.id:
        await interaction.response.send_message("You can't give coins to yourself!", ephemeral=True)
        return
    if user.bot:
        await interaction.response.send_message("You can't give coins to a bot!", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("Amount must be positive.", ephemeral=True)
        return

    sender_balance = get_balance(interaction.user.id)
    if amount > sender_balance:
        await interaction.response.send_message(f"You only have {format_coins(sender_balance)}.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)
    add_balance(user.id, amount)

    await interaction.response.send_message(
        f"💸 {interaction.user.mention} gave {format_coins(amount)} to {user.mention}!"
    )


@bot.tree.command(name="cheatcoins", description="Admin only: manually edit a user's coin balance with a code.")
@app_commands.describe(code="The access code", user="User to edit", amount="New balance to set for this user")
async def cheatcoins_command(interaction: discord.Interaction, code: str, user: discord.Member, amount: int):
    if code != CHEAT_CODE:
        await interaction.response.send_message("❌ Incorrect code.", ephemeral=True)
        return
    if amount < 0:
        await interaction.response.send_message("Balance can't be negative.", ephemeral=True)
        return

    get_balance(user.id)  # ensure entry exists
    scores[str(user.id)]["coins"] = amount
    save_scores(scores)

    await interaction.response.send_message(
        f"✅ Set **{user.display_name}**'s balance to {format_coins(amount)}.", ephemeral=True
    )


# ----------------------------------------------------------------------
# NPC CARD
# ----------------------------------------------------------------------
# Generates a fake "RPG NPC encounter" card using the target's real avatar,
# a random made-up role, a random Arabic dialogue line, and stat bars that
# are all suspiciously identical (the joke).
#
# Arabic text note: proper Arabic requires letter-joining (shaping) and
# right-to-left ordering — Pillow can't do this on its own, but its bundled
# "raqm" text-layout engine handles both automatically as long as libfribidi
# is present on the host at runtime (see nixpacks.toml, which installs it).

# Arabic text needs letter-joining (shaping) and right-to-left reordering to
# display correctly. Pillow can do this automatically via a bundled engine
# called raqm, but that depends on a system library (libfribidi) being
# present on the host, which turned out to be unreliable on Railway even
# with it explicitly installed. This does the shaping/reordering ourselves
# in pure Python instead, so it works regardless of what's on the host.
def _prepare_arabic_text(text: str) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception as e:
        print(f"Arabic text shaping failed, showing raw text instead: {e}")
        return text


NPC_ROLES = [
    "Village Elder", "Wandering Merchant", "Tavern Keeper", "Random Guard #47",
    "Suspicious Blacksmith", "Quest Giver #12", "Retired Adventurer", "Potion Seller",
    "Mysterious Stranger", "Chicken Farmer", "Bridge Troll (Off Duty)", "Local Gossip",
    "Failed Wizard", "Part-Time Dragon Slayer", "Confused Skeleton", "Tax Collector",
]

# A big pool of silly, clean (no profanity), absurdist "NPC dialogue" lines.
NPC_LINES_AR = [
    "أبيع البطاطا بسعر الذهب اليوم.",
    "لماذا تنظر إلي هكذا؟ اذهب اضغط على شيء آخر.",
    "أنا لست NPC، أنا فقط أتصرف بغرابة.",
    "قابلت تنيناً أمس، كان يشتكي من الإيجار.",
    "خبز اليوم طازج... من الأسبوع الماضي.",
    "إذا ضغطت علي مرة أخرى سأبدأ بالبكاء.",
    "أملك سيفاً سحرياً لكنه في الغسيل حالياً.",
    "الحكيم يقول: لا تأكل الفطر الغريب.",
    "أعمل هنا منذ ٣٠٠ عام، لم يعطوني إجازة قط.",
    "توقف عن الضغط، أنا أحاول أن آخذ قيلولة.",
    "لدي مهمة لك: أحضر لي قهوة، من فضلك.",
    "سمعت أن البطل الحقيقي ينام باكراً.",
    "دجاجتي تتكلم أفضل مني، اسألها.",
    "أنا حارس هذا الجسر، لكنني أخاف من المرتفعات.",
    "كل ما أملكه هو هذا القميص وبعض الأحلام.",
    "التنين في الكهف مجرد قطة كبيرة، صدقني.",
    "أبحث عن وظيفة أفضل، هل تعرف أحداً؟",
    "لو كنت بطلاً حقيقياً لكنت اشتريت بيتاً.",
    "أعيد نفس الجملة كل يوم منذ سنوات، مساعدة!",
    "هل جربت إطفاءه وإعادة تشغيله؟",
    "لدي قوة سحرية: أضيع دائماً الطريق.",
    "الملك ينام كثيراً، لهذا المملكة فوضى.",
    "أنا لست وحشاً، أنا فقط لم أستحم اليوم.",
    "اشتريت هذا الدرع من سوق مستعمل، رخيص جداً.",
    "أعرف كل شيء عن القرية إلا أين أضع مفاتيحي.",
    "صديقي الفارس اختفى، ربما ذهب ليشتري خبزاً.",
    "أحلم بأن أصبح تنيناً يوماً ما.",
    "أرض المعركة هادئة اليوم، ربما لأن الجميع نائم.",
    "أنا أحمل هذا الرمح منذ خمس سنوات ولم أستخدمه أبداً.",
    "سألتني الملكة عن الطريق، فأرسلتها إلى الاتجاه الخاطئ.",
    "قطتي أذكى مني، للأسف.",
    "أبحث عن مفتاح بيتي منذ الصباح.",
    "لدي نبوءة: ستدفع أكثر مما تتوقع في هذا المتجر.",
    "الفارس الأسود ليس شريراً، هو فقط يحب اللون الأسود.",
    "سمعت أن هناك وحشاً في الغابة، لكنه قد يكون مجرد أرنب كبير.",
    "أملك خريطة كنز لكنني ضعتها.",
    "أخي التوأم أفضل مني في كل شيء، اسأل أي شخص.",
    "أعتقد أن هذا القفل معطل، جربت المفتاح الخاطئ طوال اليوم.",
    "لا تثق بالساحر، هو فقط يرتدي قبعة.",
    "أبيع دروعاً مقاومة لكل شيء إلا المطر.",
    "الغراب الذي يتبعك ليس نذير شؤم، إنه فقط يريد الخبز.",
    "أنا فارس متقاعد، الآن أربي الدجاج.",
    "سيفي مصنوع من الخشب، لكن لا تخبر أحداً.",
    "أحاول أن أتعلم السحر منذ سنوات، لم ينجح شيء بعد.",
    "قريتي صغيرة جداً، عدد الدجاج أكبر من عدد السكان.",
    "الشبح الذي يسكن القلعة يحب فقط أن يلعب الورق.",
    "أعطيك نصيحة مجانية: لا تأكل هنا.",
    "أنا لست بخيلاً، أنا فقط أحب عد أموالي كثيراً.",
    "التنين يعيش في الجبل، لكنه في الحقيقة يخاف من الفئران.",
    "لدي درع سحري، لكنه فقط يحميني من البرد.",
    "أبحث عن مساعد، الراتب: الخبرة فقط.",
    "قابلت عرافة، قالت لي إنني سأقابل شخصاً غريباً اليوم... وها أنت.",
    "لا أخاف الموت، أخاف فقط من نفاد القهوة.",
    "بنيت هذا الكوخ بيدي، ولهذا هو مائل قليلاً.",
    "الحورية في البحيرة تطلب فقط أن تتكلم معها، لا شيء أكثر.",
    "عندي مزرعة، لكن كل ما أزرعه هو الفجل.",
    "أختي الساحرة حولتني إلى ضفدع أسبوعاً كاملاً، كانت غلطة بسيطة.",
    "أنا أعرف كل أسرار القرية إلا كيف أطبخ البيض.",
    "الوحش تحت الجسر مجرد رجل عجوز يحب الهدوء.",
    "أملك تعويذة قوية، لكنها فقط تجعل الشعر يقف.",
    "الملك يرسل لي رسائل، لكنها كلها عن الضرائب.",
    "أنا حداد، لكن سيوفي تنكسر بسهولة، لا تخبر الزبائن.",
    "لدي جواد سريع جداً، للأسف هو خائف من الفراشات.",
    "حاولت أن أصبح فارساً، لكن الدرع كان ثقيلاً جداً.",
    "أبيع تعاويذ حظ، لكنها لم تنجح معي أبداً.",
    "قابلت جنياً، طلب مني فقط قطعة جبن.",
    "أظن أن بيتي مسكون، أو أن الرياح قوية جداً.",
    "الغولم الذي أملكه ينظف البيت لكنه بطيء جداً.",
    "أعرف تعويذة تحويل الحجر إلى ذهب، لكنها لا تعمل.",
    "المحارب الأسطوري الذي تبحث عنه ذهب لشراء الخبز.",
    "قطعت الغابة كلها بحثاً عن الكنز، وجدت فقط جوزة.",
    "الأميرة هربت من القلعة لأنها تريد أن تصبح خبازة.",
    "لدي كتاب تعاويذ، لكن معظم الصفحات مبللة.",
    "الغيمة السوداء فوق القرية هي فقط دخان من مطبخي.",
    "لا تسألني عن الاتجاهات، أنا تائه منذ الصباح.",
    "أملك خنجراً سحرياً، لكنه فقط يقطع الخبز جيداً.",
    "الفارس الذهبي ليس ذهبياً حقاً، إنه فقط يحب البريق.",
    "أبحث عن شريك في التجارة، الشرط الوحيد: يحب الجبن.",
    "الساحرة العجوز تبيع فقط الشاي، رغم أن الجميع يخافها.",
    "حاولت ترويض تنيناً، لكنه أكل حذائي فقط.",
]


# Serif fonts for the elegant/glassy card style (Arabic dialogue still uses
# the Sans font via _casino_font, since DejaVu Serif has no Arabic glyphs).
_NPC_FONT_SERIF_BOLD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "DejaVuSerif-Bold.ttf")
_NPC_FONT_SERIF_REGULAR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "DejaVuSerif.ttf")
_NPC_FONT_SERIF_ITALIC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "DejaVuSerif-Italic.ttf")


def _npc_vertical_gradient(size, top_color, bottom_color) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(top_color[i] + (bottom_color[i]-top_color[i])*t) for i in range(3))
    return img.resize((w, h))


def _npc_soft_glow(base_img: Image.Image, box, color, peak_opacity, blur):
    """See the note in _render_npc_card: this draws the glow shape on a
    grayscale mask (not RGBA) specifically to avoid dark-fringing artifacts
    that blurring a transparent RGBA canvas directly would cause."""
    mask = Image.new("L", base_img.size, 0)
    ImageDraw.Draw(mask).ellipse(box, fill=peak_opacity)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    color_layer = Image.new("RGB", base_img.size, color)
    base_img.paste(color_layer, (0, 0), mask)


def _npc_soft_shadow_rect(base_img: Image.Image, box, radius, color, peak_opacity, blur, offset=(0, 0)):
    mask = Image.new("L", base_img.size, 0)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(mask).rounded_rectangle(
        [x0+offset[0], y0+offset[1], x1+offset[0], y1+offset[1]], radius=radius, fill=peak_opacity
    )
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    color_layer = Image.new("RGB", base_img.size, color)
    base_img.paste(color_layer, (0, 0), mask)


def _npc_draw_sparkle(draw, cx, cy, size, color):
    draw.polygon([
        (cx, cy-size), (cx+size*0.22, cy-size*0.22), (cx+size, cy), (cx+size*0.22, cy+size*0.22),
        (cx, cy+size), (cx-size*0.22, cy+size*0.22), (cx-size, cy), (cx-size*0.22, cy-size*0.22),
    ], fill=color)


def _npc_draw_icon_badge(draw, cx, cy, r, icon_fn, bg_color, border_color, icon_color):
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=bg_color, outline=border_color, width=2)
    icon_fn(draw, cx, cy, r*0.55, icon_color)


def _npc_icon_dumbbell(draw, cx, cy, r, color):
    draw.ellipse([cx-r*0.9, cy-r*0.5, cx-r*0.5, cy+r*0.5], fill=color)
    draw.ellipse([cx+r*0.5, cy-r*0.5, cx+r*0.9, cy+r*0.5], fill=color)
    draw.rectangle([cx-r*0.6, cy-r*0.18, cx+r*0.6, cy+r*0.18], fill=color)


def _npc_icon_book(draw, cx, cy, r, color):
    draw.polygon([(cx, cy-r*0.55), (cx-r*0.85, cy-r*0.3), (cx-r*0.85, cy+r*0.5), (cx, cy+r*0.25)], fill=color)
    draw.polygon([(cx, cy-r*0.55), (cx+r*0.85, cy-r*0.3), (cx+r*0.85, cy+r*0.5), (cx, cy+r*0.25)], fill=color)
    draw.line([cx, cy-r*0.55, cx, cy+r*0.25], fill=(255, 255, 255), width=2)


def _npc_icon_clover(draw, cx, cy, r, color):
    off = r * 0.42
    for dx, dy in [(-off, -off), (off, -off), (-off, off), (off, off)]:
        draw.ellipse([cx+dx-r*0.42, cy+dy-r*0.42, cx+dx+r*0.42, cy+dy+r*0.42], fill=color)
    draw.line([cx, cy+r*0.3, cx, cy+r*1.0], fill=color, width=3)


def _npc_icon_heart(draw, cx, cy, r, color):
    draw.pieslice([cx-r*0.9, cy-r*0.7, cx, cy+r*0.2], 180, 360, fill=color)
    draw.pieslice([cx, cy-r*0.7, cx+r*0.9, cy+r*0.2], 180, 360, fill=color)
    draw.polygon([(cx-r*0.85, cy-r*0.1), (cx+r*0.85, cy-r*0.1), (cx, cy+r*0.9)], fill=color)


def _render_npc_card(avatar_img: Image.Image, username: str, role: str, dialogue_ar: str, stat_value: int) -> discord.File:
    """Glassy/elegant NPC card: pastel gradient background, serif typography,
    icon-labeled stat bars, and decorative sparkle/quote accents.

    Glow/shadow note: blurring an RGBA shape drawn on a fully-transparent
    canvas causes GaussianBlur to pull in black from the transparent
    surroundings (they're still RGB=black underneath, just alpha=0), producing
    dark fringing instead of a clean soft glow. The fix used throughout below
    is to draw the shape on a single-channel grayscale (L) mask instead, blur
    that mask (no color channels to fringe), then paste a flat color layer
    through it — this is what _npc_soft_glow / _npc_soft_shadow_rect do.
    """
    ss = CASINO_SUPERSAMPLE
    W, H = 460, 960  # generous height so nothing gets clipped
    PURPLE = (140, 110, 190)
    PURPLE_DARK = (90, 65, 145)
    GOLD_MUTED = (170, 140, 90)
    BG_LIGHT = (248, 245, 252)

    ss_img = Image.new("RGB", (W*ss, H*ss), BG_LIGHT)
    ss_img.paste(_npc_vertical_gradient((W*ss, H*ss), (250, 248, 253), (232, 224, 245)), (0, 0))
    draw = ImageDraw.Draw(ss_img)

    rnd = random.Random()
    for _ in range(30):
        sx, sy = rnd.uniform(20, W-20)*ss, rnd.uniform(20, H-20)*ss
        s = rnd.uniform(2, 5)*ss
        _npc_draw_sparkle(draw, sx, sy, s, (225, 215, 240))

    _npc_soft_shadow_rect(ss_img, [10*ss, 10*ss, (W-10)*ss, (H-10)*ss], radius=30*ss, color=(180, 165, 210), peak_opacity=25, blur=16*ss)
    draw = ImageDraw.Draw(ss_img)
    draw.rounded_rectangle([10*ss, 10*ss, (W-10)*ss, (H-10)*ss], radius=30*ss, outline=(210, 195, 235), width=3*ss)

    f_title = ImageFont.truetype(_NPC_FONT_SERIF_BOLD_PATH, 34*ss)
    title = "NPC ENCOUNTER"
    bbox = draw.textbbox((0, 0), title, font=f_title)
    tw = bbox[2] - bbox[0]
    draw.text((W*ss/2, 55*ss), title, font=f_title, fill=PURPLE, anchor="mm")
    _npc_draw_sparkle(draw, W*ss/2 - tw/2 - 22*ss, 55*ss, 8*ss, PURPLE)
    _npc_draw_sparkle(draw, W*ss/2 + tw/2 + 22*ss, 55*ss, 8*ss, PURPLE)
    draw.line([(W*ss/2-30*ss, 78*ss), (W*ss/2+30*ss, 78*ss)], fill=(200, 185, 225), width=2*ss)
    _npc_draw_sparkle(draw, W*ss/2, 78*ss, 5*ss, PURPLE_DARK)

    avatar_size = 190 * ss
    ax, ay = W*ss/2 - avatar_size/2, 105*ss
    acx, acy = ax + avatar_size/2, ay + avatar_size/2
    _npc_soft_glow(
        ss_img,
        [acx-avatar_size/2-20*ss, acy-avatar_size/2-20*ss, acx+avatar_size/2+20*ss, acy+avatar_size/2+20*ss],
        (200, 180, 230), 45, 12*ss,
    )
    draw = ImageDraw.Draw(ss_img)

    avatar_resized = avatar_img.resize((int(avatar_size), int(avatar_size))).convert("RGB")
    amask = Image.new("L", (int(avatar_size), int(avatar_size)), 0)
    ImageDraw.Draw(amask).ellipse([0, 0, int(avatar_size)-1, int(avatar_size)-1], fill=255)
    ss_img.paste(avatar_resized, (int(ax), int(ay)), amask)
    draw = ImageDraw.Draw(ss_img)
    draw.ellipse([ax, ay, ax+avatar_size, ay+avatar_size], outline=(220, 200, 150), width=4*ss)
    draw.ellipse([ax+5*ss, ay+5*ss, ax+avatar_size-5*ss, ay+avatar_size-5*ss], outline=(255, 255, 255), width=2*ss)

    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle - 90)
        r_pos = avatar_size/2 + 8*ss
        sx = W*ss/2 + r_pos * math.cos(rad)
        sy = acy + r_pos * math.sin(rad)
        _npc_draw_sparkle(draw, sx, sy, 9*ss, PURPLE)

    name_y = ay + avatar_size + 45*ss
    f_name = ImageFont.truetype(_NPC_FONT_SERIF_BOLD_PATH, 36*ss)
    nbbox = draw.textbbox((0, 0), username.upper(), font=f_name)
    nw = nbbox[2] - nbbox[0]
    draw.text((W*ss/2, name_y), username.upper(), font=f_name, fill=PURPLE, anchor="mm")
    _npc_draw_sparkle(draw, W*ss/2-nw/2-20*ss, name_y, 7*ss, PURPLE)
    _npc_draw_sparkle(draw, W*ss/2+nw/2+20*ss, name_y, 7*ss, PURPLE)

    role_y = name_y + 38*ss
    f_role = ImageFont.truetype(_NPC_FONT_SERIF_ITALIC_PATH, 19*ss)
    role_text = f'"{role}"'
    rbbox = draw.textbbox((0, 0), role_text, font=f_role)
    rw = rbbox[2] - rbbox[0]
    draw.text((W*ss/2, role_y), role_text, font=f_role, fill=GOLD_MUTED, anchor="mm")
    draw.line([(W*ss/2-rw/2-18*ss, role_y), (W*ss/2-rw/2-6*ss, role_y)], fill=GOLD_MUTED, width=2*ss)
    draw.line([(W*ss/2+rw/2+6*ss, role_y), (W*ss/2+rw/2+18*ss, role_y)], fill=GOLD_MUTED, width=2*ss)

    box_top = role_y + 40*ss
    box_bottom = box_top + 130*ss
    _npc_soft_shadow_rect(ss_img, [30*ss, box_top, (W-30)*ss, box_bottom], radius=22*ss, color=(160, 145, 190), peak_opacity=30, blur=10*ss, offset=(0, 6*ss))
    draw = ImageDraw.Draw(ss_img)

    glass_w, glass_h = int(W*ss-60*ss), int(box_bottom-box_top)
    glass_overlay = Image.new("RGBA", ss_img.size, (0, 0, 0, 0))
    small_glass = Image.new("RGBA", (glass_w, glass_h), (255, 255, 255, 190))
    small_mask = Image.new("L", (glass_w, glass_h), 0)
    ImageDraw.Draw(small_mask).rounded_rectangle([0, 0, glass_w-1, glass_h-1], radius=22*ss, fill=255)
    small_glass.putalpha(small_mask)
    glass_overlay.paste(small_glass, (int(30*ss), int(box_top)), small_glass)
    ss_img = Image.alpha_composite(ss_img.convert("RGBA"), glass_overlay).convert("RGB")
    draw = ImageDraw.Draw(ss_img)
    draw.rounded_rectangle([30*ss, box_top, (W-30)*ss, box_bottom], radius=22*ss, outline=(215, 200, 235), width=2*ss)

    f_bigquote = ImageFont.truetype(_NPC_FONT_SERIF_BOLD_PATH, 60*ss)
    draw.text((55*ss, box_top+10*ss), '"', font=f_bigquote, fill=(200, 180, 225), anchor="la")
    draw.text((W*ss-55*ss, box_bottom-55*ss), '"', font=f_bigquote, fill=(200, 180, 225), anchor="la")

    max_width = W*ss - 80*ss
    f_measure = _casino_font(False, 23*ss)
    words = dialogue_ar.split(" ")
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        wbbox = draw.textbbox((0, 0), test, font=f_measure)
        if wbbox[2]-wbbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    # Shape + reorder each line ourselves (pure-Python, no system-library
    # dependency — see _prepare_arabic_text), then draw with Pillow's BASIC
    # layout engine so the already-shaped text isn't processed a second time.
    display_lines = [_prepare_arabic_text(line) for line in lines]
    f_dialogue_basic = ImageFont.truetype(_CASINO_FONT_REGULAR_PATH, 24*ss, layout_engine=ImageFont.Layout.BASIC)

    line_height = 36 * ss
    total_h = len(display_lines) * line_height
    start_y = (box_top+box_bottom)/2 - total_h/2 + line_height/2
    for i, line in enumerate(display_lines):
        draw.text((W*ss/2, start_y + i*line_height), line, font=f_dialogue_basic, fill=(60, 45, 80), anchor="mm")

    _npc_draw_sparkle(draw, W*ss/2, box_bottom+18*ss, 6*ss, PURPLE)

    stats = [("STR", _npc_icon_dumbbell), ("INT", _npc_icon_book), ("LUCK", _npc_icon_clover), ("RIZZ", _npc_icon_heart)]
    bar_top = box_bottom + 45*ss
    row_h = 46 * ss
    for i, (label, icon_fn) in enumerate(stats):
        y = bar_top + i*(row_h + 14*ss)
        badge_r = 20*ss
        _npc_draw_icon_badge(draw, 45*ss+badge_r, y+row_h/2, badge_r, icon_fn, (238, 230, 250), PURPLE, PURPLE_DARK)
        f_label = ImageFont.truetype(_NPC_FONT_SERIF_BOLD_PATH, 17*ss)
        draw.text((45*ss+badge_r*2+14*ss, y+row_h/2), label, font=f_label, fill=PURPLE_DARK, anchor="lm")

        bar_x0 = 45*ss + badge_r*2 + 14*ss + 70*ss
        bar_x1 = W*ss - 130*ss
        bar_h = 20 * ss
        bar_y = y + row_h/2 - bar_h/2
        draw.rounded_rectangle([bar_x0, bar_y, bar_x1, bar_y+bar_h], radius=10*ss, fill=(230, 222, 242), outline=(210, 195, 230), width=2*ss)
        fill_w = (bar_x1-bar_x0) * (stat_value/100)
        if fill_w > 4*ss:
            grad = _npc_vertical_gradient((int(fill_w), int(bar_h)), (200, 170, 235), (150, 110, 210))
            gmask2 = Image.new("L", grad.size, 0)
            ImageDraw.Draw(gmask2).rounded_rectangle([0, 0, grad.width-1, grad.height-1], radius=10*ss, fill=255)
            ss_img.paste(grad, (int(bar_x0), int(bar_y)), gmask2)
            draw = ImageDraw.Draw(ss_img)

        pill_x0, pill_x1 = W*ss - 118*ss, W*ss - 45*ss
        draw.rounded_rectangle([pill_x0, y+row_h/2-16*ss, pill_x1, y+row_h/2+16*ss], radius=16*ss, fill=(238, 230, 250), outline=(210, 195, 230), width=2*ss)
        f_val = ImageFont.truetype(_NPC_FONT_SERIF_REGULAR_PATH, 15*ss)
        draw.text(((pill_x0+pill_x1)/2, y+row_h/2), f"{stat_value} / 100", font=f_val, fill=PURPLE_DARK, anchor="mm")

    footer_y = bar_top + len(stats)*(row_h + 14*ss) + 20*ss
    f_footer = ImageFont.truetype(_NPC_FONT_SERIF_ITALIC_PATH, 15*ss)
    footer_text = "(suspiciously identical stats)"
    fbbox = draw.textbbox((0, 0), footer_text, font=f_footer)
    fw = fbbox[2] - fbbox[0]
    draw.text((W*ss/2, footer_y), footer_text, font=f_footer, fill=(150, 135, 175), anchor="mm")
    _npc_draw_sparkle(draw, W*ss/2-fw/2-16*ss, footer_y, 5*ss, PURPLE)
    _npc_draw_sparkle(draw, W*ss/2+fw/2+16*ss, footer_y, 5*ss, PURPLE)

    final = ss_img.resize((W, H), Image.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(fp=buffer, filename="npc.png")


@bot.tree.command(name="npc", description="Turn someone into a fake RPG NPC with a random dialogue line.")
@app_commands.describe(user="Who to turn into an NPC (optional, defaults to yourself)")
async def npc_command(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    await interaction.response.defer()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(target.display_avatar.replace(size=256, format="png").url)) as resp:
                if resp.status != 200:
                    await interaction.followup.send("Couldn't fetch that avatar, try again.")
                    return
                avatar_bytes = await resp.read()
    except aiohttp.ClientError:
        await interaction.followup.send("Couldn't fetch that avatar, try again.")
        return

    avatar_img = Image.open(io.BytesIO(avatar_bytes))
    role = random.choice(NPC_ROLES)
    dialogue = random.choice(NPC_LINES_AR)
    stat_value = random.randint(1, 99)  # same value used for every stat bar — that's the joke

    image_file = _render_npc_card(avatar_img, sanitize_for_font(target.display_name), role, dialogue, stat_value)
    await interaction.followup.send(file=image_file)


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
        name="/dino",
        value="Sends a random dinosaur gif (sometimes two of them fighting).",
        inline=False,
    )
    embed_en.add_field(
        name="/fries",
        value="Sends a random fries (or potato) gif.",
        inline=False,
    )
    embed_en.add_field(
        name="/npc",
        value="Turns someone into a fake RPG NPC card with their avatar, a random role, and a random Arabic dialogue line.",
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
        name="/gambling",
        value="Opens the gambling menu — slots, coinflip, and scratch cards.",
        inline=False,
    )
    embed_en.add_field(
        name="/balance",
        value="Check your (or someone else's) coin balance.",
        inline=False,
    )
    embed_en.add_field(
        name="/give",
        value="Give some of your coins to another user.",
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
        name="/dino",
        value="يرسل صورة متحركة عشوائية لديناصور (أحياناً اثنان يتقاتلان).",
        inline=False,
    )
    embed_ar.add_field(
        name="/fries",
        value="يرسل صورة متحركة عشوائية للبطاطا المقلية (أو البطاطا العادية).",
        inline=False,
    )
    embed_ar.add_field(
        name="/npc",
        value="يحوّل شخصاً إلى بطاقة NPC وهمية بصورته الشخصية، دور عشوائي، وجملة حوار عشوائية بالعربية.",
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
        name="/gambling",
        value="يفتح قائمة القمار — سلوتس، عملة معدنية، وبطاقات خدش.",
        inline=False,
    )
    embed_ar.add_field(
        name="/balance",
        value="تحقق من رصيدك (أو رصيد شخص آخر) من العملات.",
        inline=False,
    )
    embed_ar.add_field(
        name="/give",
        value="أعطِ بعضاً من عملاتك لشخص آخر.",
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


async def send_voice_message(channel_id: int, clip_path: str, duration_secs: float, waveform_b64: str):
    """Posts a real voice message (the blue waveform bubble) via a raw API call,
    since discord.py's high-level send() doesn't yet support the required
    flags/waveform/duration fields for this message type."""
    if not os.path.exists(clip_path):
        print(f"Voice clip not found at {clip_path}, skipping voice message.")
        return

    with open(clip_path, "rb") as f:
        audio_bytes = f.read()

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {TOKEN}"}
    payload = {
        "flags": 8192,  # IS_VOICE_MESSAGE
        "attachments": [{
            "id": "0",
            "filename": "voice-message.ogg",
            "duration_secs": duration_secs,
            "waveform": waveform_b64,
        }],
    }

    form = aiohttp.FormData()
    form.add_field("payload_json", json.dumps(payload), content_type="application/json")
    form.add_field("files[0]", audio_bytes, filename="voice-message.ogg", content_type="audio/ogg")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=form) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    print(f"Voice message send failed ({resp.status}): {text}")
    except aiohttp.ClientError as e:
        print(f"Voice message send error: {e}")


async def handle_voice_mention_easter_egg(message: discord.Message):
    """If VOICE_MENTION_TARGET_USER_ID is explicitly @mentioned (not just
    replied to with the ping toggle on), post the configured voice clip."""
    if VOICE_MENTION_PATTERN.search(message.content):
        await send_voice_message(message.channel.id, VOICE_CLIP_PATH, VOICE_CLIP_DURATION_SECS, VOICE_CLIP_WAVEFORM_B64)


async def handle_bot_mention_voice_easter_egg(message: discord.Message):
    """If the bot itself is explicitly @mentioned (not replied to), post the
    configured voice clip."""
    bot_mention_pattern = re.compile(rf"<@!?{bot.user.id}>")
    if bot_mention_pattern.search(message.content):
        await send_voice_message(message.channel.id, BOT_MENTION_VOICE_CLIP_PATH, BOT_MENTION_VOICE_CLIP_DURATION_SECS, BOT_MENTION_VOICE_CLIP_WAVEFORM_B64)


def _message_violates_policy(content: str) -> bool:
    if MIDDLE_FINGER_PATTERN.search(content):
        return True
    lowered = content.lower()
    return any(phrase in lowered for phrase in BANNED_PHRASES)


async def handle_auto_moderation(message: discord.Message) -> bool:
    """Deletes the message if it violates policy and DMs the dev with details.
    Returns True if the message was removed (so on_message can stop early and
    skip other handlers that would otherwise act on now-deleted content)."""
    if not _message_violates_policy(message.content):
        return False

    # Capture everything before deleting, since the message object becomes
    # unusable for some properties (and pointless to reference) afterward.
    content = message.content
    author = message.author
    channel = message.channel
    guild = message.guild
    timestamp = message.created_at
    message_id = message.id

    delete_error = None
    try:
        await message.delete()
    except discord.Forbidden:
        delete_error = "Missing 'Manage Messages' permission — the message was flagged but NOT deleted."
    except discord.HTTPException as e:
        delete_error = f"Delete failed: {e}"

    try:
        dev_user = await bot.fetch_user(MOD_ALERT_USER_ID)
        embed = discord.Embed(
            title="🚨 Auto-moderation: message removed" if not delete_error else "🚨 Auto-moderation: flagged (not deleted)",
            description=content if content else "*(no text content — likely just an emoji/attachment)*",
            color=discord.Color.red(),
            timestamp=timestamp,
        )
        embed.add_field(name="Sent by", value=f"{author} ({author.id})", inline=False)
        embed.add_field(name="Channel", value=f"#{channel.name} ({channel.id})" if hasattr(channel, "name") else str(channel), inline=False)
        embed.add_field(name="Server", value=f"{guild.name} ({guild.id})" if guild else "DM", inline=False)
        embed.add_field(name="Message ID", value=str(message_id), inline=False)
        if delete_error:
            embed.add_field(name="⚠️ Deletion issue", value=delete_error, inline=False)
        await dev_user.send(embed=embed)
    except discord.HTTPException as e:
        print(f"Could not DM dev about auto-moderation event: {e}")

    return delete_error is None


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if await handle_auto_moderation(message):
        return  # message was deleted — don't process it further

    await handle_dot_reply_easter_egg(message)
    await handle_voice_mention_easter_egg(message)
    await handle_bot_mention_voice_easter_egg(message)

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
