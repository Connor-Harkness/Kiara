import asyncio

import discord
from discord.ext import commands


class Fun(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def countgame(self, ctx):
        """Start a counting game"""
        if ctx.invoked_subcommand:
            return

        last = None
        count = 0
        participants = []

        await ctx.send("Start counting!")

        while True:
            try:
                msg = await self.bot.wait_for('message', check=lambda m: m.channel.id == ctx.channel.id and not m.author.bot, timeout=60)
            except asyncio.TimeoutError:
                await ctx.send(embed=discord.Embed(description=f"Sorry you took too long."))
                break
            # if msg.author.id == last:
            #     break
            try:
                if int(msg.content) == count+1:
                    last = msg.author.id
                    if msg.author.id not in participants:
                        participants += [msg.author.id]
                    count += 1
                    continue
                else:
                    break
            except ValueError:
                break
        hiscore = int(await ctx.redis.get("countgame_highscore") or 0)
        if count > hiscore:
            await ctx.redis.set('countgame_highscore', count)
            await ctx.redis.delete('countgame_participants')
            await ctx.redis.lpush('countgame_participants', *participants)
            await ctx.redis.set('countgame_cuck', msg.author.id)
            await ctx.send(embed=discord.Embed(description=f"{msg.author.mention} broke the chain. You made it to {count} **NEW RECORD**"))
        else:
            await ctx.send(embed=discord.Embed(description=f"{msg.author.mention} broke the chain. You made it to {count}"))

    @countgame.command(aliases=['best'])
    async def countgame_best(self, ctx):
        em = discord.Embed()
        em.add_field(name='Best score', value=str(await ctx.redis.get('countgame_highscore', encoding='utf8')))
        participants = [f'<@{m}>' for m in await ctx.redis.lrange('countgame_participants', 0, -1, encoding='utf8')]
        em.add_field(name='Participants', value='\n'.join(participants) or "Noone")
        ended_by = await ctx.redis.get('countgame_cuck', encoding='utf8')
        em.add_field(name='Ruined by', value=f'<@{ended_by}>')
        await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(Fun(bot))
