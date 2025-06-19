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

BFM_ROLE_ID = 1365134227531890749
HIGHER_UP_ROLES = [1379910798188613763, 1300916696860856448]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "clean": 0, "dirty": 0}
leaderboard = {}

class ConfirmModal(Modal, title="Confirm Action"):
    def __init__(self, target_user: discord.Member):
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
            amt = int(self.amount.value.replace(",", ""))
            paid = int(self.money.value.replace(",", "").replace("\u00a3", ""))
            is_clean = "clean" in self.money_type.value.lower()

            if amt > storage["drugs"]:
                return await interaction.response.send_message("Not enough drugs in storage.", ephemeral=True)

            storage["drugs"] -= amt
            if is_clean:
                storage["clean"] += paid
            else:
                storage["dirty"] += paid

            name = self.target_user.display_name
            leaderboard.setdefault(name, {"drugs": 0, "paid": 0})
            leaderboard[name]["drugs"] += amt
            leaderboard[name]["paid"] += paid

            log = (
                f"🔰 {user.mention} took `{amt}` drugs and deposited \u00a3{paid} ({'clean' if is_clean else 'dirty'}) for {self.target_user.mention}\n"
                f"💼 Storage: Drugs: `{storage['drugs']}`, Clean: \u00a3{storage['clean']}, Dirty: \u00a3{storage['dirty']}"
            )
            await bot.get_channel(LOG_CHANNEL_ID).send(log)
            await update_panel()
            await interaction.response.send_message("Logged successfully.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

class UserDropdown(Select):
    def __init__(self, members, label):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        super().__init__(placeholder=label, min_values=1, max_values=1, options=options, custom_id=label)

    async def callback(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(int(self.values[0]))
        await interaction.response.send_modal(ConfirmModal(target_user=member))

class HigherUpDropdown(UserDropdown):
    def __init__(self, members):
        super().__init__(members, label="Take Drugs For (Higher-Ups)")

class BFMDropdown(UserDropdown):
    def __init__(self, members):
        super().__init__(members, label="Take Drugs For (BFM)")

class PanelView(View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        higher_ups = [m for m in guild.members if any(r.id in HIGHER_UP_ROLES for r in m.roles)]
        bfm_members = [
            m for m in guild.members
            if BFM_ROLE_ID in [r.id for r in m.roles] and not any(r.id in HIGHER_UP_ROLES for r in m.roles)
        ]
        if higher_ups:
            self.add_item(HigherUpDropdown(higher_ups))
        if bfm_members:
            self.add_item(BFMDropdown(bfm_members))
        self.add_item(Button(label="📃 View Leaderboard", style=discord.ButtonStyle.blurple, custom_id="view_leaderboard"))
        self.add_item(Button(label="❌ Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset_leaderboard"))
        self.add_item(Button(label="🔧 Set Drugs (Admin Only)", style=discord.ButtonStyle.gray, custom_id="set_drugs"))
        self.add_item(Button(label="💳 Remove All Money (Admin Only)", style=discord.ButtonStyle.success, custom_id="remove_money"))

async def update_panel():
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    async for msg in channel.history(limit=5):
        if msg.author == bot.user:
            await msg.delete()
    view = PanelView(channel.guild)
    content = f"\ud83d\udcca **Drop Panel**\nDrugs: `{storage['drugs']}` | Clean: \u00a3{storage['clean']} | Dirty: \u00a3{storage['dirty']}"
    await channel.send(content, view=view)

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    await update_panel()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data.get("component_type") == 3:  # If not a Select Menu
        if interaction.data["custom_id"] == "view_leaderboard":
            entries = [f"**{name}** - Drugs: `{data['drugs']}`, Paid: \u00a3{data['paid']}" for name, data in leaderboard.items()]
            msg = "\n".join(entries) or "No data yet."
            await interaction.response.send_message(f"**Leaderboard:**\n{msg}", ephemeral=True)

        elif interaction.data["custom_id"] == "reset_leaderboard":
            if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
                return await interaction.response.send_message("You do not have permission.", ephemeral=True)
            leaderboard.clear()
            await interaction.response.send_message("Leaderboard has been reset.", ephemeral=True)

        elif interaction.data["custom_id"] == "set_drugs":
            if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
                return await interaction.response.send_message("You do not have permission.", ephemeral=True)

            class SetDrugsModal(Modal, title="Set Drugs"):
                amount = TextInput(label="New drug amount", required=True)
                async def on_submit(self, modal_interaction):
                    try:
                        amt = int(self.amount.value)
                        storage["drugs"] = amt
                        await modal_interaction.response.send_message("Drugs updated.", ephemeral=True)
                        await update_panel()
                    except:
                        await modal_interaction.response.send_message("Invalid number.", ephemeral=True)

            await interaction.response.send_modal(SetDrugsModal())

        elif interaction.data["custom_id"] == "remove_money":
            if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
                return await interaction.response.send_message("You do not have permission.", ephemeral=True)
            storage["clean"] = 0
            storage["dirty"] = 0
            await update_panel()
            await interaction.response.send_message("Money reset to 0.", ephemeral=True)

bot.run(TOKEN)

