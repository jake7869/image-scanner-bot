import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ALERT_USER_IDS = [int(uid.strip()) for uid in os.getenv("ALERT_USER_IDS", "").split(",") if uid.strip()]
ADMIN_ROLE_ID = 1365134227531890749

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "dirty_money": 0, "clean_money": 0}
leaderboard = {}
panel_message_id = None

class DropModal(discord.ui.Modal):
    def __init__(self, title, action_name):
        super().__init__(title=title)
        self.action_name = action_name
        self.add_item(discord.ui.TextInput(label="Amount", custom_id="amount", placeholder="e.g. 200000", required=action_name != "Remove All Money"))
        self.add_item(discord.ui.TextInput(label="For (optional)", custom_id="for_user", placeholder="Mention or username", required=False))
        if action_name in ["Remove Money", "Remove All Money"]:
            self.add_item(discord.ui.TextInput(label="Type (clean or dirty)", custom_id="type", placeholder="clean / dirty"))

    async def on_submit(self, interaction: discord.Interaction):
        if self.action_name in ["Deposit Drugs", "Remove Money", "Remove All Money"]:
            if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
                await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
                return

        amount = 0
        if self.action_name != "Remove All Money":
            try:
                amount = int(self.children[0].value.replace(",", ""))
            except ValueError:
                await interaction.response.send_message("Invalid amount.", ephemeral=True)
                return

        target_user = self.children[1].value.strip() or interaction.user.mention
        action = self.action_name
        user_id = interaction.user.id
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        alert_mentions = " ".join(f"<@{uid}>" for uid in ALERT_USER_IDS)
        suspicious = False

        # Logic
        if action == "Take Drugs":
            storage["drugs"] -= amount
            leaderboard[user_id] = leaderboard.get(user_id, {"drugs_taken": 0, "deposits": 0})
            leaderboard[user_id]["drugs_taken"] += amount

        elif action == "Deposit Drugs":
            storage["drugs"] += amount

        elif action == "Deposit Dirty Money":
            storage["dirty_money"] += amount

        elif action == "Deposit Clean Money":
            storage["clean_money"] += amount

        elif action in ["Remove Money", "Remove All Money"]:
            money_type = self.children[2].value.strip().lower()
            if money_type not in ["clean", "dirty"]:
                await interaction.response.send_message("❌ Type must be 'clean' or 'dirty'.", ephemeral=True)
                return

            if action == "Remove Money":
                if money_type == "clean":
                    storage["clean_money"] -= amount
                    action += " (Clean)"
                else:
                    storage["dirty_money"] -= amount
                    action += " (Dirty)"
            else:  # Remove All Money
                if money_type == "clean":
                    amount = storage["clean_money"]
                    storage["clean_money"] = 0
                    action += f" - Removed ALL Clean (£{amount:,})"
                else:
                    amount = storage["dirty_money"]
                    storage["dirty_money"] = 0
                    action += f" - Removed ALL Dirty (£{amount:,})"
            suspicious = True

        # Log message
        log_msg = f"📦 {interaction.user.mention} - **{action}** for {target_user}:\n➤ Amount: `{amount:,}`\n\n🗃️ Storage:\n• Drugs: {storage['drugs']:,}\n• Dirty: £{storage['dirty_money']:,}\n• Clean: £{storage['clean_money']:,}"
        if suspicious:
            log_msg += f"\n⚠️ {alert_mentions} - Check this action."

        await log_channel.send(log_msg)
        await update_panel()
        await update_leaderboard()
        await interaction.response.send_message("✅ Action logged!", ephemeral=True)

class Panel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Take Drugs", style=discord.ButtonStyle.primary, custom_id="take_drugs"))
        self.add_item(discord.ui.Button(label="Deposit Drugs (Admin Only)", style=discord.ButtonStyle.danger, custom_id="deposit_drugs"))
        self.add_item(discord.ui.Button(label="Deposit Dirty Money", style=discord.ButtonStyle.success, custom_id="deposit_dirty"))
        self.add_item(discord.ui.Button(label="Deposit Clean Money", style=discord.ButtonStyle.success, custom_id="deposit_clean"))
        self.add_item(discord.ui.Button(label="Remove Money (Admin Only)", style=discord.ButtonStyle.danger, custom_id="remove_money"))
        self.add_item(discord.ui.Button(label="Remove All Money (Admin Only)", style=discord.ButtonStyle.danger, custom_id="remove_all"))

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    await update_panel()
    update_leaderboard.start()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        actions = {
            "take_drugs": "Take Drugs",
            "deposit_drugs": "Deposit Drugs",
            "deposit_dirty": "Deposit Dirty Money",
            "deposit_clean": "Deposit Clean Money",
            "remove_money": "Remove Money",
            "remove_all": "Remove All Money"
        }
        if custom_id in actions:
            await interaction.response.send_modal(DropModal(title=actions[custom_id], action_name=actions[custom_id]))

async def update_panel():
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

@tasks.loop(minutes=1)
async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    sorted_stats = sorted(leaderboard.items(), key=lambda x: x[1]["drugs_taken"], reverse=True)
    board = "**📈 Drug Leaderboard**\n\n"
    for uid, stats in sorted_stats:
        board += f"<@{uid}>: {stats['drugs_taken']} drugs taken\n"
    board += f"\n**Storage Totals:**\n• Drugs: {storage['drugs']:,}\n• Dirty: £{storage['dirty_money']:,}\n• Clean: £{storage['clean_money']:,}"

    async for msg in channel.history(limit=1):
        await msg.edit(content=board)
        return
    await channel.send(board)

bot.run(TOKEN)
