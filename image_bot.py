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
BFM_ROLE_ID = int(os.getenv("BFM_ROLE_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "clean": 0, "dirty": 0}
leaderboard = {}
panel_message = None
leaderboard_message = None

class TakeDrugsModal(Modal, title="Confirm Action"):
    amount = TextInput(label="How Many Drugs Are Being Taken?", placeholder="e.g. 50", required=True)
    money = TextInput(label="How Much Money Was Deposited?", placeholder="e.g. 200000", required=True)
    mtype = TextInput(label="Type (Clean Or Dirty)", placeholder="clean or dirty", required=True)

    def __init__(self, target_id: int):
        super().__init__()
        self.target_id = target_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            money = int(self.money.value)
            is_clean = "clean" in self.mtype.value.lower()

            if storage["drugs"] < amount:
                await interaction.response.send_message("❌ Not enough drugs in storage.", ephemeral=True)
                return

            storage["drugs"] -= amount
            if is_clean:
                storage["clean"] += money
            else:
                storage["dirty"] += money

            target_user = interaction.guild.get_member(self.target_id)
            display_name = target_user.display_name if target_user else "Unknown"

            if display_name not in leaderboard:
                leaderboard[display_name] = {"drugs": 0, "paid": 0}
            leaderboard[display_name]["drugs"] += amount
            leaderboard[display_name]["paid"] += money

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(
                f"💉 {interaction.user.mention} took `{amount}` drugs and deposited `£{money}` ({'clean' if is_clean else 'dirty'}) for {target_user.mention}"
                f"\n🧾 **Storage**: Drugs: `{storage['drugs']}`, Clean: `£{storage['clean']}`, Dirty: `£{storage['dirty']}`"
            )

            await update_panel()
            await update_leaderboard()
            await interaction.response.send_message("✅ Transaction logged.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

class TakeDrugsView(View):
    def __init__(self, higherups, bfm):
        super().__init__(timeout=None)
        self.add_item(HigherUpDropdown(higherups))
        self.add_item(BFMDropdown(bfm))
        self.add_item(ViewLeaderboard())
        self.add_item(ResetLeaderboard())
        self.add_item(SetDrugs())
        self.add_item(RemoveAllMoney())

class HigherUpDropdown(Select):
    def __init__(self, members):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members[:25]]
        super().__init__(placeholder="Take Drugs For (Higher-Ups)", options=options, custom_id="higher_up")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TakeDrugsModal(target_id=int(self.values[0])))

class BFMDropdown(Select):
    def __init__(self, members):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members[:25]]
        super().__init__(placeholder="Take Drugs For (BFM)", options=options, custom_id="bfm")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TakeDrugsModal(target_id=int(self.values[0])))

class ViewLeaderboard(Button):
    def __init__(self):
        super().__init__(label="View Leaderboard", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=generate_leaderboard(), ephemeral=True)

class ResetLeaderboard(Button):
    def __init__(self):
        super().__init__(label="Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
            return
        leaderboard.clear()
        await update_leaderboard()
        await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)

class SetDrugs(Button):
    def __init__(self):
        super().__init__(label="Set Drugs (Admin Only)", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
            return
        modal = Modal(title="Set Drugs")
        modal.add_item(TextInput(label="New Drug Count", placeholder="e.g. 300", required=True))

        async def modal_submit(interact):
            try:
                storage["drugs"] = int(modal.children[0].value)
                await update_panel()
                await interact.response.send_message("✅ Drug count updated.", ephemeral=True)
            except:
                await interact.response.send_message("❌ Invalid number.", ephemeral=True)

        modal.on_submit = modal_submit
        await interaction.response.send_modal(modal)

class RemoveAllMoney(Button):
    def __init__(self):
        super().__init__(label="Remove All Money (Admin Only)", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
            return
        storage["clean"] = 0
        storage["dirty"] = 0
        await update_panel()
        await interaction.response.send_message("✅ Money storage cleared.", ephemeral=True)

@bot.event
async def on_ready():
    global panel_message, leaderboard_message
    print(f"Logged in as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)

    await panel_channel.purge(limit=5)
    await leaderboard_channel.purge(limit=5)

    members = panel_channel.guild.members
    bfm_members = [m for m in members if BFM_ROLE_ID in [r.id for r in m.roles] and ADMIN_ROLE_ID not in [r.id for r in m.roles]]
    higher_ups = [m for m in members if ADMIN_ROLE_ID in [r.id for r in m.roles]]

    panel_message = await panel_channel.send(
        f"📊 **Drop Panel**\nDrugs: `{storage['drugs']}` | Clean: `£{storage['clean']}` | Dirty: `£{storage['dirty']}`",
        view=TakeDrugsView(higher_ups, bfm_members)
    )

    leaderboard_message = await leaderboard_channel.send(embed=generate_leaderboard())

async def update_panel():
    if panel_message:
        await panel_message.edit(
            content=f"📊 **Drop Panel**\nDrugs: `{storage['drugs']}` | Clean: `£{storage['clean']}` | Dirty: `£{storage['dirty']}`"
        )

async def update_leaderboard():
    if leaderboard_message:
        await leaderboard_message.edit(embed=generate_leaderboard())

def generate_leaderboard():
    sorted_users = sorted(leaderboard.items(), key=lambda x: x[1]['paid'], reverse=True)
    description = ""
    for name, data in sorted_users:
        description += f"**{name}** - 💊 {data['drugs']} drugs | £{data['paid']} deposited\n"
    if not description:
        description = "No activity yet."
    return discord.Embed(title="🏆 Drug Leaderboard", description=description, color=0x00ff00)

bot.run(TOKEN)
