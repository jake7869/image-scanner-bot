import discord
from discord.ext import commands
import discord
from discord.ext import commands
import os
import cv2
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))

# Set up bot with message content intent
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Define template paths
TEMPLATES = {
    "Dirty Money": "templates/dirty_money.png",
    "Clean Money": "templates/clean_money.png",
    "AK47 Baggy": "templates/ak47.png",
    "Weed": "templates/weed.png",
    "Coke Pooch": "templates/coke.png",
    "Meth Pooch": "templates/meth.png",
    "Spice Pouch": "templates/spice.png",
    "Meow Meow": "templates/meow.png",
    "Money": "templates/money.png"
}

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")

@bot.event
async def on_message(message):
    print("📥 New message received")
    if message.channel.id != SCAN_CHANNEL_ID:
        print("❌ Message not in scan channel")
        return

    if message.author.bot:
        print("⚠️ Message from bot, skipping")
        return

    if not message.attachments:
        print("⚠️ No image attachments found")
        return

    for attachment in message.attachments:
        if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            await attachment.save("temp.png")
            print("📷 Image saved as temp.png")

            img = cv2.imread("temp.png", 0)
            if img is None:
                print("❌ Failed to load image")
                return

            found = []

            for label, template_path in TEMPLATES.items():
                template = cv2.imread(template_path, 0)
                if template is None:
                    print(f"⚠️ Failed to load template: {template_path}")
                    continue

                if img.shape[0] < template.shape[0] or img.shape[1] < template.shape[1]:
                    print(f"⚠️ Template too big: {label}")
                    continue

                res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
                if (res >= 0.7).any():
                    print(f"✅ Match found: {label}")
                    found.append(label)

            os.remove("temp.png")

            if found:
                await message.channel.send(f"📦 {message.author.mention} - Detected: " + ", ".join(found))
            else:
                await message.channel.send(f"❌ {message.author.mention} - No items matched.")

# Run the bot
bot.run(TOKEN)
