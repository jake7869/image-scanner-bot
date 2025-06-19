import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID") or 0)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID") or 0)
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID") or 0)
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID") or 0)

HIGHER_UP_ROLES = [1379910798188613763, 1300916696860856448]
BFM_ROLE_ID = 1365134227531890749

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

storage = {
    "drugs": 0,
    "dirty": 0,
    "clean": 0
}

leaderboard = {}

# ---- Modal for confirming drug withdrawal ----
class ConfirmModal(Modal, title="Confirm Action"):
    def __init__(self, target_user):
        super().__init__()
        self.target_user = target_user
        self.amount = TextInput(label="How Many Drugs Are Being Taken?", required=True)
        self.money = TextInput(label="How Much Money Was Deposited?", required=True)
        self.money_type = TextInput(label="Type (Clean Or Dirty)", required=True)
        self.add_item(self.amount)
        self.add_item(self.money)
        self.add_item(self.money_type)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            amt = int(self.amount.value.replace(',', ''))
            paid = int(self.money.value.replace(',', '').replace('£', ''))
            is_clean = "clean" in self.money_type.value.lower()

            if amt > storage["drugs"]:
                await interaction.response.send_message("❌ Not enough drugs in storage.", ephemeral=True)
                return

            storage["drugs"] -= amt
            storage["clean" if is_clean else "dirty"] += paid

            leaderboard.setdefault(self.target_user.id, {"drugs": 0, "paid": 0, "name": self.target_user.display_name})
            leaderboard[self.target_user.id]["drugs"] += amt
            leaderboard[self.target_user.id]["paid"] += paid

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(
                f"🔻 {user.mention} took `{amt}` drugs and deposited `£{paid}` ({'clean' if is_clean else 'dirty'}) for {self.target_user.mention}\n"
                f"🪴 Storage: Drugs: `{storage['drugs']}`, Clean: `£{storage['clean']}`, Dirty: `£{storage['dirty']}`"
            )
            await update_panel()
            await interaction.response.send_message("✅ Logged successfully.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

# ---- Dropdown for Higher-Ups ----
class HigherUpDropdown(discord.ui.Select):
    def __init__(self, members):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        super().__init__(placeholder="Take Drugs For (Higher-Ups)", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(int(self.values[0]))
        await interaction.response.send_modal(ConfirmModal(member))

# ---- Dropdown for BFM ----
class BFMDropdown(discord.ui.Select):
    def __init__(self, members):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        super().__init__(placeholder="Take Drugs For (BFM)", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(int(self.values[0]))
        await interaction.response.send_modal(ConfirmModal(member))

# ---- Full Button View ----
class PanelView(View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        bfm_members = [m for m in guild.members if BFM_ROLE_ID in [r.id for r in m.roles] and all(r.id not in HIGHER_UP_ROLES for r in m.roles)]
        higher_ups = [m for m in guild.members if any(r.id in HIGHER_UP_ROLES for r in m.roles)]

        if higher_ups:
            self.add_item(HigherUpDropdown(higher_ups))
        if bfm_members:
            self.add_item(BFMDropdown(bfm_members))

        self.add_item(Button(label="📊 View Leaderboard", style=discord.ButtonStyle.blurple, custom_id="leaderboard"))
        self.add_item(Button(label="❌ Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset"))
        self.add_item(Button(label="🧪 Set Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="set_drugs"))
        self.add_item(Button(label="💸 Remove All Money (Admin Only)", style=discord.ButtonStyle.success, custom_id="reset_money"))

# ---- Show leaderboard ----
async def show_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]["paid"], reverse=True)
    desc = "\n".join([f"**{entry['name']}** - Drugs: `{entry['drugs']}` | Paid: `£{entry['paid']}`" for _, entry in sorted_lb]) or "No data yet."
    embed = discord.Embed(title="📊 Leaderboard", description=desc, color=0x00ffcc)
    await channel.purge(limit=5)
    await channel.send(embed=embed)

# ---- Update the panel message ----
async def update_panel():
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    await panel_channel.purge(limit=5)
    content = f"📊 **Drop Panel**\nDrugs: `{storage['drugs']}` | Clean: `£{storage['clean']}` | Dirty: `£{storage['dirty']}`"
    await panel_channel.send(content, view=PanelView(panel_channel.guild))

# ---- Bot Events ----
@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    await update_panel()
    await show_leaderboard()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type.name != "component":
        return

    cid = interaction.data["custom_id"]
    if cid == "leaderboard":
        await show_leaderboard()
        await interaction.response.send_message("📊 Leaderboard refreshed.", ephemeral=True)

    elif cid == "reset":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission.", ephemeral=True)
        leaderboard.clear()
        await show_leaderboard()
        await interaction.response.send_message("Leaderboard reset.", ephemeral=True)

    elif cid == "set_drugs":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission.", ephemeral=True)
        storage["drugs"] = 0
        await update_panel()
        await interaction.response.send_message("Drugs set to 0.", ephemeral=True)

    elif cid == "reset_money":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission.", ephemeral=True)
        storage["dirty"] = 0
        storage["clean"] = 0
        await update_panel()
        await interaction.response.send_message("Money cleared.", ephemeral=True)

bot.run(TOKEN)
