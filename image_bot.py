import os
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput, Select
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

HIGHER_UP_ROLES = [1379910798188613763, 1300916696860856448]
BFM_ROLE_ID = 1365134227531890749

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

storage = {
    "drugs": 0,
    "dirty": 0,
    "clean": 0
}

leaderboard = {}
panel_message = None

class DrugDropModal(Modal, title="Drug Pickup Details"):
    amount = TextInput(label="How many drugs are being taken?")
    money = TextInput(label="How much money was deposited?")
    money_type = TextInput(label="Type of money (clean or dirty)")

    def __init__(self, target_user: discord.Member):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            amt = int(self.amount.value.replace(',', ''))
            paid = int(self.money.value.replace(',', '').replace('£', ''))
            is_clean = "clean" in self.money_type.value.lower()

            if storage["drugs"] < amt:
                return await interaction.response.send_message("❌ Not enough drugs in storage.", ephemeral=True)

            storage["drugs"] -= amt
            storage["clean" if is_clean else "dirty"] += paid

            name = self.target_user.display_name
            leaderboard.setdefault(name, {"paid": 0, "taken": 0})
            leaderboard[name]["paid"] += paid
            leaderboard[name]["taken"] += amt

            log = bot.get_channel(LOG_CHANNEL_ID)
            await log.send(
                f"💊 {user.mention} took `{amt}` drugs for {self.target_user.mention} and paid `£{paid}` ({'Clean' if is_clean else 'Dirty'})\n"
                f"📦 Storage: Drugs `{storage['drugs']}`, Clean `£{storage['clean']}`, Dirty `£{storage['dirty']}`"
            )

            await interaction.response.send_message("✅ Drop logged successfully.", ephemeral=True)
            await update_leaderboard()
            await update_panel()

        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

class MemberSelect(Select):
    def __init__(self, label, options, is_admin):
        super().__init__(placeholder=label, min_values=1, max_values=1, options=options, custom_id="user_select_admin" if is_admin else "user_select_bfm")
        self.is_admin = is_admin

    async def callback(self, interaction: discord.Interaction):
        member_id = int(self.values[0])
        member = interaction.guild.get_member(member_id)
        if not member:
            return await interaction.response.send_message("❌ Could not find member.", ephemeral=True)
        await interaction.response.send_modal(DrugDropModal(member))

class DropPanel(View):
    def __init__(self, guild):
        super().__init__(timeout=None)

        higherups = []
        bfm = []

        for member in guild.members:
            if any(role.id in HIGHER_UP_ROLES for role in member.roles):
                higherups.append(member)
            elif any(role.id == BFM_ROLE_ID for role in member.roles):
                bfm.append(member)

        if higherups:
            self.add_item(MemberSelect(
                "👑 Take Drugs For (Higher-Ups)",
                [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in higherups],
                is_admin=True
            ))

        if bfm:
            self.add_item(MemberSelect(
                "🧪 Take Drugs For (BFM Members)",
                [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in bfm],
                is_admin=False
            ))

        self.add_item(Button(label="🔄 Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id="reset_lb", row=2))
        self.add_item(Button(label="💉 Set Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="set_drugs", row=2))
        self.add_item(Button(label="💸 Remove All Money (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="remove_money", row=2))

    @discord.ui.button(label="🧾 View Leaderboard", style=discord.ButtonStyle.primary, custom_id="view_lb", row=2)
    async def view_lb(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard()
        await interaction.response.send_message("📊 Leaderboard updated.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot is ready as {bot.user}")
    await update_panel()
    await update_leaderboard()

async def update_panel():
    global panel_message
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if not channel:
        return
    await channel.purge(limit=5)
    panel_message = await channel.send(
        f"📦 **Drop Panel**\nDrugs: `{storage['drugs']}` | Clean: `£{storage['clean']}` | Dirty: `£{storage['dirty']}`",
        view=DropPanel(channel.guild)
    )

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return

    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]["paid"], reverse=True)
    lines = ["📊 **Leaderboard**"]
    for name, data in sorted_lb:
        lines.append(f"**{name}** → Paid: `£{data['paid']}` | Drugs Taken: `{data['taken']}`")
    await channel.purge(limit=5)
    await channel.send("\n".join(lines))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.type.name == "component":
        return

    cid = interaction.data["custom_id"]
    roles = [r.id for r in interaction.user.roles]

    if cid == "reset_lb":
        if ADMIN_ROLE_ID not in roles:
            return await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
        leaderboard.clear()
        await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)
        await update_leaderboard()

    elif cid == "set_drugs":
        if ADMIN_ROLE_ID not in roles:
            return await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)

        async def modal_callback(modal_interaction: discord.Interaction):
            try:
                amt = int(modal_input.value)
                storage["drugs"] = amt
                await modal_interaction.response.send_message(f"✅ Drugs set to {amt}.", ephemeral=True)
                await update_panel()
            except:
                await modal_interaction.response.send_message("❌ Invalid input.", ephemeral=True)

        modal_input = TextInput(label="New drugs amount")
        modal = Modal(title="Set Drugs")
        modal.add_item(modal_input)
        modal.on_submit = modal_callback
        await interaction.response.send_modal(modal)

    elif cid == "remove_money":
        if ADMIN_ROLE_ID not in roles:
            return await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
        storage["dirty"] = 0
        storage["clean"] = 0
        await interaction.response.send_message("✅ All money removed (clean & dirty).", ephemeral=True)
        await update_panel()

bot.run(TOKEN)
