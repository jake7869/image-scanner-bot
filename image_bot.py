import os
import discord
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID") or 0)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID") or 0)
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID") or 0)
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID") or 0)

# Role IDs
HIGHER_UP_ROLE_IDS = [1379910798188613763, 1300916696860856448]
BFM_ROLE_ID = 1365134227531890749

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "dirty": 0, "clean": 0}
leaderboard = {}

class ConfirmModal(Modal, title="Confirm Action"):
    amount = TextInput(label="How Many Drugs Are Being Taken?")
    money = TextInput(label="How Much Money Was Deposited?")
    money_type = TextInput(label="Type (Clean Or Dirty)")

    def __init__(self, requester: discord.Member, target: discord.Member):
        super().__init__()
        self.requester = requester
        self.target = target

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = int(self.amount.value.replace(',', ''))
            paid = int(self.money.value.replace(',', '').replace('£', ''))
            is_clean = "clean" in self.money_type.value.lower()

            if storage["drugs"] < amt:
                await interaction.response.send_message("❌ Not enough drugs in storage.", ephemeral=True)
                return

            storage["drugs"] -= amt
            storage["clean" if is_clean else "dirty"] += paid

            name = self.target.display_name
            leaderboard.setdefault(name, {"drugs": 0, "paid": 0})
            leaderboard[name]["drugs"] += amt
            leaderboard[name]["paid"] += paid

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(
                f"💊 {self.requester.mention} took `{amt}` drugs and deposited `£{paid}` "
                f"({'Clean' if is_clean else 'Dirty'}) for {self.target.mention}\n\n"
                f"📦 **Storage**:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']}\n• Clean: £{storage['clean']}"
            )
            await interaction.response.send_message("✅ Logged.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

class TakeDrugsDropdown(discord.ui.Select):
    def __init__(self, members, label: str, custom_id: str):
        options = [
            discord.SelectOption(label=member.display_name, value=str(member.id))
            for member in members
        ]
        super().__init__(placeholder=label, min_values=1, max_values=1, options=options, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        target = interaction.guild.get_member(int(self.values[0]))
        await interaction.response.send_modal(ConfirmModal(requester=interaction.user, target=target))

class ButtonPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def refresh(self, guild):
        self.clear_items()

        # Filter roles
        higher_ups = []
        bfm_members = []
        for member in guild.members:
            role_ids = [role.id for role in member.roles]
            if any(rid in role_ids for rid in HIGHER_UP_ROLE_IDS):
                higher_ups.append(member)
            elif BFM_ROLE_ID in role_ids:
                bfm_members.append(member)

        # Dropdowns
        self.add_item(TakeDrugsDropdown(higher_ups, "👑 Take Drugs For (Higher-Ups)", "higherup"))
        self.add_item(TakeDrugsDropdown(bfm_members, "💊 Take Drugs For (BFM Members)", "bfm"))

        # View leaderboard button
        self.add_item(Button(label="📊 View Leaderboard", style=discord.ButtonStyle.primary, custom_id="leader"))

        # Admin Buttons
        self.add_item(Button(label="🔴 Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id="reset"))
        self.add_item(Button(label="🧪 Set Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="setdrugs"))
        self.add_item(Button(label="💸 Remove All Money (Admin Only)", style=discord.ButtonStyle.success, custom_id="clearmoney"))

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    await panel_channel.purge(limit=5)

    view = ButtonPanel()
    await view.refresh(panel_channel.guild)
    await panel_channel.send("📦 **Drop Panel**", view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    cid = interaction.data.get("custom_id")

    if cid == "leader":
        lb_text = "**📊 Drug Leaderboard**\n\n"
        for user, stats in sorted(leaderboard.items(), key=lambda x: x[1]["paid"], reverse=True):
            lb_text += f"**{user}**: {stats['drugs']} drugs taken | £{stats['paid']} paid\n"
        lb_text += f"\n📦 **Storage**:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']}\n• Clean: £{storage['clean']}"
        await interaction.response.send_message(lb_text, ephemeral=True)

    elif cid == "reset":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        leaderboard.clear()
        await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)

    elif cid == "setdrugs":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("🚫 No permission.", ephemeral=True)

        class DrugSetModal(Modal, title="Set Drug Count"):
            amount = TextInput(label="Set drug count:")

            async def on_submit(self, i):
                try:
                    amt = int(self.amount.value.replace(',', ''))
                    storage["drugs"] = amt
                    await i.response.send_message(f"✅ Drugs set to {amt}", ephemeral=True)
                except:
                    await i.response.send_message("❌ Invalid number.", ephemeral=True)

        await interaction.response.send_modal(DrugSetModal())

    elif cid == "clearmoney":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        storage["clean"] = 0
        storage["dirty"] = 0
        await interaction.response.send_message("✅ Money totals reset.", ephemeral=True)

bot.run(TOKEN)
