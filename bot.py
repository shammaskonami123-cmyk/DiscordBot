import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import os
from flask import Flask
from threading import Thread

# --- Flask Keep Alive ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# --- Music Bot Logic ---

ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': 'True',
    'quiet': True,
    'default_search': 'ytsearch',
    'no_warnings': True,
}

ffmpeg_opts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.queue = {} 
        self.loop_status = {} # ലൂപ്പ് സ്റ്റാറ്റസ് സൂക്ഷിക്കാൻ

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Logged in as {self.user}")

bot = MusicBot()

# --- Helper Functions ---

async def play_next(interaction, guild_id):
    if guild_id not in bot.queue or not bot.queue[guild_id]:
        return

    vc = interaction.guild.voice_client
    if not vc:
        return

    # ലൂപ്പ് ഓഫ് ആണെങ്കിൽ മാത്രം പഴയ പാട്ട് ക്യൂവിൽ നിന്ന് മാറ്റുക
    if not bot.loop_status.get(guild_id, False):
        song_data = bot.queue[guild_id].pop(0)
    else:
        song_data = bot.queue[guild_id][0] # ലൂപ്പ് ഓൺ ആണെങ്കിൽ ആദ്യത്തെ പാട്ട് തന്നെ എടുക്കുക

    try:
        source = await discord.FFmpegOpusAudio.from_probe(song_data['url'], **ffmpeg_opts)
        
        def after_playing(error):
            coro = play_next(interaction, guild_id)
            fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
            try:
                fut.result()
            except:
                pass

        vc.play(source, after=after_playing)
        
        embed = discord.Embed(title="ഇപ്പോൾ പ്ലേ ചെയ്യുന്നു 🎶", description=f"**{song_data['title']}**", color=discord.Color.blue())
        await interaction.channel.send(embed=embed)
        
    except Exception as e:
        print(f"Error: {e}")
        await play_next(interaction, guild_id)

# --- Slash Commands ---

@bot.tree.command(name="play", description="പാട്ടിന്റെ പേരോ ലിങ്കോ നൽകുക")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    if not interaction.user.voice:
        return await interaction.followup.send("❌ നിങ്ങൾ ആദ്യം ഒരു വോയിസ് ചാനലിൽ കയറണം!")

    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()

    guild_id = interaction.guild.id

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info: info = info['entries'][0]
            
            song_data = {
                'url': info['url'], 
                'title': info['title'],
                'link': info.get('webpage_url')
            }

            if guild_id not in bot.queue:
                bot.queue[guild_id] = []

            bot.queue[guild_id].append(song_data)

            if not vc.is_playing():
                await interaction.followup.send(f"🔍 **കണ്ടെത്തി:** {song_data['title']}")
                await play_next(interaction, guild_id)
            else:
                await interaction.followup.send(f"✅ **ക്യൂവിൽ ചേർത്തു:** {song_data['title']}")

        except Exception as e:
            await interaction.followup.send(f"❌ എറർ സംഭവിച്ചു: {e}")

@bot.tree.command(name="skip", description="അടുത്ത പാട്ടിലേക്ക് പോകുക")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        # സ്കിപ്പ് ചെയ്യുമ്പോൾ ലൂപ്പ് താൽക്കാലികമായി ഓഫ് ചെയ്യണം അല്ലെങ്കിൽ അതേ പാട്ട് തന്നെ വീണ്ടും വരും
        guild_id = interaction.guild.id
        was_looping = bot.loop_status.get(guild_id, False)
        bot.loop_status[guild_id] = False
        
        vc.stop()
        
        # കുറച്ചു കഴിഞ്ഞ് ലൂപ്പ് പഴയ പടിയാക്കാം
        bot.loop_status[guild_id] = was_looping
        await interaction.response.send_message("⏭️ അടുത്ത പാട്ടിലേക്ക് മാറുന്നു...")
    else:
        await interaction.response.send_message("❌ പാട്ടുകളൊന്നും പ്ലേ ചെയ്യുന്നില്ല!")

@bot.tree.command(name="loop", description="നിലവിലെ പാട്ട് ആവർത്തിച്ചു കേൾക്കാൻ")
async def loop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    current_status = bot.loop_status.get(guild_id, False)
    bot.loop_status[guild_id] = not current_status
    
    msg = "✅ ലൂപ്പ് **ഓൺ** ആക്കി" if bot.loop_status[guild_id] else "❌ ലൂപ്പ് **ഓഫ്** ആക്കി"
    await interaction.response.send_message(msg)

@bot.tree.command(name="stop", description="ബോട്ട് ഓഫ് ചെയ്യുക")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        bot.queue[interaction.guild.id] = []
        await vc.disconnect()
        await interaction.response.send_message("⏹️ ബോട്ട് ഡിസ്‌കണക്ട് ആയി.")

import discord

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.presences = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Bot is online as {client.user}")

# Example command
@client.event
async def on_message(message):
    if message.content == "!ping":
        await message.channel.send("Pong!")

# Direct token, LAST LINE
client.run("MTQ4NzA0OTM5NzM5MTg1NTY0Nw.G9Ue1r.nZOa-ZOf3BgN_EBRwRDJS5mBOH1h0m72sO5oV0")
