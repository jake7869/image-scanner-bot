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

HIGHER_UP_ROLES = [1379910798188613763, 1300916696860856448]
BFM_ROLE = 1365134227531890749

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "dirty": 0, "clean": 0}
leaderboard = {}

class DrugModal(Modal, title="Confirm Action"):
    amount = TextInput(label="How Many Drugs Are Being Taken?", required=True)
    money = TextInput(label="How Much Money Was Deposited?", required=True)
    money_type = TextInput(label="Type (Clean Or Dirty)", required=True)

    def __init__(self, target_user: discord.Member):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            amt = int(self.amount.value.replace(",", ""))
            paid = int(self.money.value.replace(",", "").replace("\u00a3", ""))
            is_clean = "clean" in self.money_type.value.lower()
            money_type = "clean" if is_clean else "dirty"

            storage["drugs"] -= amt
            storage[money_type] += paid

            leaderboard.setdefault(self.target_user.display_name, {"drugs": 0, "paid": 0})
            leaderboard[self.target_user.display_name]["drugs"] += amt
            leaderboard[self.target_user.display_name]["paid"] += paid

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(
                f"💊 {user.mention} took `{amt}` drugs and deposited £{paid} ({money_type}) for {self.target_user.mention}\n"
                f"🛋️ Storage: Drugs: `{storage['drugs']}`, Clean: £{storage['clean']}, Dirty: £{storage['dirty']}"
            )
            await interaction.response.send_message("Logged successfully.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

class UserDropdown(discord.ui.Select):
    def __init__(self, members, label):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        super().__init__(placeholder=label, min_values=1, max_values=1, options=options, custom_id=label)

    async def callback(self, interaction: discord.Interaction):
        target = interaction.guild.get_member(int(self.values[0]))
        await interaction.response.send_modal(DrugModal(target))

class ControlView(View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)

        higher_ups = [m for m in guild.members if any(r.id in HIGHER_UP_ROLES for r in m.roles)]
        bfm_only = [m for m in guild.members if any(r.id == BFM_ROLE for r in m.roles)
                    and not any(r.id in HIGHER_UP_ROLES for r in m.roles)]

        if higher_ups:
            self.add_item(UserDropdown(higher_ups, "Take Drugs For (Higher-Ups)"))
        if bfm_only:
            self.add_item(UserDropdown(bfm_only, "Take Drugs For (BFM)"))

        self.add_item(Button(label="View Leaderboard", style=discord.ButtonStyle.blurple, custom_id="view_leaderboard"))
        self.add_item(Button(label="Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset_leaderboard"))
        self.add_item(Button(label="Set Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="set_drugs"))
        self.add_item(Button(label="Remove All Money (Admin Only)", style=discord.ButtonStyle.success, custom_id="remove_money"))

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    await channel.purge(limit=5)

    summary = f"Drugs: `{storage['drugs']}` | Clean: £{storage['clean']} | Dirty: £{storage['dirty']}"
    await channel.send(content=f"📈 **Drop Panel**\n{summary}", view=ControlView(channel.guild))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type.name == "component":
        cid = interaction.data.get("custom_id")

        if cid == "reset_leaderboard":
            if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
                return await interaction.response.send_message("You do not have permission.", ephemeral=True)
            leaderboard.clear()
            await interaction.response.send_message("Leaderboard reset.", ephemeral=True)

        elif cid == "set_drugs":
            if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
                return await interaction.response.send_message("No permission.", ephemeral=True)
            storage["drugs"] = 0
            await interaction.response.send_message("Drugs reset to 0.", ephemeral=True)

        elif cid == "remove_money":
            if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
                return await interaction.response.send_message("No permission.", ephemeral=True)
            storage["dirty"] = 0
            storage["clean"] = 0
            await interaction.response.send_message("Money reset.", ephemeral=True)

        elif cid == "view_leaderboard":
            embed = discord.Embed(title="Drug Leaderboard", color=discord.Color.blue())
            for name, stats in leaderboard.items():
                embed.add_field(name=name, value=f"Drugs: {stats['drugs']}, Paid: £{stats['paid']}", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)

bot.run(TOKEN)
