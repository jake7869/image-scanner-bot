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
BFM_ROLE_ID = int(os.getenv("BFM_ROLE_ID") or 0)

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "dirty": 0, "clean": 0}
leaderboard = {}
leaderboard_message_id = None

class ConfirmView(View):
    def __init__(self, amt, paid, is_clean):
        super().__init__(timeout=60)
        self.amt = amt
        self.paid = paid
        self.is_clean = is_clean
        self.add_item(MemberDropdown(self))

class MemberDropdown(Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = []
        for member in bot.get_all_members():
            if any(role.id == BFM_ROLE_ID for role in member.roles):
                options.append(discord.SelectOption(label=member.display_name, value=str(member.id)))
        options = options[:25]
        super().__init__(placeholder="Who is this drop for?", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        target_id = int(self.values[0])
        target = interaction.guild.get_member(target_id)
        target_display = target.display_name if target else "Unknown"
        target_mention = target.mention if target else "@Unknown"

        storage["drugs"] -= self.view.amt
        storage["clean" if self.view.is_clean else "dirty"] += self.view.paid

        leaderboard.setdefault(target_mention, {"drugs": 0, "paid": 0})
        leaderboard[target_mention]["drugs"] += self.view.amt
        leaderboard[target_mention]["paid"] += self.view.paid

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        await log_channel.send(
            f"💊 {user.mention} took `{self.view.amt}` drugs and deposited `£{self.view.paid}` ({'Clean' if self.view.is_clean else 'Dirty'}) for {target_mention}\n"
            f"\n📥 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']}\n• Clean: £{storage['clean']}"
        )
        await interaction.response.send_message("Logged successfully.", ephemeral=True)
        await update_leaderboard()

class ConfirmModal(Modal, title="Confirm Action"):
    amount = TextInput(label="How many drugs are being taken?")
    money = TextInput(label="How much money was deposited?")
    type = TextInput(label="Type (clean or dirty)")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = int(self.amount.value.replace(',', ''))
            paid = int(self.money.value.replace(',', '').replace('£', ''))
            is_clean = "clean" in self.type.value.lower()
            await interaction.response.send_message("Select who it's for:", view=ConfirmView(amt, paid, is_clean), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

async def update_leaderboard():
    global leaderboard_message_id
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]['paid'], reverse=True)
    lines = [f"**📊 Drug Leaderboard**"]
    for name, data in sorted_lb:
        lines.append(f"{name}: {data['drugs']} drugs taken | £{data['paid']} paid")
    lines.append("\n**Storage Totals:**")
    lines.append(f"• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']}\n• Clean: £{storage['clean']}")
    embed = discord.Embed(description="\n".join(lines), color=discord.Color.blue())
    if leaderboard_message_id:
        try:
            msg = await leaderboard_channel.fetch_message(leaderboard_message_id)
            await msg.edit(embed=embed)
            return
        except:
            pass
    msg = await leaderboard_channel.send(embed=embed)
    leaderboard_message_id = msg.id

class ButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Take Drugs", style=discord.ButtonStyle.primary, custom_id="take"))

    @discord.ui.button(label="Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset_leaderboard")
    async def reset_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            return await interaction.response.send_message("No permission.", ephemeral=True)
        leaderboard.clear()
        await interaction.response.send_message("Leaderboard reset.", ephemeral=True)
        await update_leaderboard()

    @discord.ui.button(label="Restock Drugs (Admin Only)", style=discord.ButtonStyle.danger, custom_id="restock_drugs")
    async def restock_drugs(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("Permission denied.", ephemeral=True)

        class RestockModal(Modal, title="Restock Drugs"):
            new_amount = TextInput(label="New drug amount")

            async def on_submit(modal_self, modal_interaction: discord.Interaction):
                try:
                    storage["drugs"] = int(modal_self.new_amount.value.replace(",", ""))
                    await modal_interaction.response.send_message("Drugs restocked.", ephemeral=True)
                    await update_leaderboard()
                except:
                    await modal_interaction.response.send_message("Invalid input.", ephemeral=True)

        await interaction.response.send_modal(RestockModal())

    @discord.ui.button(label="Reset Money (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset_money")
    async def reset_money(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("Permission denied.", ephemeral=True)
        storage["dirty"] = 0
        storage["clean"] = 0
        await interaction.response.send_message("Money reset.", ephemeral=True)
        await update_leaderboard()

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    await channel.purge(limit=5)
    await channel.send("📊 **Drop Panel**", view=ButtonView())
    await update_leaderboard()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type.name == "component":
        cid = interaction.data["custom_id"]
        if cid == "take":
            await interaction.response.send_modal(ConfirmModal())

bot.run(TOKEN)
