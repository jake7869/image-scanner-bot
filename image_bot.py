import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, ui
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
ALERT_USER_IDS = [int(uid.strip()) for uid in os.getenv("ALERT_USER_IDS", "").split(",") if uid.strip()]
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

storage = {
    "drugs": 0,
    "clean": 0,
    "dirty": 0
}

user_data = {}
last_deposit = {}
panel_message_id = None

class DropModal(ui.Modal, title="Drop Details"):
    action: str
    is_admin: bool
    def __init__(self, action, is_admin):
        super().__init__()
        self.action = action
        self.is_admin = is_admin
        self.add_item(ui.TextInput(label="Amount", placeholder="Enter amount", custom_id="amount"))
        self.add_item(ui.TextInput(label="For (optional @user)", required=False, custom_id="for"))
        if action == "remove_money":
            self.add_item(ui.TextInput(label="Money Type (clean/dirty)", placeholder="clean or dirty", custom_id="type"))

    async def on_submit(self, interaction: Interaction):
        amount = int(self.children[0].value.replace(",", ""))
        for_user = self.children[1].value.strip()
        target = interaction.user.mention
        if for_user.startswith("<@"):
            target = for_user
        log_channel = bot.get_channel(LOG_CHANNEL_ID)

        # Action handling
        if self.action == "deposit_drugs":
            if not self.is_admin:
                await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)
                return
            storage['drugs'] += amount
            user_data.setdefault(target, {"money_in": 0, "money_out": 0, "drugs_taken": 0})
            await log_channel.send(f"📦 {interaction.user.mention} - Deposit Drugs for {target}:
► Amount: `{amount}`\n\n📅 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")

        elif self.action == "take_drugs":
            if target not in last_deposit:
                alerts = ' '.join(f"<@{uid}>" for uid in ALERT_USER_IDS)
                await interaction.response.send_message(f"❌ {alerts} {interaction.user.mention} tried to take drugs without depositing.", ephemeral=True)
                return
            if storage['drugs'] < amount:
                await interaction.response.send_message("Not enough drugs in storage.", ephemeral=True)
                return
            storage['drugs'] -= amount
            user_data.setdefault(target, {"money_in": 0, "money_out": 0, "drugs_taken": 0})
            user_data[target]['drugs_taken'] += amount
            await log_channel.send(f"📅 {interaction.user.mention} - Take Drugs for {target}:
► Amount: `{amount}`\n\n📅 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")

        elif self.action == "deposit_dirty":
            storage['dirty'] += amount
            user_data.setdefault(target, {"money_in": 0, "money_out": 0, "drugs_taken": 0})
            user_data[target]['money_in'] += amount
            last_deposit[target] = amount
            await log_channel.send(f"📅 {interaction.user.mention} - Deposit Dirty Money for {target}:
► Amount: `£{amount:,}`\n\n📅 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")

        elif self.action == "remove_money":
            if not self.is_admin:
                await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)
                return
            money_type = self.children[2].value.lower()
            if money_type not in ['clean', 'dirty']:
                await interaction.response.send_message("Invalid type, must be 'clean' or 'dirty'", ephemeral=True)
                return
            if storage[money_type] < amount:
                await interaction.response.send_message("Not enough money in storage.", ephemeral=True)
                return
            storage[money_type] -= amount
            user_data.setdefault(target, {"money_in": 0, "money_out": 0, "drugs_taken": 0})
            user_data[target]['money_out'] += amount
            await log_channel.send(f"📅 {interaction.user.mention} - Remove {money_type.title()} Money:
► Amount: `£{amount:,}`\n\n📅 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")

        elif self.action == "remove_all_money":
            if not self.is_admin:
                await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)
                return
            storage['clean'] = 0
            storage['dirty'] = 0
            await log_channel.send(f"📅 {interaction.user.mention} - Removed ALL money from storage.\n\n📅 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")

        await update_leaderboard()
        await interaction.response.send_message("Action recorded.", ephemeral=True)

class DropPanel(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        buttons = [
            ("Deposit Drugs (Admin Only)", "deposit_drugs", discord.ButtonStyle.green, True),
            ("Take Drugs", "take_drugs", discord.ButtonStyle.primary, False),
            ("Deposit Money (Dirty)", "deposit_dirty", discord.ButtonStyle.green, False),
            ("Remove Money (Admin Only)", "remove_money", discord.ButtonStyle.red, True),
            ("Remove All Money (Admin Only)", "remove_all_money", discord.ButtonStyle.red, True),
        ]
        for label, cid, style, admin in buttons:
            self.add_item(ui.Button(label=label, custom_id=cid, style=style))

    @ui.button(label="Drop Panel", style=discord.ButtonStyle.blurple, custom_id="drop_panel", disabled=True)
    async def dummy(self, interaction: Interaction, button: ui.Button):
        pass

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    await bot.tree.sync()
    await send_panel()
    await update_leaderboard()

@bot.event
async def on_interaction(interaction: Interaction):
    if interaction.type == discord.InteractionType.component:
        cid = interaction.data['custom_id']
        is_admin = any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)
        modal = DropModal(action=cid, is_admin=is_admin)
        await interaction.response.send_modal(modal)

async def send_panel():
    global panel_message_id
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=5):
            if msg.author == bot.user and msg.components:
                panel_message_id = msg.id
                return
        view = DropPanel()
        sent = await panel_channel.send("📊 **Drop Panel**", view=view)
        panel_message_id = sent.id

async def update_leaderboard():
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not leaderboard_channel:
        return
    leaderboard_lines = ["**📈 Drug Leaderboard**\n"]
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]['money_in'], reverse=True)
    for user_id, stats in sorted_users:
        try:
            user = await bot.fetch_user(int(user_id.strip("<@!>")))
        except:
            continue
        leaderboard_lines.append(f"{user.display_name}: {stats['drugs_taken']} drugs taken")
        leaderboard_lines.append(f"{user.display_name}: Paid £{stats['money_in']:,}, Took £{stats['money_out']:,}")
    leaderboard_lines.append(f"\n**Storage Totals:**\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}")

    async for msg in leaderboard_channel.history(limit=5):
        if msg.author == bot.user:
            await msg.edit(content="\n".join(leaderboard_lines))
            return
    await leaderboard_channel.send("\n".join(leaderboard_lines))

bot.run(TOKEN)
