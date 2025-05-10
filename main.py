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


# Function to get player data
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


# Sends regular player update
async def send_player_update(channel, player_data):
    msg = (
        f"**Server Name:** {player_data['name']}\n"
        f"**Players Online:** {player_data['players']} / {player_data['max']}\n"
        f"**Status:** {'Online' if player_data['players'] > 0 else 'Offline'}"
    )
    await channel.send(f"```css\n{msg}\n```")


# Sends spike alert
async def send_spike_alert(channel, increase, count):
    msg = (
        f"**Player spike detected!**\n"
        f"**Player count jumped by {increase}** to **{count}** in under 2 minutes!"
    )
    await channel.send(f"```css\n{msg}\n```")


@client.event
async def on_ready():
    print(f'✅ Logged in as {client.user}')
    channel = client.get_channel(CHANNEL_ID)

    last_count = None
    history = []
    last_elder_alert = None

    while True:
        now = datetime.utcnow()
        player_data = get_player_data()

        if player_data:
            current_count = player_data["players"]

            # Update history for spike detection
            history.append((now, current_count))
            history = [(t, c) for t, c in history if now - t <= timedelta(minutes=2)]

            # Check for spike
            if history:
                oldest_time, oldest_count = history[0]
                if current_count - oldest_count >= 4:
                    await send_spike_alert(channel, current_count - oldest_count, current_count)
                    history = [(now, current_count)]

            # Send regular 10-minute update
            await send_player_update(channel, player_data)
            last_count = current_count

            # Elder alert if count < 3 and 15-minute cooldown
            if current_count < 3:
                if not last_elder_alert or (now - last_elder_alert > timedelta(minutes=15)):
                    role = discord.utils.get(channel.guild.roles, name="Elder Time")
                    if role:
                        if current_count == 0:
                            await channel.send(f"{role.mention} The server is completely empty. Go elder to your heart’s content.")
                        else:
                            await channel.send(f"{role.mention} Elder time has begun — only {current_count} players on the server. Perfect moment to take advantage.")
                        last_elder_alert = now

        await asyncio.sleep(600)  # wait 10 minutes before next check

client.run(TOKEN)
