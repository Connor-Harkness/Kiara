import random

import discord
from discord.ext import commands


class Mercy(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_subcommand=True)
    @commands.guild_only()
    async def mercy(self, ctx):
        """Enter the pink mercy giveaway"""
        if ctx.invoked_subcommand is not None:
            return
        role = discord.utils.get(ctx.guild.roles, name="Guardian Angel")
        if not role:
            return await ctx.send("There's no role named Guardian Angel")
        if role in ctx.author.roles:
            await ctx.send("You already have the role <:MindBreak:417879944169783296>")
        else:
            await ctx.author.add_roles(role)
            await ctx.send("You've been successfully entered into the drawing!")

    @mercy.command(name="winner")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def mercy_winner(self, ctx):
        role = discord.utils.get(ctx.guild.roles, name="Guardian Angel")
        if not role:
            return await ctx.send("There's no role named Guardian Angel")
        participants = [member for member in ctx.guild.members if role in member.roles]
        await ctx.send(random.choice(participants))


def setup(bot):
    bot.add_cog(Mercy(bot))
