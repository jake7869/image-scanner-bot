
import discord
from discord.ext import commands
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import io
import re
import os

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

SCAN_CHANNEL_ID = 1300916697699717142
LOG_CHANNEL_ID = 1364353345514504304

# Track last channel-wide inventory state
last_inventory = {"drugs": 0, "dirty_money": 0, "clean_money": 0}

# Match exactly what the image shows
drug_keywords = ["AK47 Baggy", "Coke Pooch", "Weed"]
money_keywords = {
    "dirty": "Dirty Money",
    "clean": "Money"
}

def preprocess_image(image):
    image = image.convert("L")  # Grayscale
    image = image.filter(ImageFilter.MedianFilter())
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)
    return image

def extract_inventory(text):
    drugs = 0
    dirty_money = 0
    clean_money = 0

    for line in text.splitlines():
        line = line.strip()
        lower_line = line.lower()

        # Drugs
        for keyword in drug_keywords:
            if keyword.lower() in lower_line:
                match = re.search(r"(\d{1,3}(?:,\d{3})*)\s*[xX]", line)
                if match:
                    drugs += int(match.group(1).replace(",", ""))

        # Dirty money
        if money_keywords["dirty"].lower() in lower_line:
            match = re.search(r"(\d{1,3}(?:,\d{3})*)\s*[xX]", line)
            if match:
                dirty_money += int(match.group(1).replace(",", ""))

        # Clean money (labelled just as Money)
        if money_keywords["clean"].lower() in lower_line and "dirty" not in lower_line:
            match = re.search(r"(\d{1,3}(?:,\d{3})*)\s*[xX]", line)
            if match:
                clean_money += int(match.group(1).replace(",", ""))

    return {
        "drugs": drugs,
        "dirty_money": dirty_money,
        "clean_money": clean_money
    }

def format_currency(value):
    return f"£{value:,}"

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != SCAN_CHANNEL_ID or not message.attachments:
        return

    attachment = message.attachments[0]
    if not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        return

    image_bytes = await attachment.read()
    image = Image.open(io.BytesIO(image_bytes))
    image = preprocess_image(image)
    text = pytesseract.image_to_string(image)

    current = extract_inventory(text)
    previous = last_inventory.copy()
    last_inventory.update(current)

    drug_diff = current["drugs"] - previous["drugs"]
    dirty_diff = current["dirty_money"] - previous["dirty_money"]
    clean_diff = current["clean_money"] - previous["clean_money"]

    changes = []

    # Drug movement
    if drug_diff < 0:
        changes.append(f"Took out {abs(drug_diff)} drugs")
    elif drug_diff > 0:
        changes.append(f"Restocked {drug_diff} drugs")

    # Money movement
    if dirty_diff > 0:
        changes.append(f"Deposited {format_currency(dirty_diff)} dirty money")
    elif dirty_diff < 0:
        changes.append(f"Took out {format_currency(abs(dirty_diff))} dirty money")

    if clean_diff > 0:
        changes.append(f"Deposited {format_currency(clean_diff)} clean money")
    elif clean_diff < 0:
        changes.append(f"Took out {format_currency(abs(clean_diff))} clean money")

    if not changes:
        changes.append("No meaningful changes detected.")

    # Log channel
    log_channel = client.get_channel(LOG_CHANNEL_ID)

    change_summary = "\n".join(changes)
    inventory_summary = (
        f"\n\n📦 Storage now contains:\n"
        f"• Drugs: {current['drugs']}\n"
        f"• Dirty Money: {format_currency(current['dirty_money'])}\n"
        f"• Clean Money: {format_currency(current['clean_money'])}"
    )

    await log_channel.send(f"🔍 <@{message.author.id}> - {change_summary}{inventory_summary}")

client.run(os.getenv("YOUR_BOT_TOKEN"))
