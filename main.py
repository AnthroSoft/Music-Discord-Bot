# main
import discord
from discord.ext import commands
# essential
import youtube_dl
# important
import asyncio
import functools
import itertools
# for embed timestamp (not necessary)
import datetime

# bug report
youtube_dl.utils.bug_reports_message = lambda: ''

# bot's def
bot = commands.Bot(command_prefix='?', case_insensitive=True,
                   description="Type Anything Here")
bot.remove_command('help')

# information
botname = 'Your Bot Name Here'
TOKEN = 'Your Bot Token Here'


# status
@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.playing, name='?help'))
    print('{0.user.name} Is Online!'.format(bot))


# rest of the code
class VoiceError(Exception):
    pass


class YTDLError(Exception):
    pass


class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'source_address': '0.0.0.0',
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx: commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.stream_url = data.get('url')

    def __str__(self):
        return '**{0.title}** by **{0.uploader}**'.format(self)

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(
            cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError(
                'Couldn\'t find anything that matches `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError(
                    'Couldn\'t find anything that matches `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(
            cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError(
                        'Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    @classmethod
    async def search_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        channel = ctx.channel
        loop = loop or asyncio.get_event_loop()

        cls.search_query = '%s%s:%s' % ('ytsearch', 10, ''.join(search))

        partial = functools.partial(
            cls.ytdl.extract_info, cls.search_query, download=False, process=False)
        info = await loop.run_in_executor(None, partial)

        cls.search = {}
        cls.search["title"] = f'Search results for:\n**{search}**'
        cls.search["type"] = 'rich'
        cls.search["color"] = 7506394
        cls.search["author"] = {'name': f'{ctx.author.name}',
                                'url': f'{ctx.author.avatar_url}', 'icon_url': f'{ctx.author.avatar_url}'}

        lst = []

        for e in info['entries']:
            VId = e.get('id')
            VUrl = 'https://www.youtube.com/watch?v=%s' % (VId)
            lst.append(
                f'`{info["entries"].index(e) + 1}.` [{e.get("title")}]({VUrl})\n')

        lst.append('\n**Type a number to make a choice, Type `cancel` to exit**')
        cls.search["description"] = "\n".join(lst)

        em = discord.Embed.from_dict(cls.search)
        await ctx.send(embed=em, delete_after=45.0)

        def check(msg):
            return msg.content.isdigit() == True and msg.channel == channel or msg.content == 'cancel' or msg.content == 'Cancel'

        try:
            m = await bot.wait_for('message', check=check, timeout=45.0)

        except asyncio.TimeoutError:
            rtrn = 'timeout'

        else:
            if m.content.isdigit() == True:
                sel = int(m.content)
                if 0 < sel <= 10:
                    for key, value in info.items():
                        if key == 'entries':
                            """data = value[sel - 1]"""
                            VId = value[sel - 1]['id']
                            VUrl = 'https://www.youtube.com/watch?v=%s' % (VId)
                            partial = functools.partial(
                                cls.ytdl.extract_info, VUrl, download=False)
                            data = await loop.run_in_executor(None, partial)
                    rtrn = cls(ctx, discord.FFmpegPCMAudio(
                        data['url'], **cls.FFMPEG_OPTIONS), data=data)
                else:
                    rtrn = 'sel_invalid'
            elif m.content == 'cancel':
                rtrn = 'cancel'
            else:
                rtrn = 'sel_invalid'

        return rtrn

    @staticmethod
    def parse_duration(duration: int):
        if duration > 0:
            minutes, seconds = divmod(duration, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)

            duration = []
            if days > 0:
                duration.append('{}'.format(days))
            if hours > 0:
                duration.append('{}'.format(hours))
            if minutes > 0:
                duration.append('{}'.format(minutes))
            if seconds > 0:
                duration.append('{}'.format(seconds))

            value = ':'.join(duration)

        elif duration == 0:
            value = "LIVE"

        return value


class Song:
    __slots__ = ('source', 'requester')

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()
        self.exists = True

        self.skip_votes = set()

    def __del__(self):
        self.audio_player.cancel()

    def __del__(self):
        self.audio_player.cancel()


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state or not state.exists:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage(
                'This command can\'t be used in DM channels.')

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    @commands.command(name='join', invoke_without_subcommand=True)
    async def _join(self, ctx: commands.Context):
        destination = ctx.message.author.voice.channel
        if ctx.voice_client is None:
            embed = discord.Embed(
                description='✅ Successfully Joined The VC',
                colour=discord.Colour.red()
            )
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text=f'{botname}')
            embed.set_author(name=ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            await ctx.reply(embed=embed, mention_author=False)
            await destination.connect()
        else:
            embed = discord.Embed(
                description='❎ Error! Bot is already in a VC',
                colour=discord.Colour.red()
            )
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text=f'{botname}')
            embed.set_author(name=ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name='summon')
    async def _summon(self, ctx: commands.Context):
        destination = ctx.message.author.voice.channel
        if ctx.voice_client is None:
            embed = discord.Embed(
                description='❎ Error! Bot is not connected to any VC',
                colour=discord.Colour.red()
            )
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text=f'{botname}')
            embed.set_author(name=ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            await ctx.reply(embed=embed, mention_author=False)
        else:
            await ctx.voice_client.move_to(destination)

    @commands.command(name='leave')
    async def _leave(self, ctx: commands.Context):
        if not ctx.guild.voice_client:
            embed = discord.Embed(
                description='❎ Error! Bot is not connected to any VC',
                colour=discord.Colour.red()
            )
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text=f'{botname}')
            embed.set_author(name=ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            await ctx.reply(embed=embed, mention_author=False)
        else:
            await ctx.voice_client.disconnect()
            embed = discord.Embed(
                description='✅ Successfully Left The VC',
                colour=discord.Colour.red()
            )
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text=f'{botname}')
            embed.set_author(name=ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            await ctx.reply(embed=embed, mention_author=False)
            await ctx.voice_client.disconnect()

    @commands.command(name='pause')
    async def _pause(self, ctx: commands.Context):
        embed = discord.Embed(
            description='⏸️ Paused!',
            colour=discord.Colour.red()
        )
        embed.timestamp = datetime.datetime.utcnow()
        embed.set_footer(text=f'{botname}')
        embed.set_author(name=ctx.author.name,
                         icon_url=ctx.author.avatar_url)
        await ctx.reply(embed=embed, mention_author=False)
        await ctx.voice_client.pause()

    @commands.command(name='resume')
    async def _resume(self, ctx: commands.Context):
        embed = discord.Embed(
            description='▶️ Resumed!',
            colour=discord.Colour.red()
        )
        embed.timestamp = datetime.datetime.utcnow()
        embed.set_footer(text=f'{botname}')
        embed.set_author(name=ctx.author.name,
                         icon_url=ctx.author.avatar_url)
        await ctx.reply(embed=embed, mention_author=False)
        await ctx.voice_client.resume()

    @commands.command(name='stop')
    async def _stop(self, ctx: commands.Context):
        embed = discord.Embed(
            description=f'✅ Stopped the song', colour=discord.Colour.red())
        embed.timestamp = datetime.datetime.utcnow()
        embed.set_footer(text=f'{botname}')
        embed.set_author(name=ctx.author.name,
                         icon_url=ctx.author.avatar_url)
        await ctx.reply(embed=embed, mention_author=False)
        ctx.voice_client.stop()

    @commands.command(name='play')
    async def _play(self, ctx: commands.Context, *, search: str = None):
        if search == None:
            embed = discord.Embed(
                description='❎ Error! Please specify a song to play',
                colour=discord.Colour.red()
            )
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text=f'{botname}')
            embed.set_author(name=ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            await ctx.reply(embed=embed, mention_author=False)
        else:
            async with ctx.typing():
                try:
                    source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
                except YTDLError as e:
                    await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
                else:
                    if not ctx.guild.voice_client:
                        vc = ctx.message.author.voice.channel
                        await vc.connect()
                    song = Song(source)
                    await ctx.voice_state.songs.put(song)
                    await ctx.guild.change_voice_state(channel=ctx.author.voice.channel, self_deaf=True)
                    ctx.voice_client.play(source)
                    embed = discord.Embed(
                        description=f'✅ Enqueued {str(source)}', colour=discord.Colour.red())
                    embed.timestamp = datetime.datetime.utcnow()
                    embed.set_footer(text=f'{botname}')
                    embed.set_author(name=ctx.author.name,
                                     icon_url=ctx.author.avatar_url)
                    await ctx.reply(embed=embed, mention_author=False)

    @ commands.command(name='search')
    async def _search(self, ctx: commands.Context, *, search: str = None):
        if search == None:
            embed = discord.Embed(
                description='❎ Error! Please specify a song to search',
                colour=discord.Colour.red()
            )
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text=f'{botname}')
            embed.set_author(name=ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            await ctx.reply(embed=embed, mention_author=False)
        else:
            async with ctx.typing():
                try:
                    source = await YTDLSource.search_source(ctx, search, loop=self.bot.loop)
                except YTDLError as e:
                    await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
                else:
                    if source == 'sel_invalid':
                        await ctx.send('Invalid selection')
                    elif source == 'cancel':
                        await ctx.send(':white_check_mark:')
                    elif source == 'timeout':
                        await ctx.send(':alarm_clock: **Time\'s up bud**')
                    else:
                        if not ctx.voice_state.voice:
                            await ctx.invoke(self._join)
                        song = Song(source)
                        await ctx.voice_state.songs.put(song)
                        vc = ctx.voice_client
                        vc.play(source)
                        await ctx.send('Enqueued {}'.format(str(source)))

    @ _summon
    @ _join.before_invoke
    @ _play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                description='❎ Error! You are not connected to any VC',
                colour=discord.Colour.red()
            )
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_footer(text=f'{botname}')
            embed.set_author(name=ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            await ctx.reply(embed=embed, mention_author=False)


@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title='__Help Menu__',
        description='Write Something Here!',
        color=discord.Colour.red())
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_footer(text=f'{botname}')
    embed.set_author(name=f'{botname}',
                     icon_url='https://cdn.discordapp.com/attachments/968089547894317066/1004129550030090291/repeat-button_1f501.png')
    embed.add_field(
        name='🎶 • Music Commands',
        value='**Command:** ``?join``\n**Usage:** *Joins a voice channel*\n**Command:** ``?leave``\n**Usage:** *leaves the voice channel*\n**Command:** ``?play`` ``<song name>``\n**Usage:** *Plays a song*\n**Command:** ``?pause``\n**Usage:** *Pauses the currently playing song*\n**Command:** ``?resume``\n**Usage:** *Resumes a currently paused song*\n**Command:** ``?summon``\n**Usage:** *Summons the bot to your voice channel*\n**Command:** ``?stop``\n**Usage:** *Stops playing song and clears the queue*', inline=False)
    await ctx.send(embed=embed)

bot.add_cog(Music(bot))

bot.run(TOKEN)
