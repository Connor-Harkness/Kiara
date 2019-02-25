import random

import discord
from discord.ext import commands


class Gala(commands.Cog):
    """Help yourself"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_any_role('IQ')
    async def iq(self, ctx, member: discord.Member = None):
        if member is None:
            return await ctx.send('A targeted user is required')
        iq = random.randint(1, 201)
        # like if its 1-300 would be green, 300-600 would be orange, 600-900 would be red and 900-1000 purple? if not just make it always red :p
        if iq <= 19:
            color = discord.Color.green()
        elif iq <= 59:
            color = discord.Color(0xf1c40f)
        elif iq <= 119:
            color = discord.Color.orange()
        elif iq <= 200:
            color = discord.Color.red()
        else:
            color = discord.Color.purple()
        lastmsg = await ctx.history().get(author__id=member.id)
        embed = discord.Embed(color=color, description=f'{member.mention}\n\n"{lastmsg.clean_content}"\n\n{iq} IQ')
        embed.set_author(name='❗ IQ Analyzer ❗', icon_url=member.avatar_url_as(size=32))
        embed.set_footer(text=f'🔮 {lastmsg.created_at.strftime("%d/%m/%Y")}, #{ctx.channel.name} 🔮')

        if lastmsg.attachments:
            embed.set_image(url=lastmsg.attachments[0].url)

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Gala(bot))
