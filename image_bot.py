import os
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID") or 0)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID") or 0)
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID") or 0)
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID") or 0)

HIGHER_UP_ROLE_IDS = [1379910798188613763, 1300916696860856448]
BFM_ROLE_ID = 1365134227531890749

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "dirty": 0, "clean": 0}
leaderboard = {}

class ConfirmModal(Modal, title="Confirm Action"):
    def __init__(self, target_member: discord.Member):
        super().__init__()
        self.target_member = target_member
        self.amount = TextInput(label="How Many Drugs Are Being Taken?")
        self.money = TextInput(label="How Much Money Was Deposited?")
        self.drug_type = TextInput(label="Type (Clean Or Dirty)")
        self.add_item(self.amount)
        self.add_item(self.money)
        self.add_item(self.drug_type)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = int(self.amount.value.replace(",", ""))
            paid = int(self.money.value.replace(",", "").replace("£", ""))
            is_clean = "clean" in self.drug_type.value.lower()

            storage["drugs"] -= amt
            storage["clean" if is_clean else "dirty"] += paid

            key = self.target_member.display_name
            leaderboard.setdefault(key, {"drugs": 0, "paid": 0})
            leaderboard[key]["drugs"] += amt
            leaderboard[key]["paid"] += paid

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(
                f"💊 {interaction.user.mention} took `{amt}` drugs and deposited `£{paid}` "
                f"({'Clean' if is_clean else 'Dirty'}) for {self.target_member.mention}.\n"
                f"📦 Storage Now: Drugs: `{storage['drugs']}` | Clean: `£{storage['clean']}` | Dirty: `£{storage['dirty']}`"
            )
            await interaction.response.send_message("Action logged.", ephemeral=True)
            await update_leaderboard()
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

class HigherUpDropdown(Select):
    def __init__(self, members):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        super().__init__(placeholder="Take Drugs For (Higher-Ups)", options=options, custom_id="higher_up")

    async def callback(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(int(self.values[0]))
        await interaction.response.send_modal(ConfirmModal(member))

class BFMDropdown(Select):
    def __init__(self, members):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        super().__init__(placeholder="Take Drugs For (BFM Members)", options=options, custom_id="bfm")

    async def callback(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(int(self.values[0]))
        await interaction.response.send_modal(ConfirmModal(member))

class DropPanel(View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.build_dropdowns()

    def build_dropdowns(self):
        higher_ups = []
        bfm = []

        for member in self.guild.members:
            roles = [r.id for r in member.roles]
            if any(r in HIGHER_UP_ROLE_IDS for r in roles):
                higher_ups.append(member)
            elif BFM_ROLE_ID in roles:
                bfm.append(member)

        if higher_ups:
            self.add_item(HigherUpDropdown(higher_ups))
        if bfm:
            self.add_item(BFMDropdown(bfm))

        self.add_item(Button(label="📊 View Leaderboard", style=discord.ButtonStyle.primary, custom_id="view_lb"))
        self.add_item(Button(label="❌ Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset_lb"))
        self.add_item(Button(label="💊 Set Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="set_drugs"))
        self.add_item(Button(label="💵 Remove All Money (Admin Only)", style=discord.ButtonStyle.success, custom_id="reset_money"))

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    await panel_channel.purge(limit=5)
    await panel_channel.send("🧊 **Drop Panel**", view=DropPanel(panel_channel.guild))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    cid = interaction.data.get("custom_id")
    if cid == "reset_lb":
        if ADMIN_ROLE_ID in [role.id for role in interaction.user.roles]:
            leaderboard.clear()
            await interaction.response.send_message("Leaderboard reset.", ephemeral=True)
            await update_leaderboard()
        else:
            await interaction.response.send_message("No permission.", ephemeral=True)

    elif cid == "set_drugs":
        if ADMIN_ROLE_ID in [role.id for role in interaction.user.roles]:
            class SetDrugsModal(Modal, title="Set Drug Amount"):
                amount = TextInput(label="Enter new drug count")

                async def on_submit(self2, i):
                    try:
                        storage["drugs"] = int(self2.amount.value.replace(",", ""))
                        await i.response.send_message("Drugs updated.", ephemeral=True)
                    except:
                        await i.response.send_message("Invalid number.", ephemeral=True)

            await interaction.response.send_modal(SetDrugsModal())
        else:
            await interaction.response.send_message("No permission.", ephemeral=True)

    elif cid == "reset_money":
        if ADMIN_ROLE_ID in [role.id for role in interaction.user.roles]:
            storage["clean"] = 0
            storage["dirty"] = 0
            await interaction.response.send_message("All money reset.", ephemeral=True)
        else:
            await interaction.response.send_message("No permission.", ephemeral=True)

    elif cid == "view_lb":
        await update_leaderboard()
        await interaction.response.send_message("Leaderboard updated.", ephemeral=True)

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    await channel.purge(limit=5)
    if not leaderboard:
        await channel.send("🏆 **Leaderboard**\nNo data yet.")
        return

    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]["paid"], reverse=True)
    lines = []
    for name, data in sorted_lb:
        lines.append(f"**{name}** — Paid: `£{data['paid']}` | Drugs Taken: `{data['drugs']}`")
    await channel.send("🏆 **Leaderboard**\n" + "\n".join(lines))

bot.run(TOKEN)
