import discord
from discord.ext import commands


class Minecraft(commands.Cog):
    """Minecraft server related commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def minecraft(self, ctx):
        guild = self.bot.get_guild(215424443005009920) or ctx.guild
        member = guild.get_member(ctx.author.id)
        if discord.utils.get(member.roles, id=457213160504426496) is None:
            return await ctx.send("You need to be at least level 3.")
        try:
            await ctx.author.send(await ctx.redis.get(f'snippet:minecraftrules1', encoding='utf8'))
            await ctx.author.send(await ctx.redis.get(f'snippet:minecraftrules2', encoding='utf8'))
            if ctx.guild:
                await ctx.send("I sent you a DM!")
        except discord.Forbidden:
            if ctx.guild:
                await ctx.send("Please use this command in a DM with me.")

    @commands.command()
    async def confirm(self, ctx, *, minecraft_username):
        guild = self.bot.get_guild(215424443005009920) or ctx.guild
        member = guild.get_member(ctx.author.id)
        if discord.utils.get(member.roles, id=457213160504426496) is None:
            return await ctx.send("You need to be at least level 3.")

        await self.bot.db.execute("INSERT INTO minecraft_whitelist (user_id, username) VALUES (%s, %s)",
                                  (ctx.author.id, minecraft_username))

        ch = self.bot.get_channel(508326036845363227)
        await ch.send(embed=discord.Embed(title=f"{ctx.author} wants to get whitelisted.", description=f"`{minecraft_username}`"))
        await ctx.send("Thank you! You've now been added to the whitelist queue, when we confirm you, connect using the IP `waifuworshipping.com`")

def setup(bot):
    bot.add_cog(Minecraft(bot))
