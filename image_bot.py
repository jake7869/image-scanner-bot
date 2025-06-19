import os
import discord
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))
HIGHER_UP_ROLE_IDS = [1379910798188613763, 1300916696860856448]
BFM_ROLE_ID = 1365134227531890749

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "dirty": 0, "clean": 0}
leaderboard = {}

class ConfirmModal(Modal, title="Confirm Action"):
    def __init__(self, target_user: discord.Member):
        super().__init__()
        self.target_user = target_user
        self.amount = TextInput(label="How Many Drugs Are Being Taken?", required=True)
        self.money = TextInput(label="How Much Money Was Deposited?", required=True)
        self.type = TextInput(label="Type (Clean Or Dirty)", required=True)
        self.add_item(self.amount)
        self.add_item(self.money)
        self.add_item(self.type)

    async def on_submit(self, interaction: discord.Interaction):
        amt = int(self.amount.value)
        paid = int(self.money.value.replace("\u00a3", ""))
        is_clean = "clean" in self.type.value.lower()

        if storage["drugs"] < amt:
            await interaction.response.send_message("❌ Not enough drugs in storage.", ephemeral=True)
            return

        storage["drugs"] -= amt
        storage["clean" if is_clean else "dirty"] += paid

        name = self.target_user.display_name
        leaderboard.setdefault(name, {"drugs": 0, "paid": 0})
        leaderboard[name]["drugs"] += amt
        leaderboard[name]["paid"] += paid

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        await log_channel.send(
            f"💊 {interaction.user.mention} took `{amt}` drugs and deposited £{paid} ({'clean' if is_clean else 'dirty'}) for {self.target_user.mention}\n"
            f"👜 Storage: Drugs: `{storage['drugs']}`, Clean: £{storage['clean']}, Dirty: £{storage['dirty']}"
        )

        await interaction.response.send_message("✅ Action logged successfully.", ephemeral=True)

class DualDropdownView(View):
    def __init__(self, members):
        super().__init__(timeout=None)
        self.members = members
        self.build_dropdowns()

    def build_dropdowns(self):
        higher_ups = [m for m in self.members if any(role.id in HIGHER_UP_ROLE_IDS for role in m.roles)]
        bfm_members = [m for m in self.members if BFM_ROLE_ID in [r.id for r in m.roles] and not any(role.id in HIGHER_UP_ROLE_IDS for role in m.roles)]

        if higher_ups:
            self.add_item(MemberDropdown(higher_ups, label="Take Drugs For (Higher-Ups)"))
        if bfm_members:
            self.add_item(MemberDropdown(bfm_members, label="Take Drugs For (BFM)"))

        self.add_item(Button(label="📈 View Leaderboard", style=discord.ButtonStyle.blurple, custom_id="view_leaderboard"))
        self.add_item(Button(label="❌ Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset_leaderboard"))
        self.add_item(Button(label="🔧 Set Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="set_drugs"))
        self.add_item(Button(label="💳 Remove All Money (Admin Only)", style=discord.ButtonStyle.success, custom_id="remove_money"))

class MemberDropdown(Select):
    def __init__(self, members, label):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        super().__init__(placeholder=label, min_values=1, max_values=1, options=options, custom_id=label)

    async def callback(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(int(self.values[0]))
        await interaction.response.send_modal(ConfirmModal(target_user=member))

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    await panel_channel.purge(limit=5)
    view = DualDropdownView(panel_channel.guild.members)
    await panel_channel.send(f"📊 **Drop Panel**\nDrugs: `{storage['drugs']}` | Clean: £{storage['clean']} | Dirty: £{storage['dirty']}", view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data:
        return
    cid = interaction.data.get("custom_id")
    if cid == "view_leaderboard":
        sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]['paid'], reverse=True)
        msg = "\n".join([f"**{name}** - Drugs: `{data['drugs']}`, Paid: £{data['paid']}" for name, data in sorted_lb]) or "No entries yet."
        await interaction.response.send_message(f"🏆 **Leaderboard:**\n{msg}", ephemeral=True)

    elif cid == "reset_leaderboard":
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
            return
        leaderboard.clear()
        await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)

    elif cid == "set_drugs":
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
            return

        class SetDrugsModal(Modal, title="Set Drugs Amount"):
            amount = TextInput(label="New Drugs Amount", required=True)

            async def on_submit(modal_self, modal_inter):
                storage["drugs"] = int(modal_self.amount.value)
                await modal_inter.response.send_message("✅ Drugs storage updated.", ephemeral=True)

        await interaction.response.send_modal(SetDrugsModal())

    elif cid == "remove_money":
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
            return
        storage["dirty"] = 0
        storage["clean"] = 0
        await interaction.response.send_message("✅ All money values reset.", ephemeral=True)

bot.run(TOKEN)
