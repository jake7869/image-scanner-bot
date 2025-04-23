import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ALERT_USER_ID = int(os.getenv("ALERT_USER_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot or message.channel.id != SCAN_CHANNEL_ID:
        return

    if message.attachments:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        await log_channel.send(f"🖼️ New image received from {message.author.mention}")

    await bot.process_commands(message)

bot.run(TOKEN)
