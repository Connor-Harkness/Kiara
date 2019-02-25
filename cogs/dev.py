import re

from discord.ext import commands


class Dev(commands.Cog):
    """Development stuff"""

    def __init__(self, bot):
        self.bot = bot
        self.issue = re.compile(r'##(?P<number>[0-9]+)')

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author) or ctx.author.id == 211238461682876416

    @commands.Cog.listener()
    async def on_ready(self):
        ch = await self.bot.redis.get('restartmessage')
        if ch:
            ch = self.bot.get_channel(int(ch))
            await ch.send("Back")
            await self.bot.redis.delete('restartmessage')

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return

        m = self.issue.search(message.content)
        if m is not None:
            url = 'https://github.com/Nekorooni/Kiara/issues/'
            await message.channel.send(url + m.group('number'))

    @commands.command(hidden=True)
    async def restart(self, ctx):
        await ctx.redis.set('restartmessage', ctx.channel.id)
        await ctx.send("Restarting")
        exit(1)

def setup(bot):
    bot.add_cog(Dev(bot))
