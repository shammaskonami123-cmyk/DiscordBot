import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio

# മ്യൂസിക് സെറ്റിംഗ്സ്
ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': 'True',
    'quiet': True,
    'default_search': 'ytsearch',
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
        self.loop = {}  

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Logged in as {self.user} - Professional Music Bot Ready!")

bot = MusicBot()

# --- മ്യൂസിക് പ്ലേയിംഗ് ലോജിക് ---

async def play_next(interaction, guild_id):
    if guild_id not in bot.queue or not bot.queue[guild_id]:
        return

    vc = interaction.guild.voice_client
    if not vc:
        return

    # ലൂപ്പ് ഓഫ് ആണെങ്കിൽ പഴയ പാട്ട് കളയുക
    if not bot.loop.get(guild_id, False):
        bot.queue[guild_id].pop(0)

    if not bot.queue[guild_id]:
        return

    next_song = bot.queue[guild_id][0]
    source = await discord.FFmpegOpusAudio.from_probe(next_song['url'], **ffmpeg_opts)
    
    vc.play(source, after=lambda e: bot.loop_event.set())
    bot.loop_event.clear()
    await bot.loop_event.wait()
    await play_next(interaction, guild_id)

# --- സ്ലാഷ് കമാൻഡുകൾ ---

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
                'thumbnail': info.get('thumbnail'),
                'link': info.get('webpage_url')
            }

            if guild_id not in bot.queue:
                bot.queue[guild_id] = [song_data]
                bot.loop_event = asyncio.Event()
                
                source = await discord.FFmpegOpusAudio.from_probe(song_data['url'], **ffmpeg_opts)
                vc.play(source, after=lambda e: bot.loop_event.set())
                
                embed = discord.Embed(title="ഇപ്പോൾ പ്ലേ ചെയ്യുന്നു 🎶", description=f"**[{song_data['title']}]({song_data['link']})**", color=discord.Color.green())
                if song_data['thumbnail']: embed.set_thumbnail(url=song_data['thumbnail'])
                await interaction.followup.send(embed=embed)
                
                # അടുത്ത പാട്ടുകൾക്കായി വെയിറ്റ് ചെയ്യുന്നു
                await bot.loop_event.wait()
                await play_next(interaction, guild_id)
            else:
                bot.queue[guild_id].append(song_data)
                await interaction.followup.send(f"✅ **ക്യൂവിൽ ചേർത്തു:** {song_data['title']}")

        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="skip", description="അടുത്ത പാട്ടിലേക്ക് പോകുക")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭️ അടുത്ത പാട്ടിലേക്ക് മാറുന്നു...")
    else:
        await interaction.response.send_message("❌ പാട്ടുകളൊന്നും പ്ലേ ചെയ്യുന്നില്ല!")

@bot.tree.command(name="loop", description="ലൂപ്പ് ഓൺ/ഓഫ് ചെയ്യുക")
async def loop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    bot.loop[guild_id] = not bot.loop.get(guild_id, False)
    status = "ഓൺ" if bot.loop[guild_id] else "ഓഫ്"
    await interaction.response.send_message(f"🔁 ലൂപ്പ് ഇപ്പോൾ **{status}** ആണ്.")

@bot.tree.command(name="stop", description="പാട്ട് നിർത്തി ബോട്ട് ലീവ് ആകുക")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        bot.queue[interaction.guild.id] = []
        await vc.disconnect()
        await interaction.response.send_message("⏹️ ബോട്ട് ഡിസ്‌കണക്ട് ആയി.")

# നിങ്ങളുടെ ടോക്കൺ ഇവിടെ ചേർത്തു
bot.run('MTQ4NzA0OTM5NzM5MTg1NTY0Nw.GSN1d6.9ZfVferFBUtOaFSunrqEGi-bom9Qfeeu0lEBOI')
