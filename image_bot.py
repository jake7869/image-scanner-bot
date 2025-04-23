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
    "Weed": "templates/weed.png",
    "Coke Pouch": "templates/coke.png",
    "Meth Pouch": "templates/meth.png",
    "Spice Pouch": "templates/spice.png",
    "Meow Meow": "templates/meow.png",
    "Money": "templates/money.png"
}

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
        print("❌ No attachments found.")
        return

    for attachment in message.attachments:
        if attachment.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            await attachment.save("latest.png")
            print("✅ Image saved as latest.png")

            img = cv2.imread("latest.png")
            if img is None:
                print("❌ Failed to load image with OpenCV.")
                return

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            print("🧠 Loaded image into OpenCV")
            print(f"📐 Image shape: {img.shape}")
            print("🔎 Processing image...")

            found = []
            for label, path in TEMPLATES.items():
                print(f"🔍 Checking template: {label}")
                template = cv2.imread(path, 0)
                if template is None:
                    print(f"❌ Failed to load template: {path}")
                    continue

                res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                print(f"📈 {label}: Match score {max_val:.3f}")

                if max_val > 0.7:
                    found.append(label)

            if found:
                print(f"✅ Match found: {found}")
                await message.channel.send(f"{message.author.mention} - Detected: {', '.join(found)}")
            else:
                print("❌ No items matched.")
                await message.channel.send(f"{message.author.mention} - No items matched.")

bot.run(TOKEN)
