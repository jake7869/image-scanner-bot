import os
import discord
import cv2
import numpy as np
from dotenv import load_dotenv
from discord.ext import commands
from PIL import Image
import pytesseract

load_dotenv()
TOKEN = os.getenv("YOUR_BOT_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ALERT_USER_ID = int(os.getenv("ALERT_USER_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

TEMPLATE_DIR = "templates"
ITEMS = {
    "dirty_money": {"name": "Dirty Money", "template": "dirty_money.png"},
    "clean_money": {"name": "Money", "template": "clean_money.png"},
    "ak47": {"name": "AK47 Baggy", "template": "ak47.png"},
    "weed": {"name": "Weed", "template": "weed.png"},
    "coke": {"name": "Coke Pooch", "template": "coke.png"},
    "meow": {"name": "Meow Meow", "template": "meow.png"},
    "meth": {"name": "Meth Pooch", "template": "meth.png"},
    "spice": {"name": "Spice Pooch", "template": "spice.png"}
}

latest_state = {}

def extract_quantity(cropped_image):
    gray = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]
    text = pytesseract.image_to_string(thresh, config='--psm 6')
    for part in text.split("x"):
        try:
            return int(part.replace(",", "").strip())
        except ValueError:
            continue
    return 0

def detect_items(image):
    found_items = {}
    for key, item in ITEMS.items():
        template_path = os.path.join(TEMPLATE_DIR, item['template'])
        if not os.path.exists(template_path):
            continue
        template = cv2.imread(template_path)
        if template is None:
            continue
        res = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.85
        loc = np.where(res >= threshold)
        for pt in zip(*loc[::-1]):
            crop = image[pt[1]:pt[1]+60, pt[0]+120:pt[0]+220]  # Adjust if needed
            quantity = extract_quantity(crop)
            if key not in found_items or quantity > found_items[key]:
                found_items[key] = quantity
    return found_items

def summarize_inventory(items):
    drugs = sum(v for k, v in items.items() if k in ["ak47", "weed", "coke", "meow", "meth", "spice"])
    dirty_money = items.get("dirty_money", 0)
    clean_money = items.get("clean_money", 0)
    return drugs, dirty_money, clean_money

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")

@bot.event
async def on_message(message):
    global latest_state
    if message.channel.id != SCAN_CHANNEL_ID or not message.attachments:
        return

    attachment = message.attachments[0]
    image_path = f"temp/{attachment.filename}"
    await attachment.save(image_path)
    image = cv2.imread(image_path)
    if image is None:
        return

    detected = detect_items(image)
    drugs, dirty, clean = summarize_inventory(detected)

    if not detected:
        await message.channel.send(f"{message.author.mention} - No meaningful changes or items detected.")
        return

    log_msg = f"\ud83c\udfe6 Storage now contains:\n• Drugs: {drugs}\n• Dirty Money: £{dirty:,}\n• Clean Money: £{clean:,}"

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"{message.author.mention} - Dropoff\n{log_msg}")

    # Suspicious activity
    if any(v > 50 for v in detected.values()):
        alert_user = bot.get_user(ALERT_USER_ID)
        if alert_user:
            await message.channel.send(f"\u26a0\ufe0f {alert_user.mention} check this out!")

    latest_state = detected

bot.run(TOKEN)
