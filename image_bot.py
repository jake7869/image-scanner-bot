import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ALERT_USER_IDS = [int(uid.strip()) for uid in os.getenv("ALERT_USER_IDS", "").split(",")]
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

storage = {
    "drugs": 0,
    "dirty": 0,
    "clean": 0
}

leaderboard = {}

def format_currency(val):
    return f"£{val:,}"

def update_leaderboard_display():
    leaderboard_text = "**📊 Drug Leaderboard**\n\n"
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1]['money_in'], reverse=True)

    for user_id, data in sorted_leaderboard:
        leaderboard_text += (
            f"<@{user_id}>:\n"
            f"• Drugs Taken: {data['drugs_taken']}\n"
            f"• Drugs Deposited: {data['drugs_deposited']}\n"
            f"• Money In: {format_currency(data['money_in'])}\n"
            f"• Money Out: {format_currency(data['money_out'])}\n\n"
        )

    leaderboard_text += (
        "**💾 Storage Totals:**\n"
        f"• Drugs: {storage['drugs']}\n"
        f"• Dirty: {format_currency(storage['dirty'])}\n"
        f"• Clean: {format_currency(storage['clean'])}"
    )

    return leaderboard_text

async def update_leaderboard_panel():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return
    async for msg in channel.history(limit=5):
        if msg.author == bot.user:
            await msg.edit(content=update_leaderboard_display())
            return
    await channel.send(update_leaderboard_display())

def ensure_user_entry(user_id):
    if user_id not in leaderboard:
        leaderboard[user_id] = {
            "drugs_taken": 0,
            "drugs_deposited": 0,
            "money_in": 0,
            "money_out": 0
        }

class ConfirmModal(discord.ui.Modal):
    def __init__(self, title, action_type):
        super().__init__(title=title)
        self.action_type = action_type
        self.amount = discord.ui.TextInput(label="Amount", required=True)
        self.target = discord.ui.TextInput(label="Who is this for?", required=False)
        self.add_item(self.amount)
        self.add_item(self.target)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        amount = int(self.amount.value.replace(",", "").strip())
        target = interaction.user
        if self.target.value:
            mention = self.target.value.strip().replace("<@", "").replace(">", "").replace("!", "")
            if mention.isdigit():
                fetched = await interaction.guild.fetch_member(int(mention))
                if fetched:
                    target = fetched

        ensure_user_entry(target.id)
        log_channel = bot.get_channel(LOG_CHANNEL_ID)

        if self.action_type == "deposit_dirty":
            storage["dirty"] += amount
            leaderboard[target.id]["money_in"] += amount
            await log_channel.send(f"💸 {interaction.user.mention} - Deposit Dirty Money for {target.mention}:\n➤ Amount: {format_currency(amount)}")
        elif self.action_type == "deposit_clean":
            storage["clean"] += amount
            leaderboard[target.id]["money_in"] += amount
            await log_channel.send(f"💸 {interaction.user.mention} - Deposit Clean Money for {target.mention}:\n➤ Amount: {format_currency(amount)}")
        elif self.action_type == "remove_money":
            if amount > (storage["dirty"] + storage["clean"]):
                await interaction.followup.send("❌ Not enough money in storage.")
                return
            options = f"💸 {interaction.user.mention} - Remove Money for {target.mention}:\n➤ Amount: {format_currency(amount)}"
            if storage["dirty"] >= amount:
                storage["dirty"] -= amount
            elif storage["clean"] >= amount:
                storage["clean"] -= amount
            else:
                await interaction.followup.send("❌ Could not determine clean/dirty amount.")
                return
            leaderboard[target.id]["money_out"] += amount
            await log_channel.send(options)
        elif self.action_type == "remove_all":
            leaderboard[target.id]["money_out"] += storage["dirty"] + storage["clean"]
            await log_channel.send(f"💥 {interaction.user.mention} - Remove ALL Money for {target.mention}")
            storage["dirty"] = 0
            storage["clean"] = 0
        elif self.action_type == "deposit_drugs":
            storage["drugs"] += amount
            leaderboard[target.id]["drugs_deposited"] += amount
            await log_channel.send(f"📦 {interaction.user.mention} - Deposit Drugs for {target.mention}:\n➤ Amount: {amount}")
        elif self.action_type == "take_drugs":
            if amount > storage["drugs"]:
                await interaction.followup.send("❌ Not enough drugs in storage.")
                return
            if leaderboard[target.id]["money_in"] - leaderboard[target.id]["money_out"] < amount * 5000:
                tags = " ".join(f"<@{aid}>" for aid in ALERT_USER_IDS)
                await interaction.followup.send(f"🚨 Suspicious! {interaction.user.mention} taking drugs without payment.\n{tags}")
                return
            storage["drugs"] -= amount
            leaderboard[target.id]["drugs_taken"] += amount
            await log_channel.send(f"📦 {interaction.user.mention} - Take Drugs for {target.mention}:\n➤ Amount: {amount}")

        await update_leaderboard_panel()

class DropPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def handle_action(self, interaction, action_type):
        if "admin" in action_type and ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
            return
        await interaction.response.send_modal(ConfirmModal(title="Confirm Action", action_type=action_type))

    @discord.ui.button(label="Deposit Drugs (Admin Only)", style=discord.ButtonStyle.secondary)
    async def deposit_drugs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "deposit_drugs_admin")

    @discord.ui.button(label="Take Drugs", style=discord.ButtonStyle.primary)
    async def take_drugs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "take_drugs")

    @discord.ui.button(label="Deposit Dirty Money", style=discord.ButtonStyle.success)
    async def deposit_dirty(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "deposit_dirty")

    @discord.ui.button(label="Deposit Clean Money", style=discord.ButtonStyle.success)
    async def deposit_clean(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "deposit_clean")

    @discord.ui.button(label="Remove All Money (Admin Only)", style=discord.ButtonStyle.danger)
    async def remove_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "remove_all")

    @discord.ui.button(label="Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger)
    async def reset_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
            return
        leaderboard.clear()
        storage["drugs"] = 0
        storage["dirty"] = 0
        storage["clean"] = 0
        await update_leaderboard_panel()
        await interaction.response.send_message("✅ Leaderboard and storage reset.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        async for msg in channel.history(limit=5):
            if msg.author == bot.user:
                await msg.edit(content="📊 **Drop Panel**", view=DropPanel())
                break
        else:
            await channel.send("📊 **Drop Panel**", view=DropPanel())
    await update_leaderboard_panel()

bot.run(TOKEN)
