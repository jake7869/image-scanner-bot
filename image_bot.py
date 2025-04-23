
import discord
from discord.ext import commands
import os
import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

TEMPLATES = {
    "Dirty Money": "templates/dirty_money.png",
    "Clean Money": "templates/clean_money.png",
    "AK47 Baggy": "templates/ak47.png",
    "Coke Pouch": "templates/coke.png",
    "Meth Pouch": "templates/meth.png",
    "Spice Pouch": "templates/spice.png",
    "Meow Meow": "templates/meow.png",
    "Money": "templates/money.png",
    "Weed": "templates/weed.png"
}

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")

@bot.event
async def on_message(message):
    print(f"[DEBUG] Message received in {message.channel.id} by {message.author}")

    if message.channel.id != SCAN_CHANNEL_ID or message.author.bot:
        print("[DEBUG] Ignored message (wrong channel or bot)")
        return

    if not message.attachments:
        print("[DEBUG] No attachments found.")
        return

    for attachment in message.attachments:
        if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            await attachment.save("temp.png")
            img = cv2.imread("temp.png", 0)
            found = []

            for label, template_path in TEMPLATES.items():
                template = cv2.imread(template_path, 0)
                if template is None or img is None or img.shape[0] < template.shape[0] or img.shape[1] < template.shape[1]:
                    continue
                result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
                if (result >= 0.7).any():
                    found.append(label)

            if found:
                await message.channel.send(f"{message.author.mention} - Detected: " + ", ".join(found))
            else:
                await message.channel.send(f"{message.author.mention} - No items matched.")
