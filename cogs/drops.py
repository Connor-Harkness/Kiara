import asyncio
import datetime
import random
import sys

import discord
from discord.ext import commands

import logging

log = logging.getLogger(__name__)


class Drops(commands.Cog):
    """Random lewd care packages"""

    def __init__(self, bot):
        self.bot = bot
        self.economy = self.bot.get_cog('Economy')
        self.bg_task = bot.loop.create_task(self.drop_present_task())

    def __unload(self):
        self.bg_task.cancel()

    async def drop_present_task(self):
        await self.bot.wait_until_ready()
        try:
            while not self.bot.is_closed():
                if random.random() <= 0.015:
                    await self.drop_present()
                await asyncio.sleep(60)
        except Exception as e:
            log.error(e)

    async def drop_present(self, channel=None):
        ch = self.bot.get_channel(channel or 215424443005009920)

        emb = discord.Embed(color=discord.Color(0xFFA4C4))
        emb.add_field(name='💖 A lewd care package has dropped.',
                      value="React with 💖 to claim your share.")
        msg = await ch.send(embed=emb)
        await msg.add_reaction('💖')

        end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.randint(10, 30))

        claimed = []

        for i in range(20):
            try:
                reaction, user = await self.bot.wait_for('reaction_add', check=lambda r, u: u.id != self.bot.user.id and
                                                                                            r.message.id == msg.id,
                                                         timeout=(end_time - datetime.datetime.now()).total_seconds())
                if user.id in claimed:
                    continue
                claimed += [user.id]
            except asyncio.TimeoutError:
                break

        if claimed:
            share = ' and '.join(', '.join([f'<@{uid}>' for uid in claimed]).rsplit(', ', 1))
            emb = discord.Embed(color=discord.Color(0xFFA4C4))
            emb.add_field(name=f'The care package has been emptied out.', value=f'{share} took their share.')
            await ch.send(embed=emb)
        else:
            emb = discord.Embed(color=discord.Color(0xFFA4C4), title="The care package despawned before anyone could take a share..")
            await ch.send(embed=emb)
            return

        for user_id in claimed:
            try:
                user = self.bot.get_user(user_id)
                if user is None:
                    continue

                rand = random.random()

                if rand < .90:  # Half daily
                    async with self.economy.transaction(user_id) as profile:
                        amount = int(random.randint(1, 3) * (1 + .2 * (profile.level // 5)) * self.economy.gold_rate)

                        if rand < .25:  # Double
                            amount *= 2
                        profile.coins += amount
                    await user.send(f"Your share contained {amount} gold!")

                else:  # 12-25 gold
                    async with self.economy.transaction(user_id) as profile:
                        amount = random.randint(12, 25)
                        profile.coins += amount
                    await user.send(f"Your share contained {amount} gold!")
            except Exception as e:
                print(f'Fucksywucksy', file=sys.stderr)
                print(e, file=sys.stderr)

    @commands.command(hidden=True)
    @commands.has_role('Staff')
    async def droppresent(self, ctx, channel: int =None):
        await self.drop_present(channel)

def setup(bot):
    bot.add_cog(Drops(bot))
