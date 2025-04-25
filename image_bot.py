import os
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

storage = {
    "drugs": 0,
    "dirty": 0,
    "clean": 0
}

leaderboard = {}

class TakeDrugsModal(Modal, title="Take Drugs"):
    amount = TextInput(label="How many drugs are being taken?")
    money = TextInput(label="How much was paid? (number only)")
    payment_type = TextInput(label="Type of money (clean or dirty)")
    for_who = TextInput(label="Who is this for? (@mention or leave blank)", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            amt = int(self.amount.value.replace(",", ""))
            paid = int(self.money.value.replace(",", "").replace("£", ""))
            money_type = "clean" if "clean" in self.payment_type.value.lower() else "dirty"
            target = self.for_who.value.strip()

            # Who it's for
            if target.startswith("<@") and target.endswith(">"):
                target_id = int(target[2:-1].replace("!", ""))
                member = interaction.guild.get_member(target_id)
                target_display = member.display_name if member else user.display_name
            else:
                target_display = user.display_name

            if amt <= 0 or paid <= 0:
                return await interaction.response.send_message("Amount and payment must be more than 0.", ephemeral=True)

            if paid < amt * 10000:
                alert = f"⚠️ Suspicious drop detected by {user.mention} (only £{paid:,} for {amt} drugs)"
                await bot.get_channel(LOG_CHANNEL_ID).send(alert)

            storage["drugs"] -= amt
            storage[money_type] += paid

            leaderboard.setdefault(target_display, {"drugs": 0, "paid": 0})
            leaderboard[target_display]["drugs"] += amt
            leaderboard[target_display]["paid"] += paid

            await interaction.response.send_message("✅ Action logged!", ephemeral=True)

            await bot.get_channel(LOG_CHANNEL_ID).send(
                f"💊 {user.mention} - Take Drugs for **{target_display}**\n"
                f"➤ Amount: `{amt}`\n➤ Paid: `£{paid:,}` ({money_type.capitalize()})\n\n"
                f"📦 **Storage**\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']:,}\n• Clean: £{storage['clean']:,}"
            )
            await update_leaderboard()

        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

class DropPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Take Drugs", style=discord.ButtonStyle.primary, custom_id="take"))
        self.add_item(Button(label="Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset"))

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    await panel_channel.purge(limit=5)
    await panel_channel.send("📊 **Drop Panel**", view=DropPanel())

async def update_leaderboard():
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    entries = sorted(leaderboard.items(), key=lambda x: x[1]["paid"], reverse=True)

    msg = "📈 **Drug Leaderboard**\n\n"
    for name, stats in entries:
        msg += f"**{name}**: {stats['drugs']} drugs taken • £{stats['paid']:,} paid\n"

    msg += (
        f"\n📦 **Storage Totals:**\n"
        f"• Drugs: {storage['drugs']}\n"
        f"• Dirty: £{storage['dirty']:,}\n"
        f"• Clean: £{storage['clean']:,}"
    )

    await leaderboard_channel.purge(limit=5)
    await leaderboard_channel.send(msg)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        if interaction.type.name == "component":
            if interaction.data["custom_id"] == "take":
                await interaction.response.send_modal(TakeDrugsModal())
            elif interaction.data["custom_id"] == "reset":
                if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
                    await interaction.response.send_message("❌ You don’t have permission.", ephemeral=True)
                else:
                    leaderboard.clear()
                    await update_leaderboard()
                    await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

bot.run(TOKEN)
