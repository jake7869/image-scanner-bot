import os
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN is missing or empty!")

PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID") or 0)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID") or 0)
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID") or 0)
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID") or 0)

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

storage = {"drugs": 0, "dirty": 0, "clean": 0}
leaderboard = {}
leaderboard_message_id = None

class ConfirmModal(Modal, title="Confirm Action"):
    amount = TextInput(label="How many drugs are being taken?")
    money = TextInput(label="How much money was deposited?")
    type = TextInput(label="Type (clean or dirty)")
    target = TextInput(label="Who is it for? (optional @mention)", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        global leaderboard_message_id
        user = interaction.user
        try:
            amt = int(self.amount.value.replace(',', ''))
            paid = int(self.money.value.replace(',', '').replace('�', '').replace('�', '').replace('L', ''))
            is_clean = "clean" in self.type.value.lower()
            target = self.target.value.strip()
            if target.startswith("<@") and target.endswith(">"):
                target_id = int(target[2:-1].replace("!", ""))
                member = interaction.guild.get_member(target_id)
                target_display = member.display_name if member else target
            else:
                target_display = user.display_name

            storage["drugs"] -= amt
            storage["clean" if is_clean else "dirty"] += paid

            leaderboard.setdefault(target_display, {"drugs": 0, "paid": 0})
            leaderboard[target_display]["drugs"] += amt
            leaderboard[target_display]["paid"] += paid

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(
                f"💊 {user.mention} - Take Drugs for {target_display}:\n"
                f"➤ Amount: `{amt}`\n➤ Paid: `£{paid}` ({'Clean' if is_clean else 'Dirty'})\n"
                f"\n📥 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']}\n• Clean: £{storage['clean']}"
            )
            await interaction.response.send_message("Logged successfully.", ephemeral=True)
            await update_leaderboard()
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

class RestockDrugsModal(Modal, title="Restock Drugs"):
    amount = TextInput(label="New drug amount")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
                return await interaction.response.send_message("Permission denied.", ephemeral=True)
            storage["drugs"] = int(self.amount.value.replace(',', ''))
            await interaction.response.send_message("Drugs restocked.", ephemeral=True)
            await update_leaderboard()
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

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
        await interaction.response.send_modal(RestockDrugsModal())

    @discord.ui.button(label="Reset Money (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset_money")
    async def reset_money(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("Permission denied.", ephemeral=True)
        storage["clean"] = 0
        storage["dirty"] = 0
        await interaction.response.send_message("Money reset.", ephemeral=True)
        await update_leaderboard()

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    await channel.purge(limit=5)
    await channel.send("📊 **Drop Panel**", view=ButtonView())
    await update_leaderboard()

async def update_leaderboard():
    global leaderboard_message_id
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]['paid'], reverse=True)
    lines = [f"**📊 Drug Leaderboard**"]
    for name, data in sorted_lb:
        lines.append(f"**{name}**: {data['drugs']} drugs taken | £{data['paid']} paid")
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

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type.name == "component":
        cid = interaction.data["custom_id"]
        if cid == "take":
            await interaction.response.send_modal(ConfirmModal())
        elif cid == "restock_drugs":
            pass
        elif cid == "reset_leaderboard":
            pass
        elif cid == "reset_money":
            pass

bot.run(TOKEN)
