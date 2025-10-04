import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from datetime import datetime, timedelta

# ==============================
# Intents
# ==============================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# ==============================
# Bot Setup
# ==============================
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.report_channels = self.load_config()
        self.bad_words = self.load_bad_words()
        self.recent_messages = {}  # For spam detection

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced (global).")

    def load_config(self):
        if os.path.exists("report_config.json"):
            with open("report_config.json", "r") as f:
                return json.load(f)
        return {}

    def save_config(self):
        with open("report_config.json", "w") as f:
            json.dump(self.report_channels, f, indent=4)

    def load_bad_words(self):
        if os.path.exists("bad_words.json"):
            with open("bad_words.json", "r") as f:
                return json.load(f)
        return []

bot = MyBot()

# ==============================
# Events
# ==============================
@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content_lower = message.content.lower()
    triggered_words = [word for word in bot.bad_words if word in content_lower]
    guild_id = str(message.guild.id)

    # ------------------------------
    # Bad word detection
    # ------------------------------
    if triggered_words:
        if guild_id in bot.report_channels:
            channel_id = bot.report_channels[guild_id]
            report_channel = bot.get_channel(channel_id)
            if report_channel:
                embed = discord.Embed(
                    title="🚨 Banned Word Detected",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="👤 User", value=message.author.mention, inline=False)
                embed.add_field(name="💬 Message", value=message.content, inline=False)
                embed.add_field(name="⚠️ Triggered Words", value=", ".join(triggered_words), inline=False)
                embed.add_field(name="📍 Channel", value=message.channel.mention, inline=True)
                embed.add_field(name="🕒 Time", value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), inline=True)
                await report_channel.send(embed=embed)

        # Delete the message automatically
        try:
            await message.delete()
        except discord.errors.Forbidden:
            print(f"⚠️ Missing permissions to delete message in {message.channel.name}")

    # ------------------------------
    # Spam detection
    # ------------------------------
    user_id = message.author.id
    now = datetime.utcnow()

    if user_id not in bot.recent_messages:
        bot.recent_messages[user_id] = []

    # Remove old messages (>4 seconds)
    bot.recent_messages[user_id] = [m for m in bot.recent_messages[user_id] if now - m["time"] <= timedelta(seconds=4)]

    # Add current message
    bot.recent_messages[user_id].append({"content": content_lower, "time": now})

    # Count repeated messages
    counts = sum(1 for m in bot.recent_messages[user_id] if m["content"] == content_lower)
    if counts > 2:  # Same message sent more than 2 times in 4 seconds
        if guild_id in bot.report_channels:
            channel_id = bot.report_channels[guild_id]
            report_channel = bot.get_channel(channel_id)
            if report_channel:
                embed = discord.Embed(
                    title="⚠️ Spam Detected",
                    color=discord.Color.orange(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="👤 User", value=message.author.mention, inline=False)
                embed.add_field(name="💬 Message", value=message.content, inline=False)
                embed.add_field(name="📍 Channel", value=message.channel.mention, inline=True)
                embed.add_field(name="🕒 Time", value=now.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=True)
                await report_channel.send(embed=embed)

    await bot.process_commands(message)

# ==============================
# Slash Commands
# ==============================
@bot.tree.command(name="setreport", description="Set the channel for abuse reports")
@app_commands.checks.has_permissions(administrator=True)
async def setreport(interaction: discord.Interaction, channel: discord.TextChannel):
    bot.report_channels[str(interaction.guild.id)] = channel.id
    bot.save_config()
    await interaction.response.send_message(f"✅ Report channel set to {channel.mention}", ephemeral=True)

@setreport.error
async def setreport_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ You must be an **Administrator** to use this command.", ephemeral=True)

@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong! The bot is working.", ephemeral=True)

# ==============================
# Run Bot
# ==============================
bot.run(os.environ["DISCORD_TOKEN"])
