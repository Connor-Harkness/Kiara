import discord
from discord.ext import commands


class Manage(commands.Cog):
    """Commands for managing Kiara as user"""

    def __init__(self, bot):
        self.bot = bot

    async def __local_check(self, ctx):
        return ctx.author.id in [73389450113069056, 211238461682876416]

    @commands.group(hidden=True, aliases=['set', 'mng'])
    async def manage(self, ctx):
        """Manage Kiara"""
        if ctx.invoked_subcommand is None:
            raise commands.CommandInvokeError

    @manage.command(hidden=True, aliases=['user', 'name'])
    async def username(self, ctx, *, name):
        """Set Kiara's username."""
        await self.bot.user.edit(username=name)

    @manage.command(hidden=True, aliases=['nick'])
    @commands.guild_only()
    async def nickname(self, ctx, *, name=None):
        """Set Kiara's nickname."""
        await ctx.guild.me.edit(nick=name)

    @manage.command(hidden=True, aliases=['ava'])
    async def avatar(self, ctx, url=None):
        """Set Kiara's avatar."""
        if url:
            async with self.bot.session.get(url) as resp:
                if resp.status == 200:
                    await self.bot.user.edit(avatar=await resp.read())
        else:
            if ctx.message.attachments:
                async with self.bot.session.get(ctx.message.attachments[0].url) as resp:
                    if resp.status == 200:
                        await self.bot.user.edit(avatar=await resp.read())
            else:
                await self.bot.user.edit(avatar=None)

    @manage.command(hidden=True, aliases=['game'])
    async def playing(self, ctx, *, game: discord.Game = None):
        """Set Kiara's game."""
        await self.bot.change_presence(game=game)

    @manage.command(hidden=True)
    async def status(self, ctx, status = 'online'):
        """Set Kiara's status."""
        await self.bot.change_presence(status=discord.Status[status])

    @manage.command(hidden=True)
    async def stream(self, ctx, url=None, *, title=None):
        """Set Kiara's stream."""
        if ctx.guild:
            await self.bot.change_presence(game=discord.Game(name=title or ctx.guild.me.game.name or '\u200b', url=url, type=1))
        else:
            await self.bot.change_presence(game=discord.Game(name=title or '\u200b', url=url, type=1))
        # TODO: Maybe a better way to handle no title

    @manage.command(hidden=True, aliases=['listeningto'])
    async def listening(self, ctx, *, status):
        """Set Kiara's 'listening to' status."""
        await self.bot.change_presence(game=discord.Game(name=status, type=2))

    @manage.command(hidden=True)
    async def watching(self, ctx, *, status):
        """Set Kiara's 'watching' status."""
        await self.bot.change_presence(game=discord.Game(name=status, type=3))

def setup(bot):
    bot.add_cog(Manage(bot))
