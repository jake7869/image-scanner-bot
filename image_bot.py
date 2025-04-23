import discord
import os
import asyncio
import cv2
import pytesseract
import numpy as np
from discord.ext import commands
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("YOUR_BOT_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
ALERT_USER_ID = int(os.getenv("ALERT_USER_ID"))

# Preload templates
ITEM_TEMPLATES = {
    "Dirty Money": cv2.imread("templates/dirty_money.png", 0),
    "Money": cv2.imread("templates/clean_money.png", 0),
    "Coke Pouch": cv2.imread("templates/coke.png", 0),
    "Meth Pouch": cv2.imread("templates/meth.png", 0),
    "Meow Meow": cv2.imread("templates/meow.png", 0),
    "Spice Pouch": cv2.imread("templates/spice.png", 0),
    "AK47 Baggy": cv2.imread("templates/ak47.png", 0),
}

# Last known inventory state
last_inventory = {}

def extract_quantity(crop_img):
    text = pytesseract.image_to_string(crop_img, config='--psm 6').replace(",", "").replace("x", "")
    try:
        return int("".join(filter(str.isdigit, text)))
    except:
        return 0

def parse_inventory(image):
    inventory = {item: 0 for item in ITEM_TEMPLATES}
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    for name, template in ITEM_TEMPLATES.items():
        result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.78
        loc = np.where(result >= threshold)

        for pt in zip(*loc[::-1]):
            x, y = pt
            quantity_crop = gray[y:y+30, x+130:x+210]
            amount = extract_quantity(quantity_crop)
            inventory[name] += amount

    return inventory

def compare_changes(prev, curr):
    changes = {}
    for item in curr:
        changes[item] = curr[item] - prev.get(item, 0)
    return changes

def format_inventory(inv):
    total_drugs = sum(inv[item] for item in inv if "Pouch" in item or "Baggy" in item)
    dirty = inv.get("Dirty Money", 0)
    clean = inv.get("Money", 0)
    return f"📦 Storage now contains:\n• Drugs: {total_drugs}\n• Dirty Money: £{dirty:,}\n• Clean Money: £{clean:,}"

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != SCAN_CHANNEL_ID or not message.attachments:
        return

    attachment = message.attachments[0]
    await attachment.save("latest.png")

    image = cv2.imread("latest.png")
    if image is None:
        return

    current_inventory = parse_inventory(image)
    global last_inventory

    if not last_inventory:
        last_inventory = current_inventory
        return

    changes = compare_changes(last_inventory, current_inventory)
    last_inventory = current_inventory

    total_money = changes.get("Dirty Money", 0) + changes.get("Money", 0)
    total_drugs = sum(changes[item] for item in changes if "Pouch" in item or "Baggy" in item)

    uploader = message.author.mention
    for_mention = ""
    if message.mentions:
        for_mention = f"{message.mentions[0].mention} - "

    log_channel = client.get_channel(LOG_CHANNEL_ID)

    if total_drugs == -50 and total_money >= 200_000:
        await log_channel.send(
            f"✅ {for_mention}Drop by {uploader} - Valid: Took 50 drugs, deposited £{total_money:,}\n" +
            format_inventory(current_inventory)
        )
    else:
        alert = f"⚠️ {for_mention}Suspicious drop by {uploader}:\n• Drugs taken: {-total_drugs}\n• Money deposited: £{total_money:,}\n"
        if ALERT_USER_ID:
            alert += f"<@{ALERT_USER_ID}>"
        await log_channel.send(alert + "\n" + format_inventory(current_inventory))

client.run(TOKEN)
