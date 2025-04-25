import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ALERT_USER_IDS = [int(uid.strip()) for uid in os.getenv("ALERT_USER_IDS", "").split(",") if uid.strip()]
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Storage tracking
storage = {
    "drugs": 0,
    "clean": 0,
    "dirty": 0
}

# Confirmation tracking
user_payments = defaultdict(int)

# Leaderboard tracking
user_data = defaultdict(lambda: {
    "drugs_taken": 0,
    "drugs_deposited": 0,
    "money_paid": 0,
    "money_taken": 0
})

panel_message = None

class ConfirmModal(discord.ui.Modal):
    def __init__(self, title, custom_id):
        super().__init__(title=title)
        self.add_item(discord.ui.TextInput(label="Amount", custom_id="amount", required=True))
        self.add_item(discord.ui.TextInput(label="For User (Optional)", custom_id="for_user", required=False))
        self.custom_id = custom_id

    async def on_submit(self, interaction: discord.Interaction):
        amount = self.children[0].value
        target_input = self.children[1].value
        try:
            amount = int(amount.replace(",", ""))
        except ValueError:
            await interaction.response.send_message("❌ Invalid amount entered.", ephemeral=True)
            return

        target = interaction.user.display_name
        if target_input:
            target = target_input.strip('<@!>')

        log_channel = bot.get_channel(LOG_CHANNEL_ID)

        if self.custom_id == "deposit_drugs":
            if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
                await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
                return

            storage["drugs"] += amount
            user_data[target]["drugs_deposited"] += amount
            await log_channel.send(f"📦 {interaction.user.mention} - Deposit Drugs for <@{target}>:\n➤ Amount: `{amount}`\n\n📠 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")
            await update_leaderboard()
            await interaction.response.send_message("✅ Logged.", ephemeral=True)

        elif self.custom_id == "take_drugs":
            if user_payments.get(target, 0) < amount * 50000:
                alert_mentions = " ".join([f"<@{uid}>" for uid in ALERT_USER_IDS])
                await interaction.response.send_message(f"❌ You must confirm payment before taking drugs.\n{alert_mentions}", ephemeral=False)
                return

            storage["drugs"] -= amount
            user_data[target]["drugs_taken"] += amount
            await log_channel.send(f"📦 {interaction.user.mention} - Take Drugs for <@{target}>:\n➤ Amount: `{amount}`\n\n📠 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")
            user_payments[target] -= amount * 50000
            await update_leaderboard()
            await interaction.response.send_message("✅ Logged.", ephemeral=True)

        elif self.custom_id == "deposit_dirty":
            storage["dirty"] += amount
            user_data[target]["money_paid"] += amount
            user_payments[target] += amount
            await log_channel.send(f"📦 {interaction.user.mention} - Deposit Dirty Money for {target}:\n➤ Amount: `{amount:,}`\n\n📠 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")
            await update_leaderboard()
            await interaction.response.send_message("✅ Logged.", ephemeral=True)

        elif self.custom_id == "deposit_clean":
            storage["clean"] += amount
            user_data[target]["money_paid"] += amount
            user_payments[target] += amount
            await log_channel.send(f"📦 {interaction.user.mention} - Deposit Clean Money for {target}:\n➤ Amount: `{amount:,}`\n\n📠 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")
            await update_leaderboard()
            await interaction.response.send_message("✅ Logged.", ephemeral=True)

        elif self.custom_id == "remove_money":
            if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
                await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
                return
            await interaction.response.send_message("Please specify: 'clean' or 'dirty'", ephemeral=True)

        elif self.custom_id == "remove_all_money":
            if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
                await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
                return
            storage["dirty"] = 0
            storage["clean"] = 0
            await log_channel.send(f"⚠️ {interaction.user.mention} removed all money from storage.")
            await update_leaderboard()
            await interaction.response.send_message("✅ All money removed.", ephemeral=True)

        elif self.custom_id == "reset_leaderboard":
            if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
                await interaction.response.send_message("❌ You don't have permission to reset leaderboard.", ephemeral=True)
                return
            user_data.clear()
            await log_channel.send(f"♻️ {interaction.user.mention} reset the leaderboard.")
            await update_leaderboard()
            await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    await post_panel()
    await update_leaderboard()

async def post_panel():
    global panel_message
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    await channel.purge(limit=1)
    view = PanelView()
    panel_message = await channel.send("📊 **Drop Panel**", view=view)

class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(discord.ui.Button(label="Deposit Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="deposit_drugs"))
        self.add_item(discord.ui.Button(label="Take Drugs", style=discord.ButtonStyle.primary, custom_id="take_drugs"))
        self.add_item(discord.ui.Button(label="Deposit Dirty Money", style=discord.ButtonStyle.success, custom_id="deposit_dirty"))
        self.add_item(discord.ui.Button(label="Deposit Clean Money", style=discord.ButtonStyle.success, custom_id="deposit_clean"))
        self.add_item(discord.ui.Button(label="Remove All Money (Admin Only)", style=discord.ButtonStyle.danger, custom_id="remove_all_money"))
        self.add_item(discord.ui.Button(label="Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id="reset_leaderboard"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    @discord.ui.button(label="💬 Interact", style=discord.ButtonStyle.primary, custom_id="interact")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # unused default button

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        await interaction.response.send_modal(ConfirmModal(title="Submit Info", custom_id=interaction.data["custom_id"]))

async def update_leaderboard():
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    await leaderboard_channel.purge(limit=1)

    sorted_users = sorted(user_data.items(), key=lambda x: x[1]["money_paid"], reverse=True)
    leaderboard = "\n".join(
        f"**{bot.get_user(int(uid)).display_name if bot.get_user(int(uid)) else f'<@{uid}>'}** — Paid £{data['money_paid']:,}, Taken £{data['money_taken']:,}, Drugs In {data['drugs_deposited']}, Out {data['drugs_taken']}"
        for uid, data in sorted_users
    )

    storage_totals = f"\n\n**Storage Totals:**\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}"

    await leaderboard_channel.send(f"📊 **Drug Leaderboard**\n\n{leaderboard}{storage_totals}")

bot.run(TOKEN)
