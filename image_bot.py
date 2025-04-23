import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import cv2
import pytesseract
import numpy as np
from collections import defaultdict

# Load environment variables
load_dotenv()
TOKEN = os.getenv("YOUR_BOT_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ALERT_USER_ID = int(os.getenv("ALERT_USER_ID"))

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

ITEM_TEMPLATES = {
    "dirty_money": "templates/dirty_money.png",
    "clean_money": "templates/clean_money.png",
    "coke": "templates/coke.png",
    "meth": "templates/meth.png",
    "meow": "templates/meow.png",
    "spice": "templates/spice.png",
    "ak47": "templates/ak47.png",
    "weed": "templates/weed.png"
}

inventory_state = {}
user_tallies = defaultdict(lambda: {"in": 0, "out": 0, "drugs_in": 0, "drugs_out": 0})

def detect_quantity(slot_img):
    # Crop top right corner to extract text quantity
    h, w = slot_img.shape[:2]
    qty_region = slot_img[0:int(h * 0.25), int(w * 0.55):]
    text = pytesseract.image_to_string(qty_region, config='--psm 6').strip()
    digits = ''.join(filter(lambda x: x.isdigit() or x == ',', text)).replace(',', '')
    return int(digits) if digits.isdigit() else 0

def detect_items(image):
    found_items = {}
    gray_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    for item_name, template_path in ITEM_TEMPLATES.items():
        template = cv2.imread(template_path, 0)
        if template is None:
            continue
        res = cv2.matchTemplate(gray_img, template, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= 0.8)
        for pt in zip(*loc[::-1]):
            x, y = pt
            slot = image[y:y + template.shape[0], x:x + template.shape[1]]
            qty = detect_quantity(slot)
            if item_name in found_items:
                found_items[item_name] += qty
            else:
                found_items[item_name] = qty
    return found_items

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')

@bot.event
async def on_message(message):
    if message.channel.id != SCAN_CHANNEL_ID or not message.attachments:
        return

    latest_items = {}
    for attachment in message.attachments:
        img_bytes = await attachment.read()
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        latest_items = detect_items(img)

    global inventory_state
    diffs = {}
    for item, qty in latest_items.items():
        previous = inventory_state.get(item, 0)
        if qty != previous:
            diffs[item] = qty - previous
    inventory_state = latest_items

    if not diffs:
        return

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    user_tag = message.author.mention
    for line in message.content.splitlines():
        if "for <@" in line:
            user_tag = line.split("for ")[-1].strip()

    action_lines = []
    for item, diff in diffs.items():
        action_type = "added" if diff > 0 else "removed"
        abs_qty = abs(diff)
        action_lines.append(f"{item.replace('_', ' ').title()}: {action_type} {abs_qty}")
        if "money" in item:
            if diff > 0:
                user_tallies[user_tag]["in"] += diff
            else:
                user_tallies[user_tag]["out"] += abs(diff)
        else:
            if diff > 0:
                user_tallies[user_tag]["drugs_in"] += diff
            else:
                user_tallies[user_tag]["drugs_out"] += abs(diff)

    # Suspicious action alert
    for item, diff in diffs.items():
        if abs(diff) > 50 or (item == "dirty_money" and diff < 0 and latest_items.get("dirty_money", 0) < 100000):
            alert_user = bot.get_user(ALERT_USER_ID)
            if alert_user:
                await log_channel.send(f"⚠️ Suspicious action by {message.author.mention} → {item.replace('_', ' ').title()} {diff}\n{alert_user.mention}")

    # Update log
    inventory_log = "\n".join(action_lines)
    await log_channel.send(f"📦 {user_tag} - Dropoff:\n{inventory_log}\n\n**Storage now contains:**\n• Drugs: {sum(v for k,v in inventory_state.items() if k not in ['dirty_money', 'clean_money'])}\n• Dirty Money: £{inventory_state.get('dirty_money', 0):,}\n• Clean Money: £{inventory_state.get('clean_money', 0):,}")

bot.run(TOKEN)
