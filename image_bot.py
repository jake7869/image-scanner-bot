import os
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID", "0"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))
ALERT_USER_IDS = [int(uid.strip()) for uid in os.getenv("ALERT_USER_IDS", "").split(",") if uid.strip()]
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

storage = {
    "drugs": 0,
    "dirty": 0,
    "clean": 0,
}

leaderboard = {
    "users": {},
    "log": [],
}

def update_leaderboard(user_id, name, key, amount):
    if user_id not in leaderboard["users"]:
        leaderboard["users"][user_id] = {"name": name, "drugs_taken": 0, "money_paid": 0}
    leaderboard["users"][user_id][key] += amount

def format_leaderboard():
    entries = sorted(leaderboard["users"].values(), key=lambda u: u["money_paid"], reverse=True)
    leaderboard_text = "**📊 Drug Leaderboard**\n\n"
    for entry in entries:
        leaderboard_text += f"**{entry['name']}** - 💵 £{entry['money_paid']:,} | 💊 {entry['drugs_taken']} drugs taken\n"
    leaderboard_text += f"\n**📦 Storage Totals:**\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}"
    return leaderboard_text

class ConfirmModal(Modal):
    def __init__(self, title, action_type):
        super().__init__(title=title)
        self.action_type = action_type
        self.amount = TextInput(label="Amount", required=True)
        self.target = TextInput(label="Who is this for? (@name or leave blank)", required=False)
        self.add_item(self.amount)
        self.add_item(self.target)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value.replace(",", "").strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid amount.", ephemeral=True)
            return

        target = self.target.value.strip()
        if target.startswith("<@") and target.endswith(">"):
            target_user = interaction.guild.get_member(int(target.strip("<@!>")))
        else:
            target_user = interaction.user

        target_name = target_user.display_name
        uid = target_user.id

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)

        if self.action_type in ["deposit_dirty", "deposit_clean"]:
            if self.action_type == "deposit_dirty":
                storage["dirty"] += amount
                label = "Deposit Dirty Money"
            else:
                storage["clean"] += amount
                label = "Deposit Clean Money"

            update_leaderboard(uid, target_name, "money_paid", amount)
            await log_channel.send(f"📦 {interaction.user.mention} - {label} for {target_name}:\n➤ Amount: £{amount:,}\n\n🗃️ Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")

        elif self.action_type in ["deposit_drugs", "deposit_drugs_admin"]:
            storage["drugs"] += amount
            await log_channel.send(f"📦 {interaction.user.mention} - Deposit Drugs for {target_name}:\n➤ Amount: {amount}\n\n🗃️ Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")

        elif self.action_type == "take_drugs":
            if leaderboard["users"].get(uid, {}).get("money_paid", 0) < (amount * 4000):
                alert = ", ".join(f"<@{aid}>" for aid in ALERT_USER_IDS)
                await log_channel.send(f"⚠️ {alert} - Suspicious drug take attempt by {interaction.user.mention} (no payment logged).")
                await interaction.response.send_message("❌ You must deposit money before taking drugs!", ephemeral=True)
                return
            if storage["drugs"] < amount:
                await interaction.response.send_message("❌ Not enough drugs in storage.", ephemeral=True)
                return
            storage["drugs"] -= amount
            update_leaderboard(uid, target_name, "drugs_taken", amount)
            await log_channel.send(f"📦 {interaction.user.mention} - Take Drugs for {target_name}:\n➤ Amount: {amount}\n\n🗃️ Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")

        elif self.action_type == "remove_all":
            storage["dirty"] = 0
            storage["clean"] = 0
            await log_channel.send(f"❌ {interaction.user.mention} removed **ALL money** from storage.")

        await leaderboard_channel.purge(limit=5)
        await leaderboard_channel.send(format_leaderboard())
        await interaction.response.send_message("✅ Action complete!", ephemeral=True)

class PanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(Button(label="Deposit Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="deposit_drugs_admin"))
        self.add_item(Button(label="Take Drugs", style=discord.ButtonStyle.primary, custom_id="take_drugs"))
        self.add_item(Button(label="Deposit Dirty Money", style=discord.ButtonStyle.success, custom_id="deposit_dirty"))
        self.add_item(Button(label="Deposit Clean Money", style=discord.ButtonStyle.success, custom_id="deposit_clean"))
        self.add_item(Button(label="Remove All Money (Admin Only)", style=discord.ButtonStyle.danger, custom_id="remove_all"))
        self.add_item(Button(label="Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset_leaderboard"))

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        await panel_channel.purge(limit=5)
        await panel_channel.send("📊 **Drop Panel**", view=PanelView())

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or not interaction.data.get("custom_id"):
        return

    cid = interaction.data["custom_id"]
    member = interaction.user
    is_admin = any(role.id == ADMIN_ROLE_ID for role in member.roles)

    if "admin" in cid or cid in ["reset_leaderboard", "remove_all"]:
        if not is_admin:
            await interaction.response.send_message("❌ You don’t have permission to use this button.", ephemeral=True)
            return

    if cid == "reset_leaderboard":
        leaderboard["users"].clear()
        await bot.get_channel(LEADERBOARD_CHANNEL_ID).purge(limit=5)
        await bot.get_channel(LEADERBOARD_CHANNEL_ID).send("📊 Drug Leaderboard reset.")
        await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)
        return

    await interaction.response.send_modal(ConfirmModal(title="Confirm Action", action_type=cid))

bot.run(TOKEN)
