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

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "dirty_money": 0, "clean_money": 0}
panel_message_id = None
user_stats = {}  # {user_id: {"deposited": 0, "withdrawn": 0, "drugs_in": 0, "drugs_out": 0}}

pending_payment = set()  # Users who confirmed payment before taking drugs

class DropModal(discord.ui.Modal):
    def __init__(self, title, action_name):
        super().__init__(title=title)
        self.action_name = action_name
        self.add_item(discord.ui.TextInput(label="Amount", custom_id="amount"))
        self.add_item(discord.ui.TextInput(label="For (optional)", custom_id="for_user", required=False))
        if action_name in ["Remove Money", "Remove All Money"]:
            self.add_item(discord.ui.TextInput(label="Type (clean or dirty)", custom_id="type", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        user_id = user.id
        roles = [role.id for role in user.roles]

        if self.action_name in ["Deposit Drugs", "Remove Money", "Remove All Money", "Reset Leaderboard"]:
            if ADMIN_ROLE_ID not in roles:
                await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
                return

        try:
            amount = int(self.children[0].value.replace(",", ""))
        except ValueError:
            await interaction.response.send_message("Invalid amount.", ephemeral=True)
            return

        target_input = self.children[1].value.strip()
        target_user = target_input if target_input else user.mention

        if target_input.startswith("<@") and target_input.endswith(">"):
            target_id = int(target_input.strip("<@!>"))
        else:
            target_id = user_id

        user_stats.setdefault(target_id, {"deposited": 0, "withdrawn": 0, "drugs_in": 0, "drugs_out": 0})

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        alert_mentions = " ".join(f"<@{uid}>" for uid in ALERT_USER_IDS)
        suspicious = False
        action = self.action_name

        if action == "Deposit Dirty Money":
            storage["dirty_money"] += amount
            user_stats[target_id]["deposited"] += amount
            pending_payment.add(target_id)

        elif action == "Deposit Clean Money":
            storage["clean_money"] += amount
            user_stats[target_id]["deposited"] += amount
            pending_payment.add(target_id)

        elif action == "Deposit Drugs":
            storage["drugs"] += amount
            user_stats[target_id]["drugs_in"] += amount

        elif action == "Take Drugs":
            if target_id not in pending_payment:
                await interaction.response.send_message("💸 You must deposit money before taking drugs.", ephemeral=True)
                return
            storage["drugs"] -= amount
            user_stats[target_id]["drugs_out"] += amount
            user_stats[target_id]["withdrawn"] += amount * 50000
            pending_payment.discard(target_id)
            if amount > 50:
                suspicious = True

        elif action == "Remove Money":
            type_input = self.children[2].value.strip().lower()
            if type_input == "dirty":
                storage["dirty_money"] -= amount
                action += " (Dirty)"
            elif type_input == "clean":
                storage["clean_money"] -= amount
                action += " (Clean)"
            else:
                await interaction.response.send_message("❌ Invalid type. Use 'clean' or 'dirty'.", ephemeral=True)
                return
            suspicious = True

        elif action == "Remove All Money":
            type_input = self.children[2].value.strip().lower()
            if type_input == "dirty":
                amount = storage["dirty_money"]
                storage["dirty_money"] = 0
                action += f" (ALL Dirty)"
            elif type_input == "clean":
                amount = storage["clean_money"]
                storage["clean_money"] = 0
                action += f" (ALL Clean)"
            else:
                await interaction.response.send_message("❌ Invalid type. Use 'clean' or 'dirty'.", ephemeral=True)
                return
            suspicious = True

        elif action == "Reset Leaderboard":
            user_stats.clear()
            await bot.get_channel(LEADERBOARD_CHANNEL_ID).send("🔄 Leaderboard has been reset.")
            return

        msg = f"📦 {user.mention} - **{action}** for {target_user}:\n➤ Amount: `{amount:,}`\n\n🗃️ Inventory:\n• Drugs: {storage['drugs']:,}\n• Dirty: £{storage['dirty_money']:,}\n• Clean: £{storage['clean_money']:,}"
        if suspicious:
            msg += f"\n⚠️ {alert_mentions} - Check this action."

        await log_channel.send(msg)
        await update_leaderboard()
        await interaction.response.send_message("✅ Action logged!", ephemeral=True)

class Panel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Take Drugs", style=discord.ButtonStyle.primary, custom_id="Take Drugs"))
        self.add_item(discord.ui.Button(label="Deposit Drugs (Admin Only)", style=discord.ButtonStyle.danger, custom_id="Deposit Drugs"))
        self.add_item(discord.ui.Button(label="Deposit Dirty Money", style=discord.ButtonStyle.success, custom_id="Deposit Dirty Money"))
        self.add_item(discord.ui.Button(label="Deposit Clean Money", style=discord.ButtonStyle.success, custom_id="Deposit Clean Money"))
        self.add_item(discord.ui.Button(label="Remove Money (Admin Only)", style=discord.ButtonStyle.danger, custom_id="Remove Money"))
        self.add_item(discord.ui.Button(label="Remove All Money (Admin Only)", style=discord.ButtonStyle.danger, custom_id="Remove All Money"))
        self.add_item(discord.ui.Button(label="Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="Reset Leaderboard"))

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    await post_panel()
    update_leaderboard.start()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    cid = interaction.data.get("custom_id")
    if cid:
        await interaction.response.send_modal(DropModal(title=cid, action_name=cid))

async def post_panel():
    global panel_message_id
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    view = Panel()
    async for msg in channel.history(limit=10):
        if msg.author == bot.user:
            await msg.delete()
    panel = await channel.send("📊 **Drop Panel**", view=view)
    panel_message_id = panel.id

@tasks.loop(minutes=1)
async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    embed = discord.Embed(title="📈 Leaderboard", color=discord.Color.blue())
    sorted_users = sorted(user_stats.items(), key=lambda x: x[1]["deposited"], reverse=True)
    for uid, stats in sorted_users:
        embed.add_field(
            name=f"<@{uid}>",
            value=(
                f"💰 Paid: £{stats['deposited']:,}\n"
                f"💸 Taken: £{stats['withdrawn']:,}\n"
                f"📦 Drugs In: {stats['drugs_in']:,}\n"
                f"🚨 Drugs Out: {stats['drugs_out']:,}"
            ),
            inline=False
        )
    async for msg in channel.history(limit=1):
        await msg.edit(embed=embed)
        return
    await channel.send(embed=embed)

bot.run(TOKEN)
