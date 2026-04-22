import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from database import Database

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
owner_env = os.getenv("OWNER_ID")

if not owner_env:
    raise ValueError("OWNER_ID missing")

try:
    OWNER_ID = int(owner_env)
except:
    raise ValueError("OWNER_ID must be a number")  # Your Discord user ID - only YOU get /setmoney

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
db = Database()

# Make db and OWNER_ID accessible to cogs
bot.db = db
bot.OWNER_ID = OWNER_ID

@bot.event
async def on_ready():
    print(f"🎰 {bot.user} is online and ready to gamble!")
    await bot.load_extension("cogs.economy")
    await bot.load_extension("cogs.gambling")
    await bot.load_extension("cogs.admin")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Sync error: {e}")

bot.run(TOKEN)
