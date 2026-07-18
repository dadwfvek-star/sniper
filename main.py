import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import asyncio
import random
import string
import json
import os
from flask import Flask
from threading import Thread

# Flask server for Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Dc_Ai Bot Running"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

WEBHOOKS_FILE = "webhooks.txt"
CHECKED_FILE = "checked.txt"

# Ensure files exist
for f in [WEBHOOKS_FILE, CHECKED_FILE]:
    if not os.path.exists(f):
        open(f, "w").close()

# Load webhooks
def load_webhooks():
    with open(WEBHOOKS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

# Add webhook
def add_webhook(url):
    with open(WEBHOOKS_FILE, "a") as f:
        f.write(url + "\n")

# Load checked links
def load_checked():
    if not os.path.exists(CHECKED_FILE):
        return set()
    with open(CHECKED_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

# Save checked link
def save_checked(link):
    with open(CHECKED_FILE, "a") as f:
        f.write(link + "\n")

# Send to all webhooks
async def notify_webhooks(link, link_type):
    webhooks = load_webhooks()
    if not webhooks:
        return

    payload = {
        "content": f"# SNIPE {link_type}\n-# {link}",
        "username": "Snipe Bot"
    }

    async with aiohttp.ClientSession() as session:
        for webhook_url in webhooks:
            try:
                async with session.post(webhook_url, json=payload) as resp:
                    if resp.status not in [200, 204]:
                        print(f"Webhook failed: {webhook_url} -> {resp.status}")
            except Exception as e:
                print(f"Webhook error: {e}")

# Check Discord Gift Link
async def check_gift_link(code):
    url = f"https://discordapp.com/api/v9/entitlements/gift-codes/{code}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("uses") < data.get("max_uses", 1):
                        return True
                return False
        except:
            return False

# Check Discord Invite Link
async def check_invite_link(code):
    url = f"https://discordapp.com/api/v9/invites/{code}?with_counts=true"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=5) as resp:
                return resp.status == 200
        except:
            return False

# Generate random code
def generate_code(length=16):
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))

# Gift sniper task
@gift_sniper.before_loop
async def before_gift():
    await bot.wait_until_ready()

@gift_sniper.error
async def gift_error(error):
    print(f"Gift sniper error: {error}")
    await asyncio.sleep(5)
    gift_sniper.start()

# Invite sniper task
@invite_sniper.before_loop
async def before_invite():
    await bot.wait_until_ready()

@invite_sniper.error
async def invite_error(error):
    print(f"Invite sniper error: {error}")
    await asyncio.sleep(5)
    invite_sniper.start()

# Gift sniper loop
@tasks.loop(seconds=0.5)
async def gift_sniper():
    code = generate_code(16)
    link = f"https://discord.gift/{code}"

    checked = load_checked()
    if link in checked:
        return

    save_checked(link)

    is_valid = await check_gift_link(code)
    if is_valid:
        await notify_webhooks(link, "GIFT LINK")
        print(f"[GIFT FOUND] {link}")

# Invite sniper loop
@tasks.loop(seconds=0.5)
async def invite_sniper():
    code = generate_code(8)
    link = f"https://discord.gg/{code}"

    checked = load_checked()
    if link in checked:
        return

    save_checked(link)

    is_valid = await check_invite_link(code)
    if is_valid:
        await notify_webhooks(link, "INVITE LINK")
        print(f"[INVITE FOUND] {link}")

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync error: {e}")

@bot.tree.command(name="gift", description="Start sniping Discord gift links")
@app_commands.checks.has_permissions(administrator=True)
async def gift_command(interaction: discord.Interaction):
    if gift_sniper.is_running():
        await interaction.response.send_message("Gift sniper is already running.", ephemeral=True)
        return
    gift_sniper.start()
    await interaction.response.send_message("Gift sniper started.", ephemeral=True)

@bot.tree.command(name="invite", description="Start sniping Discord invite links")
@app_commands.checks.has_permissions(administrator=True)
async def invite_command(interaction: discord.Interaction):
    if invite_sniper.is_running():
        await interaction.response.send_message("Invite sniper is already running.", ephemeral=True)
        return
    invite_sniper.start()
    await interaction.response.send_message("Invite sniper started.", ephemeral=True)

@bot.tree.command(name="webhooks", description="Create a webhook in this channel and add it to the notification list")
@app_commands.checks.has_permissions(administrator=True)
async def webhooks_command(interaction: discord.Interaction):
    webhook = await interaction.channel.create_webhook(name="Snipe Notifications")
    add_webhook(webhook.url)
    await interaction.response.send_message(f"Webhook created and added: `{webhook.url}`", ephemeral=True)

@bot.tree.command(name="stop", description="Stop all snipers")
@app_commands.checks.has_permissions(administrator=True)
async def stop_command(interaction: discord.Interaction):
    gift_sniper.stop() if gift_sniper.is_running() else None
    invite_sniper.stop() if invite_sniper.is_running() else None
    await interaction.response.send_message("All snipers stopped.", ephemeral=True)

@bot.tree.command(name="status", description="Check sniper status")
@app_commands.checks.has_permissions(administrator=True)
async def status_command(interaction: discord.Interaction):
    gift_status = "Running" if gift_sniper.is_running() else "Stopped"
    invite_status = "Running" if invite_sniper.is_running() else "Stopped"
    webhooks = load_webhooks()
    await interaction.response.send_message(
        f"Gift sniper: {gift_status}\nInvite sniper: {invite_status}\nWebhooks: {len(webhooks)}",
        ephemeral=True
    )

# Error handlers
@gift_command.error
@invite_command.error
@webhooks_command.error
@stop_command.error
@status_command.error
async def command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You need administrator permissions.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Error: {error}", ephemeral=True)

# Run
if __name__ == "__main__":
    # Start Flask server in background
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()

    # Run bot
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN environment variable not set")
        exit(1)
    bot.run(TOKEN)
