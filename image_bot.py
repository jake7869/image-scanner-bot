import os
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ALERT_USER_IDS = [int(uid.strip()) for uid in os.getenv("ALERT_USER_IDS", "").split(",") if uid.strip()]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

storage = {
    "dirty_money": 0,
    "clean_money": 0,
    "drugs": 0,
}

latest_panel_message = None

class DropView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Deposit Dirty Money", style=discord.ButtonStyle.green, custom_id="deposit_dirty"))
        self.add_item(Button(label="Deposit Clean Money", style=discord.ButtonStyle.green, custom_id="deposit_clean"))
        self.add_item(Button(label="Deposit Drugs", style=discord.ButtonStyle.green, custom_id="deposit_drugs"))
        self.add_item(Button(label="Take Drugs", style=discord.ButtonStyle.red, custom_id="take_drugs"))

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    post_panel.start()

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title="📊 Storage Leaderboard", color=discord.Color.blue())
        embed.add_field(name="💵 Dirty Money", value=f"£{storage['dirty_money']:,}")
        embed.add_field(name="🏦 Clean Money", value=f"£{storage['clean_money']:,}")
        embed.add_field(name="💊 Drugs", value=f"{storage['drugs']:,}")
        messages = [msg async for msg in channel.history(limit=5)]
        if messages:
            await messages[0].edit(embed=embed)
        else:
            await channel.send(embed=embed)

@tasks.loop(minutes=1)
async def post_panel():
    global latest_panel_message
    channel = bot.get_channel(SCAN_CHANNEL_ID)
    if channel:
        view = DropView()
        if latest_panel_message:
            try:
                await latest_panel_message.delete()
            except:
                pass
        latest_panel_message = await channel.send("💼 Choose an action below:", view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or "custom_id" not in interaction.data:
        return

    custom_id = interaction.data["custom_id"]

    await interaction.response.send_modal(
        discord.ui.Modal(
            title="Enter Details",
            custom_id=f"modal_{custom_id}",
            children=[
                discord.ui.TextInput(label="Amount", custom_id="amount", style=discord.TextStyle.short, required=True),
                discord.ui.TextInput(label="For (leave blank if yourself)", custom_id="for_user", style=discord.TextStyle.short, required=False),
            ]
        )
    )

@bot.event
async def on_modal_submit(interaction: discord.Interaction):
    data = interaction.data
    custom_id = data["custom_id"].replace("modal_", "")
    fields = {field["custom_id"]: field["value"] for row in data["components"] for field in row["components"]}
    amount = int(fields.get("amount", "0").replace(",", ""))
    target_user = fields.get("for_user", "").strip() or interaction.user.mention

    if custom_id == "deposit_dirty":
        storage["dirty_money"] += amount
        action = f"💰 {target_user} deposited £{amount:,} in **Dirty Money**"
    elif custom_id == "deposit_clean":
        storage["clean_money"] += amount
        action = f"🏦 {target_user} deposited £{amount:,} in **Clean Money**"
    elif custom_id == "deposit_drugs":
        storage["drugs"] += amount
        action = f"📦 {target_user} restocked with **{amount:,} drugs**"
    elif custom_id == "take_drugs":
        storage["drugs"] -= amount
        action = f"🚨 {target_user} took **{amount:,} drugs**"
        if amount > 50:
            action += f"\n⚠️ Possible suspicious activity."
            for uid in ALERT_USER_IDS:
                action += f" <@{uid}>"

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(action)

    await update_leaderboard()
    await interaction.followup.send("✅ Action logged successfully!", ephemeral=True)

bot.run(TOKEN)
