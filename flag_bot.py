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
import random
import unicodedata

import discord
from discord import app_commands
from discord.ext import commands

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------

TOKEN = os.environ.get("DISCORD_TOKEN", "NzcyOTIxMzYyODU5MTYzNjg4.G5AGzT.MnNIENJocoBTwUWAtb-_eDK_yOex1dUVFwlPWw")

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

bot = commands.Bot(command_prefix="!", intents=intents)

# channel_id -> currently active country dict (or None if no round running)
active_rounds: dict[int, dict] = {}


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


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel_id = message.channel.id
    country = active_rounds.get(channel_id)

    if country:
        if is_correct_guess(message.content, country):
            active_rounds[channel_id] = None
            try:
                await message.add_reaction("✅")
            except discord.HTTPException:
                pass

            en_name = country["en"][0].title()
            ar_name = country["ar"][0]
            await message.channel.send(
                f"🎉 {message.author.mention} got it! {country['flag']} was **{en_name}** ({ar_name})"
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
