import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import cv2
import pytesseract
import numpy as np
from PIL import Image

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ALERT_USER_ID = int(os.getenv("ALERT_USER_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

TEMPLATES = {
    "Dirty Money": "templates/dirty_money.png",
    "Money": "templates/clean_money.png",
    "Coke Pooch": "templates/coke.png",
    "Meth Pooch": "templates/meth.png",
    "Meow Meow": "templates/meow.png",
    "Spice Pooch": "templates/spice.png",
    "AK47 Baggy": "templates/ak47.png",
    "Weed": "templates/weed.png"
}

STORAGE_STATE = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.channel.id != SCAN_CHANNEL_ID or message.author == bot.user:
        return

    if not message.attachments:
        return

    for attachment in message.attachments:
        if any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
            await attachment.save("latest.png")
            await process_image("latest.png", message)

async def process_image(image_path, message):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    results = {}
    for label, template_path in TEMPLATES.items():
        template = cv2.imread(template_path, 0)
        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= 0.8)
        if len(loc[0]) > 0:
            for pt in zip(*loc[::-1]):
                x, y = pt[0] + 150, pt[1] - 10  # top right area
                cropped = img[y:y + 30, x:x + 120]
                text = pytesseract.image_to_string(cropped, config='--psm 6')
                try:
                    qty = int(text.replace(",", "").replace("x", "").strip())
                    results[label] = results.get(label, 0) + qty
                except:
                    continue

    await log_results(results, message)

def calculate_changes(new, old):
    changes = {}
    for key, value in new.items():
        prev = old.get(key, 0)
        if value != prev:
            changes[key] = value - prev
    return changes

async def log_results(new_state, message):
    global STORAGE_STATE
    changes = calculate_changes(new_state, STORAGE_STATE)
    STORAGE_STATE = new_state

    if not changes:
        return

    user_text = f"{message.author.mention}"
    content = f"📦 {user_text} - Dropoff:\n"
    for item, qty in changes.items():
        sign = "added" if qty > 0 else "removed"
        content += f"{item}: {sign} {abs(qty)}\n"

    drug_total = sum(qty for k, qty in STORAGE_STATE.items() if "Pooch" in k or "Baggy" in k or k == "Weed")
    dirty_total = STORAGE_STATE.get("Dirty Money", 0)
    clean_total = STORAGE_STATE.get("Money", 0)

    content += f"\n**Storage now contains:**\n"
    content += f"\u2022 Drugs: {drug_total}\n"
    content += f"\u2022 Dirty Money: £{dirty_total:,}\n"
    content += f"\u2022 Clean Money: £{clean_total:,}"

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(content)

    if any(qty > 50 for qty in changes.values()):
        alert_user = f"<@{ALERT_USER_ID}>"
        await log_channel.send(f"⚠️ {alert_user} - unusual drop volume detected!")

bot.run(TOKEN)
