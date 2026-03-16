import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID"))  # Channel to stay in

intents = discord.Intents.default()
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ── State ──────────────────────────────────────────────────────────────────────
target_channel_id: int = TARGET_CHANNEL_ID
staying: bool = True          # Toggle to stop the bot from rejoining


# ── on_ready ───────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    await tree.sync()
    print("✅ Slash commands synced")
    watchdog.start()          # Start the 24/7 watchdog loop


# ── Watchdog loop — checks every 10 s and rejoins if disconnected ──────────────
@tasks.loop(seconds=10)
async def watchdog():
    if not staying:
        return

    channel = bot.get_channel(target_channel_id)
    if channel is None or not isinstance(channel, discord.VoiceChannel):
        return

    guild = channel.guild
    vc = guild.voice_client

    # Already connected to the right channel — do nothing
    if vc and vc.channel.id == target_channel_id and vc.is_connected():
        return

    # Connected somewhere else — move
    if vc and vc.is_connected():
        await vc.move_to(channel)
        print(f"🔀 Moved to #{channel.name}")
        return

    # Not connected at all — join
    try:
        await channel.connect()
        print(f"🎙️ Joined #{channel.name}")
    except Exception as e:
        print(f"❌ Could not join channel: {e}")


@watchdog.before_loop
async def before_watchdog():
    await bot.wait_until_ready()


# ── Slash command: /join ────────────────────────────────────────────────────────
@tree.command(name="join", description="Make the bot join your current voice channel")
async def join(interaction: discord.Interaction):
    global target_channel_id, staying

    if interaction.user.voice is None:
        await interaction.response.send_message("❌ You need to be in a voice channel first!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    target_channel_id = channel.id
    staying = True

    vc = interaction.guild.voice_client
    if vc and vc.is_connected():
        await vc.move_to(channel)
    else:
        await channel.connect()

    await interaction.response.send_message(f"✅ Joined **{channel.name}** and will stay there 24/7!", ephemeral=True)


# ── Slash command: /leave ───────────────────────────────────────────────────────
@tree.command(name="leave", description="Make the bot leave the voice channel")
async def leave(interaction: discord.Interaction):
    global staying

    staying = False
    vc = interaction.guild.voice_client
    if vc and vc.is_connected():
        await vc.disconnect()
        await interaction.response.send_message("👋 Left the voice channel.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ I'm not in a voice channel.", ephemeral=True)


# ── Slash command: /status ──────────────────────────────────────────────────────
@tree.command(name="status", description="Check if the bot is in a voice channel")
async def status(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_connected():
        await interaction.response.send_message(
            f"🎙️ Currently in **{vc.channel.name}** | Auto-rejoin: {'✅ ON' if staying else '❌ OFF'}",
            ephemeral=True
        )
    else:
        await interaction.response.send_message("❌ Not in any voice channel right now.", ephemeral=True)


# ── Auto-rejoin on voice state update (kicked detection) ───────────────────────
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member != bot.user:
        return
    if not staying:
        return

    # Bot was disconnected
    if before.channel is not None and after.channel is None:
        print("⚠️ Bot was disconnected! Rejoining in 3s...")
        await asyncio.sleep(3)
        channel = bot.get_channel(target_channel_id)
        if channel:
            try:
                await channel.connect()
                print(f"🔁 Rejoined #{channel.name}")
            except Exception as e:
                print(f"❌ Failed to rejoin: {e}")


# ── Run ─────────────────────────────────────────────────────────────────────────
bot.run(TOKEN)
