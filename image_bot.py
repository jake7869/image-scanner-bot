import os
import discord
from discord.ext import commands, tasks
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

storage = {"drugs": 0, "dirty": 0, "clean": 0}
leaderboard = {}

class ConfirmModal(Modal, title="Confirm Action"):
    amount = TextInput(label="How many drugs are being taken?")
    money = TextInput(label="How much money was deposited?")
    money_type = TextInput(label="Type (clean or dirty)")
    target = TextInput(label="Who is it for? (optional @mention)", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            amt = int(self.amount.value.replace(",", ""))
            paid = int(self.money.value.replace(",", "").replace("\u00a3", ""))
            is_clean = "clean" in self.money_type.value.lower()
            target = self.target.value.strip()

            if target.startswith("<@") and target.endswith(">"):
                target_id = int(target[2:-1].replace("!", ""))
                member = interaction.guild.get_member(target_id)
                target_display = member.display_name if member else target
            elif target:
                target_display = target
            else:
                target_display = user.display_name

            if amt > storage["drugs"]:
                return await interaction.response.send_message("❌ Not enough drugs in storage.", ephemeral=True)

            if paid < amt * 50000:
                alert_channel = bot.get_channel(LOG_CHANNEL_ID)
                await alert_channel.send(f"🚨 **Suspicious Drop** by {user.mention} - Took `{amt}` drugs for {target_display} but only paid £{paid}.")

            storage["drugs"] -= amt
            leaderboard.setdefault(target_display, {"drugs": 0, "paid": 0})
            leaderboard[target_display]["drugs"] += amt
            leaderboard[target_display]["paid"] += paid
            storage["clean" if is_clean else "dirty"] += paid

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(
                f"💊 {user.mention} - Take Drugs for {target_display}:\n"
                f"➤ Amount: `{amt}`\n➤ Paid: `£{paid}` ({'Clean' if is_clean else 'Dirty'})\n"
                f"\n📥 Storage:\n• Drugs: {storage['drugs']}\n• Dirty: £{storage['dirty']}\n• Clean: £{storage['clean']}"
            )
            await interaction.response.send_message("✅ Action logged.", ephemeral=True)
            await update_leaderboard()
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

class SetDrugsModal(Modal, title="Set Drug Count"):
    amount = TextInput(label="How many drugs are now in storage?")

    async def on_submit(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission.", ephemeral=True)

        try:
            amt = int(self.amount.value.replace(",", ""))
            storage["drugs"] = amt
            await interaction.response.send_message(f"✅ Drug storage set to `{amt}`.", ephemeral=True)
            await update_leaderboard()
        except:
            await interaction.response.send_message("❌ Invalid number.", ephemeral=True)

class ButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Take Drugs", style=discord.ButtonStyle.primary, custom_id="take"))
        self.add_item(Button(label="Set Drugs (Admin Only)", style=discord.ButtonStyle.secondary, custom_id="set", row=1))
        self.add_item(Button(label="Remove All Money (Admin Only)", style=discord.ButtonStyle.danger, custom_id="clear_money", row=1))
        self.add_item(Button(label="Reset Leaderboard (Admin Only)", style=discord.ButtonStyle.danger, custom_id="reset", row=2))

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    await update_panel()
    await update_leaderboard()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    cid = interaction.data.get("custom_id")
    if cid == "take":
        await interaction.response.send_modal(ConfirmModal())
    elif cid == "reset":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission.", ephemeral=True)
        leaderboard.clear()
        await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)
        await update_leaderboard()
    elif cid == "clear_money":
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission.", ephemeral=True)
        storage["clean"] = 0
        storage["dirty"] = 0
        await interaction.response.send_message("✅ Money cleared.", ephemeral=True)
        await update_leaderboard()
    elif cid == "set":
        await interaction.response.send_modal(SetDrugsModal())

async def update_panel():
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if not channel:
        return
    await channel.purge(limit=5)
    await channel.send("📊 **Drop Panel**", view=ButtonView())

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return
    await channel.purge(limit=5)

    embed = discord.Embed(title="📈 Drug Leaderboard", color=discord.Color.green())
    if leaderboard:
        sorted_users = sorted(leaderboard.items(), key=lambda x: x[1]["paid"], reverse=True)
        for user, data in sorted_users:
            embed.add_field(
                name=f"{user}",
                value=f"Drugs Taken: `{data['drugs']}`\nMoney Paid: `£{data['paid']}`",
                inline=False
            )
    else:
        embed.description = "No data yet."

    embed.set_footer(text=f"Storage Totals: Drugs: {storage['drugs']} | Dirty: £{storage['dirty']} | Clean: £{storage['clean']}")
    await channel.send(embed=embed)

bot.run(TOKEN)
