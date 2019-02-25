import discord
from discord.ext import commands


class Silhouette(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.name.lower() == 'silhouette':
            await member.kick(reason='Spam bot')


def setup(bot):
    bot.add_cog(Silhouette(bot))
