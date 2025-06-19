import os
import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Select
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID") or 0)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID") or 0)
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID") or 0)
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID") or 0)
BFM_ROLE_ID = int(os.getenv("BFM_ROLE_ID") or 0)
HIGHER_UP_ROLE_IDS = [
    int(os.getenv("HIGHER_UP_ROLE_ID_1") or 0),
    int(os.getenv("HIGHER_UP_ROLE_ID_2") or 0)
]

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

class ConfirmModal(Modal, title="Confirm Action"):
    amount = TextInput(label="How Many Drugs Are Being Taken?")
    money = TextInput(label="How Much Money Was Deposited?")
    type = TextInput(label="Type (Clean Or Dirty)")

    def __init__(self, target_user):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            amt = int(self.amount.value.replace(',', ''))
            paid = int(self.money.value.replace(',', '').replace('�', '').replace('�', ''))
            is_clean = "clean" in self.type.value.lower()

            if amt > storage["drugs"]:
                return await interaction.response.send_message("Not enough drugs in storage.", ephemeral=True)

            storage["drugs"] -= amt
            storage["clean" if is_clean else "dirty"] += paid

            leaderboard.setdefault(self.target_user.id, {"drugs": 0, "paid": 0})
            leaderboard[self.target_user.id]["drugs"] += amt
            leaderboard[self.target_user.id]["paid"] += paid

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(
                f"🔻 {user.mention} took `{amt}` drugs and deposited `£{paid}` ({'clean' if is_clean else 'dirty'}) for {self.target_user.mention}\n"
                f"🪪 Storage: Drugs: `{storage['drugs']}`, Clean: £{storage['clean']}, Dirty: £{storage['dirty']}"
            )
            await interaction.response.send_message("Logged successfully.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

class DrugDropdown(discord.ui.Select):
    def __init__(self, label, users, custom_id):
        options = [
            discord.SelectOption(label=member.display_name, value=str(member.id))
            for member in users
        ]
        super().__init__(placeholder=f"Take Drugs For ({label})", options=options, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        selected_id = int(self.values[0])
        member = interaction.guild.get_member(selected_id)
        if not member:
            return await interaction.response.send_message("User not found.", ephemeral=True)
        await interaction.response.send_modal(ConfirmModal(target_user=member))

class DrugDropdownView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)

        higher_ups = []
        bfm_members = []
        for member in guild.members:
            role_ids = [role.id for role in member.roles]
            if any(rid in HIGHER_UP_ROLE_IDS for rid in role_ids):
                higher_ups.append(member)
            elif BFM_ROLE_ID in role_ids:
                bfm_members.append(member)

        if higher_ups:
            self.add_item(DrugDropdown("Higher-Ups", higher_ups, "select_higher"))
        if bfm_members:
            self.add_item(DrugDropdown("BFM Members", bfm_members, "select_bfm"))

    @discord.ui.button(label="View Leaderboard", style=discord.ButtonStyle.blurple, custom_id="view_lb")
    async def view_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]['paid'], reverse=True)
        embed = discord.Embed(title="Leaderboard", color=discord.Color.blurple())
        for uid, data in sorted_lb:
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"<@{uid}>"
            embed.add_field(name=name, value=f"Drugs: {data['drugs']}, Paid: £{data['paid']}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset")
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission.", ephemeral=True)
        leaderboard.clear()
        await interaction.response.send_message("Leaderboard has been reset.", ephemeral=True)

    @discord.ui.button(label="Set Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="set_drugs")
    async def set_drugs(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission.", ephemeral=True)
        class SetDrugsModal(Modal, title="Set Drug Count"):
            amount = TextInput(label="New Drug Amount")
            async def on_submit(inner_self, interaction2):
                try:
                    storage["drugs"] = int(inner_self.amount.value)
                    await interaction2.response.send_message("Drugs updated.", ephemeral=True)
                except:
                    await interaction2.response.send_message("Invalid number.", ephemeral=True)
        await interaction.response.send_modal(SetDrugsModal())

    @discord.ui.button(label="Remove All Money (Admin Only)", style=discord.ButtonStyle.success, custom_id="remove_money")
    async def remove_money(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission.", ephemeral=True)
        storage["clean"] = 0
        storage["dirty"] = 0
        await interaction.response.send_message("All money values reset.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    await panel_channel.purge(limit=5)
    await panel_channel.send(
        f"📊 **Drop Panel**\nDrugs: {storage['drugs']} | Clean: £{storage['clean']} | Dirty: £{storage['dirty']}",
        view=DrugDropdownView(panel_channel.guild)
    )

bot.run(TOKEN)
