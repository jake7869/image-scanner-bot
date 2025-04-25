import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import asyncio
ADMIN_ROLE_ID = 1365134227531890749

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ALERT_USER_IDS = [int(uid.strip()) for uid in os.getenv("ALERT_USER_IDS", "").split(",") if uid.strip()]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "dirty_money": 0, "clean_money": 0}
leaderboard = {}

panel_message_id = None

class DropModal(discord.ui.Modal):
    def __init__(self, title, action_name):
        super().__init__(title=title)
        self.action_name = action_name

        self.add_item(discord.ui.TextInput(label="Amount", placeholder="e.g. 200000 or 50"))
        self.add_item(discord.ui.TextInput(label="For (optional)", placeholder="Mention or username", required=False))

    async def on_submit(self, interaction: discord.Interaction):
        amount_input = self.children[0].value
        target_user_input = self.children[1].value.strip()
        try:
            amount = int(amount_input.replace(",", ""))
        except ValueError:
            await interaction.response.send_message("Invalid amount. Please enter a number.", ephemeral=True)
            return

        user_id = interaction.user.id
        user_name = interaction.user.mention
        target_user = user_name if not target_user_input else target_user_input

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        alert_mentions = " ".join(f"<@{uid}>" for uid in ALERT_USER_IDS)

        suspicious = False
        if self.action_name == "Take Drugs":
            storage["drugs"] -= amount
            leaderboard[user_id] = leaderboard.get(user_id, {"drugs_taken": 0, "deposits": 0})
            leaderboard[user_id]["drugs_taken"] += amount
        elif self.action_name == "Deposit Drugs":
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)
                return
            storage["drugs"] += amount
        elif self.action_name == "Deposit Dirty Money":
            storage["dirty_money"] += amount
        elif self.action_name == "Deposit Clean Money":
            storage["clean_money"] += amount
        elif self.action_name == "Remove Money":
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)
                return
            storage["dirty_money"] -= amount
            suspicious = True

        log_msg = f"📦 {user_name} - **{self.action_name}** for {target_user}:\n➤ Amount: `{amount:,}`\n\n🗃️ Current Inventory:\n• Drugs: {storage['drugs']:,}\n• Dirty Money: £{storage['dirty_money']:,}\n• Clean Money: £{storage['clean_money']:,}"
        if suspicious:
            log_msg += f"\n\n⚠️ {alert_mentions} - Check this action."

        await log_channel.send(log_msg)
        await update_leaderboard()
        await update_panel()
        await interaction.response.send_message(f"{self.action_name} recorded for {target_user}.", ephemeral=True)

class Panel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Take Drugs", style=discord.ButtonStyle.primary, custom_id="take_drugs"))
        self.add_item(discord.ui.Button(label="Deposit Drugs (Admin Only)", style=discord.ButtonStyle.danger, custom_id="deposit_drugs"))
        self.add_item(discord.ui.Button(label="Deposit Dirty Money", style=discord.ButtonStyle.success, custom_id="deposit_dirty"))
        self.add_item(discord.ui.Button(label="Deposit Clean Money", style=discord.ButtonStyle.success, custom_id="deposit_clean"))
        self.add_item(discord.ui.Button(label="Remove Money (Admin Only)", style=discord.ButtonStyle.danger, custom_id="remove_money"))

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    await post_or_update_panel()
    await update_leaderboard.start()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.data.get("component_type") == 2:  # Button click
        label = interaction.data.get("custom_id")
        action_titles = {
            "take_drugs": "Take Drugs",
            "deposit_drugs": "Deposit Drugs",
            "deposit_dirty": "Deposit Dirty Money",
            "deposit_clean": "Deposit Clean Money",
            "remove_money": "Remove Money"
        }
        if label in action_titles:
            modal = DropModal(title=action_titles[label], action_name=action_titles[label])
            await interaction.response.send_modal(modal)

async def post_or_update_panel():
    global panel_message_id
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    view = Panel()

    if panel_message_id:
        try:
            msg = await channel.fetch_message(panel_message_id)
            await msg.edit(content="📊 **Drop Panel**", view=view)
            return
        except discord.NotFound:
            pass

    msg = await channel.send("📊 **Drop Panel**", view=view)
    panel_message_id = msg.id

async def update_panel():
    await post_or_update_panel()

@tasks.loop(minutes=1)
async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    sorted_users = sorted(leaderboard.items(), key=lambda x: x[1]["drugs_taken"], reverse=True)
    leaderboard_text = "**📈 Drug Leaderboard**\n\n"
    for user_id, stats in sorted_users:
        leaderboard_text += f"<@{user_id}>: {stats['drugs_taken']} drugs taken\n"
    leaderboard_text += f"\n**Inventory:**\n• Drugs: {storage['drugs']:,}\n• Dirty Money: £{storage['dirty_money']:,}\n• Clean Money: £{storage['clean_money']:,}"
    
    async for msg in channel.history(limit=1):
        await msg.edit(content=leaderboard_text)
        return
    await channel.send(leaderboard_text)

bot.run(TOKEN)
