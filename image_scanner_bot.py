
import discord
from discord.ext import commands
import pytesseract
from PIL import Image
import io
import re
import os

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

SCAN_CHANNEL_ID = 1300916697699717142
LOG_CHANNEL_ID = 1364353345514504304

# Drug keywords to look for
drug_keywords = ["AK47", "Skunk", "Weed", "Coke"]

# Track last image info for comparison
last_drug_data = {}

def extract_items(text):
    drug_total = 0
    money_total = 0

    for line in text.splitlines():
        line = line.strip()

        # Detect drugs
        for keyword in drug_keywords:
            if keyword.lower() in line.lower():
                match = re.search(r"(\d+)[xX]", line)
                if match:
                    drug_total += int(match.group(1))

        # Detect money
        if "money" in line.lower():
            match = re.search(r"(\d{1,3}(?:,\d{3})*)(?=x)", line)
            if match:
                money_total += int(match.group(1).replace(",", ""))

    return drug_total, money_total

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

    text = pytesseract.image_to_string(image)
    current_drugs, current_money = extract_items(text)

    user_id = str(message.author.id)
    last_data = last_drug_data.get(user_id, (current_drugs, current_money))

    diff_drugs = last_data[0] - current_drugs
    diff_money = current_money - last_data[1]

    last_drug_data[user_id] = (current_drugs, current_money)

    log_channel = client.get_channel(LOG_CHANNEL_ID)

    if diff_drugs == 50 and diff_money >= 200000:
        await log_channel.send(f"✅ <@{user_id}> - Valid drop: 50 drugs, £{diff_money:,} deposited.")
    else:
        await log_channel.send(
            f"❌ <@{user_id}> - Invalid drop:\nDrugs taken: {diff_drugs}\nMoney deposited: £{diff_money:,}"
        )

client.run(os.getenv("YOUR_BOT_TOKEN"))
