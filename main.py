import discord
import requests
import asyncio
import os
from keep_alive import keep_alive
from datetime import datetime, timedelta

# Start the web server to keep the bot alive
keep_alive()

# Load secrets from environment variables
TOKEN = os.getenv('MM_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

API_URL = "https://api.gamemonitoring.net/servers/7483264"

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# Track state globally
last_count = None
history = []
last_elder_alert = None
last_regular_ping = datetime.utcnow()

# --- Function: Get player data from API ---
def get_player_data():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()["response"]
        return {
            "players": data["numplayers"],
            "max": data["maxplayers"],
            "name": data["name"]
        }
    except Exception as e:
        print(f"Error fetching player data: {e}")
        return None

# --- Function: Send a regular player update to the channel ---
async def send_player_update(channel, player_data):
    msg = (
        f"**Server Name:** {player_data['name']}\n"
        f"**Players Online:** {player_data['players']} / {player_data['max']}\n"
        f"**Status:** {'Online' if player_data['players'] > 0 else 'Offline'}"
    )
    await channel.send(f"```css\n{msg}\n```")

# --- Function: Send a spike alert if a sudden jump in player count is detected ---
async def send_spike_alert(channel, increase, count):
    msg = (
        f"**Player spike detected!**\n"
        f"**Player count jumped by {increase}** to **{count}** in under 2 minutes!"
    )
    await channel.send(f"```css\n{msg}\n```")

# --- Function: Send an elder alert if player count is low ---
async def send_elder_alert(channel, current_count):
    global last_elder_alert
    role = discord.utils.get(channel.guild.roles, name="Elder Time")
    if role:
        if current_count == 0:
            await channel.send(f"{role.mention} The server is completely empty. Go elder to your heart’s content.")
        else:
            await channel.send(f"{role.mention} Elder time has begun — only {current_count} players on the server. Perfect moment to take advantage.")
        last_elder_alert = datetime.utcnow()

# --- Background loop: Checks server every 2 minutes, sends updates as needed ---
async def monitor_players():
    global last_count, history, last_regular_ping
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    if not channel:
        print("⚠️ Channel not found. Check CHANNEL_ID or bot permissions.")
        return

    while not client.is_closed():
        now = datetime.utcnow()
        player_data = get_player_data()

        if player_data:
            current_count = player_data["players"]

            # Update 2-minute history for spike detection
            history.append((now, current_count))
            history = [(t, c) for t, c in history if now - t <= timedelta(minutes=2)]

            # Spike Detection
            if history:
                oldest_time, oldest_count = history[0]
                if current_count - oldest_count >= 4:
                    await send_spike_alert(channel, current_count - oldest_count, current_count)
                    history = [(now, current_count)]

            # Regular 15-min interval update
            if (now - last_regular_ping) > timedelta(minutes=15):
                await send_player_update(channel, player_data)
                last_regular_ping = now

            # Elder Time Alert: if player count < 3 and 15-minute cooldown
            if current_count < 3:
                if not last_elder_alert or (now - last_elder_alert > timedelta(minutes=15)):
                    await send_elder_alert(channel, current_count)

            # Save the current count for comparison
            last_count = current_count

        await asyncio.sleep(120)  # Wait 2 minutes before checking again

@client.event
async def on_ready():
    print(f'✅ Logged in as {client.user}')
    client.loop.create_task(monitor_players())

client.run(TOKEN)
