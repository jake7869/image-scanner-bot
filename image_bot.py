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

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "dirty": 0, "clean": 0}
leaderboard = {}

class DrugModal(Modal, title="Confirm Action"):
    def __init__(self, target_user):
        super().__init__()
        self.target_user = target_user
        self.amount = TextInput(label="How Many Drugs Are Being Taken?", required=True)
        self.money = TextInput(label="How Much Money Was Deposited?", required=True)
        self.type = TextInput(label="Type (Clean Or Dirty)", required=True)
        self.add_item(self.amount)
        self.add_item(self.money)
        self.add_item(self.type)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            amt = int(self.amount.value)
            paid = int(self.money.value.replace('"', '').replace(",", "").replace("\u00a3", ""))
            is_clean = "clean" in self.type.value.lower()

            if amt > storage['drugs']:
                await interaction.response.send_message("❌ Not enough drugs in storage.", ephemeral=True)
                return

            storage['drugs'] -= amt
            storage['clean' if is_clean else 'dirty'] += paid

            leaderboard.setdefault(str(self.target_user.id), {"name": self.target_user.display_name, "drugs": 0, "paid": 0})
            leaderboard[str(self.target_user.id)]["drugs"] += amt
            leaderboard[str(self.target_user.id)]["paid"] += paid

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(
                f"💉 {user.mention} took {amt} drugs and deposited £{paid} ({'clean' if is_clean else 'dirty'}) for {self.target_user.mention}\n"
                f"🛀 Storage: Drugs: {storage['drugs']}, Clean: £{storage['clean']}, Dirty: £{storage['dirty']}"
            )
            await interaction.response.send_message("✅ Logged successfully.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

class DrugView(View):
    def __init__(self, members, label):
        super().__init__(timeout=None)
        self.add_item(DrugSelect(members, label))

class DrugSelect(Select):
    def __init__(self, members, label):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        super().__init__(placeholder=f"Take Drugs For ({label})", options=options, custom_id=f"select_{label.lower()}")

    async def callback(self, interaction: discord.Interaction):
        target_id = int(self.values[0])
        target_user = interaction.guild.get_member(target_id)
        await interaction.response.send_modal(DrugModal(target_user))

class ControlView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="View Leaderboard", style=discord.ButtonStyle.blurple, custom_id="view_leaderboard"))
        self.add_item(Button(label="Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset_leaderboard"))
        self.add_item(Button(label="Set Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="set_drugs"))
        self.add_item(Button(label="Remove All Money (Admin Only)", style=discord.ButtonStyle.success, custom_id="reset_money"))

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    guild = bot.guilds[0]
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    await panel_channel.purge(limit=10)

    higher_ups = [m for m in guild.members if any(r.id in HIGHER_UP_ROLE_IDS for r in m.roles)]
    bfm_members = [m for m in guild.members if BFM_ROLE_ID in [r.id for r in m.roles] and not any(r.id in HIGHER_UP_ROLE_IDS for r in m.roles)]

    await panel_channel.send(
        f"📊 **Drop Panel**\nDrugs: {storage['drugs']} | Clean: £{storage['clean']} | Dirty: £{storage['dirty']}",
        view=DrugView(higher_ups, "Higher-Ups")
    )
    await panel_channel.send(view=DrugView(bfm_members, "BFM Members"))
    await panel_channel.send(view=ControlView())

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.type.name == "component":
        return
    cid = interaction.data["custom_id"]

    if cid == "reset_leaderboard":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        leaderboard.clear()
        await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)

    elif cid == "set_drugs":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        modal = Modal(title="Set Drug Count")
        amount = TextInput(label="New Drug Count", required=True)
        modal.add_item(amount)

        async def modal_submit(i):
            try:
                new_amt = int(amount.value)
                storage["drugs"] = new_amt
                await i.response.send_message(f"✅ Drug count set to {new_amt}.", ephemeral=True)
            except:
                await i.response.send_message("❌ Invalid number.", ephemeral=True)

        modal.on_submit = modal_submit
        await interaction.response.send_modal(modal)

    elif cid == "reset_money":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        storage["clean"] = 0
        storage["dirty"] = 0
        await interaction.response.send_message("✅ Money storage reset.", ephemeral=True)

    elif cid == "view_leaderboard":
        lb_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        lines = [
            f"**{data['name']}** - Drugs Taken: `{data['drugs']}` | Paid: £{data['paid']}"
            for _, data in sorted(leaderboard.items(), key=lambda x: x[1]['paid'], reverse=True)
        ] or ["No data."]
        await lb_channel.send("🏆 **Leaderboard**\n" + "\n".join(lines))

bot.run(TOKEN)

