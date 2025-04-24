import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ALERT_USER_IDS = [int(uid.strip()) for uid in os.getenv("ALERT_USER_IDS", "").split(",")]

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

user_stats = defaultdict(lambda: {"drugs_taken": 0, "money_deposited": 0})
storage = {"clean": 0, "dirty": 0, "drugs": 0}
leaderboard_message = None

class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Take Drugs", style=discord.ButtonStyle.primary, custom_id="take_drugs")
    async def take_drugs(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        user_stats[uid]["drugs_taken"] += 50
        storage["drugs"] -= 50
        await interaction.response.send_message("💊 You took 50 drugs.", ephemeral=True)
        await update_leaderboard()
        await check_balance(interaction.user, 50)

    @discord.ui.button(label="Deposit Money (Dirty)", style=discord.ButtonStyle.secondary, custom_id="deposit_dirty")
    async def deposit_dirty(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        user_stats[uid]["money_deposited"] += 200000
        storage["dirty"] += 200000
        await interaction.response.send_message("💵 You deposited £200,000 dirty money.", ephemeral=True)
        await update_leaderboard()

    @discord.ui.button(label="Deposit Money (Clean)", style=discord.ButtonStyle.secondary, custom_id="deposit_clean")
    async def deposit_clean(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        user_stats[uid]["money_deposited"] += 200000
        storage["clean"] += 200000
        await interaction.response.send_message("💷 You deposited £200,000 clean money.", ephemeral=True)
        await update_leaderboard()

    @discord.ui.button(label="Restock Drugs", style=discord.ButtonStyle.success, custom_id="restock_drugs")
    async def restock_drugs(self, interaction: discord.Interaction, button: discord.ui.Button):
        storage["drugs"] += 50
        await interaction.response.send_message("📦 You restocked 50 drugs.", ephemeral=True)
        await update_leaderboard()

    @discord.ui.button(label="Withdraw Money", style=discord.ButtonStyle.danger, custom_id="withdraw_money")
    async def withdraw_money(self, interaction: discord.Interaction, button: discord.ui.Button):
        storage["dirty"] -= 200000
        await interaction.response.send_message("💸 You withdrew £200,000 dirty money.", ephemeral=True)
        await update_leaderboard()

async def update_leaderboard():
    global leaderboard_message
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return

    leaderboard = "**📊 Leaderboard**\n"
    for uid, stats in user_stats.items():
        user = await bot.fetch_user(int(uid))
        leaderboard += f"**{user.name}** — 💊 {stats['drugs_taken']} drugs, 💷 £{stats['money_deposited']:,}\n"

    summary = (
        f"\n**🏦 Storage**\n"
        f"• Clean Money: £{storage['clean']:,}\n"
        f"• Dirty Money: £{storage['dirty']:,}\n"
        f"• Drugs: {storage['drugs']}\n"
    )

    content = leaderboard + summary

    if leaderboard_message and leaderboard_message.channel == channel:
        await leaderboard_message.edit(content=content)
    else:
        messages = [msg async for msg in channel.history(limit=5)]
        for msg in messages:
            if msg.author == bot.user:
                leaderboard_message = msg
                await msg.edit(content=content)
                return
        leaderboard_message = await channel.send(content)

async def check_balance(user, drugs_taken):
    expected_payment = drugs_taken * 4000
    actual_payment = user_stats[str(user.id)]["money_deposited"]
    if actual_payment < expected_payment:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            alert_mentions = " ".join(f"<@{uid}>" for uid in ALERT_USER_IDS)
            await log_channel.send(f"⚠️ {user.mention} may not have paid enough for drugs. {alert_mentions}")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        await panel_channel.purge(limit=5)
        await panel_channel.send("🔘 Drug Tracker Panel", view=PanelView())
    await update_leaderboard()

bot.run(TOKEN)
