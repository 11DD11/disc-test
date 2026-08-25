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
import random
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

SCORES_FILE = "scores.json"

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

bot = commands.Bot(command_prefix="!", intents=intents)

# channel_id -> currently active country dict (or None if no round running)
active_rounds: dict[int, dict] = {}

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
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Slash command sync failed: {e}")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


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
