import discord
from discord.ext import commands
import os
import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"[READY] Bot logged in as {bot.user}")

@bot.event
async def on_message(message):
    print(f"[EVENT] Message received from {message.author} in channel {message.channel.id}")

    if message.author.bot:
        print("[SKIP] Message is from a bot.")
        return

    if message.channel.id != SCAN_CHANNEL_ID:
        print(f"[SKIP] Message not in scan channel ({SCAN_CHANNEL_ID}).")
        return

    if not message.attachments:
        print("[SKIP] No attachments in message.")
        return

    for attachment in message.attachments:
        if not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            print(f"[SKIP] Unsupported file type: {attachment.filename}")
            continue

        print(f"[PROCESS] Downloading attachment: {attachment.filename}")
        await attachment.save("latest.png")

        # Simulated OCR / image debug log
        print("[DEBUG] Image saved as 'latest.png'. Starting scan...")
        # ... your OCR/image logic would go here ...

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"📸 Image received from {message.author.mention} in <#{SCAN_CHANNEL_ID}>.")
        else:
            print("[ERROR] Log channel not found.")

bot.run(TOKEN)# Main bot logic placeholder
