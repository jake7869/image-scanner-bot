import discord
import os
import pytesseract
import cv2
import numpy as np
from discord.ext import commands
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
ALERT_USER_ID = int(os.getenv("ALERT_USER_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

last_inventory = {}

def extract_items_from_image(image_path):
    img = cv2.imread(image_path)
    h, w = img.shape[:2]

    slots = []
    slot_width = 250
    slot_height = 100
    cols = w // slot_width
    rows = h // slot_height

    for row in range(rows):
        for col in range(cols):
            x = col * slot_width
            y = row * slot_height
            slot_img = img[y:y+slot_height, x:x+slot_width]
            gray = cv2.cvtColor(slot_img, cv2.COLOR_BGR2GRAY)
            text = pytesseract.image_to_string(gray, config='--psm 6').strip()
            if text:
                slots.append(text)

    items = {}
    for entry in slots:
        parts = entry.split('x')
        if len(parts) == 2:
            try:
                name = parts[1].strip().lower()
                qty = int(parts[0].replace(',', '').strip())
                items[name] = items.get(name, 0) + qty
            except:
                continue
    return items

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    global last_inventory
    if message.channel.id != SCAN_CHANNEL_ID or not message.attachments:
        return

    for attachment in message.attachments:
        if any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
            await attachment.save("current.png")
            current_items = extract_items_from_image("current.png")

            changes = {}
            for item, qty in current_items.items():
                old_qty = last_inventory.get(item, 0)
                diff = qty - old_qty
                if diff != 0:
                    changes[item] = diff

            last_inventory = current_items

            if not changes:
                return

            log_lines = [f"📦 {message.author.mention} – Inventory Change Detected:"]
            suspicious = False
            total_money_added = 0
            total_drugs_taken = 0

            for item, diff in changes.items():
                if diff > 0:
                    log_lines.append(f"• Added {diff}x {item.title()}")
                else:
                    log_lines.append(f"• Removed {abs(diff)}x {item.title()}")
                if "money" in item:
                    total_money_added += diff
                if "pooch" in item or "baggy" in item or "weed" in item:
                    total_drugs_taken += abs(diff) if diff < 0 else 0

            if total_drugs_taken >= 50 and total_money_added < 200000:
                log_lines.append(f"⚠️ <@{ALERT_USER_ID}> - Possible theft! {total_drugs_taken}x drugs removed but only £{total_money_added:,} added.")
                suspicious = True

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send("\n".join(log_lines))

bot.run(TOKEN)
