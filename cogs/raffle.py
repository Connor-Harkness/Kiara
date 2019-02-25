import asyncio
import datetime
import random

import discord
from discord.ext import commands


def custom_format(td):
    minutes, seconds = divmod(td.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return '{:d}:{:02d}'.format(hours, minutes)


class Raffle(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.profiles = bot.get_cog("Economy")
        self.raffle_channel = None
        self.alt_raffle_channel = None
        self.raffles = []
        self.bg_task = bot.loop.create_task(self.raffle_interval())

    def __unload(self):
        self.bg_task.cancel()

    async def raffle_interval(self):
        await self.bot.wait_until_ready()
        # Load the channel and raffles from redis
        self.raffle_channel = self.bot.get_channel(467614160251912193)
        self.alt_raffle_channel = self.bot.get_channel(508287405061701633)
        self.raffles = await self.bot.redis.keys('raffle:*', encoding='utf8')
        try:
            while not self.bot.is_closed():
                self.raffles = await self.bot.redis.keys('raffle:*', encoding='utf8')
                for key in self.raffles:
                    message_id = int(key.split(':')[1])
                    await self.update_raffle(message_id)
                    await asyncio.sleep(5)
                await asyncio.sleep(60)
        except Exception as e:
            print(e)

    async def update_raffle(self, message_id):
        try:
            message = await self.raffle_channel.get_message(message_id)
        except discord.NotFound:
            try:
                message = await self.alt_raffle_channel.get_message(message_id)
            except discord.NotFound:
                # Message was deleted
                return await self.bot.redis.delete(f'raffle:{message_id}')

        end = await self.bot.redis.hget(f'raffle:{message_id}', 'end', encoding='utf8')
        end = datetime.datetime.utcfromtimestamp(int(end))

        num_winners = int(await self.bot.redis.hget(f'raffle:{message_id}', 'winners', encoding='utf8') or 1)

        if datetime.datetime.utcnow() >= end:
            winners = []
            entries = await self.bot.redis.lrange(f'raffle_entries:{message_id}', 0, -1, encoding='utf8') or ['???']
            for x in range(num_winners):
                for i in range(20):
                    winner = random.choice(entries)
                    if winner in winners:
                        continue
                    if self.bot.get_user(int(winner)):
                        winners += [winner]
                        break

            await message.edit(embed=await self.generate_end_embed(message_id, winners))
            await self.bot.redis.delete(f'raffle:{message_id}')
        else:
            await message.edit(embed=await self.generate_embed(message_id))

    @commands.has_role('Staff')
    @commands.command()
    async def createraffle(self, ctx, cost: int, hours: int, winners: int, *, reward):
        if ctx.channel not in [self.raffle_channel, self.alt_raffle_channel]:
            return await ctx.send("Use this in one of the raffle channels")
        await ctx.message.delete()
        message = await ctx.send('setting up raffle..')
        await message.add_reaction('💎')

        raffle_id = await self.bot.redis.incr('rafflecount')
        endtime = datetime.datetime.utcnow() + datetime.timedelta(hours=hours)
        await self.bot.redis.hmset(f'raffle:{message.id}', 'raffle_id', raffle_id, 'cost', cost, 'reward', reward,
                                   'winners', winners,
                                   'end', round((endtime - datetime.datetime(1970, 1, 1)).total_seconds()))

        await message.edit(content=None, embed=await self.generate_embed(message.id))
        self.raffles = await self.bot.redis.keys('raffle:*', encoding='utf8')

    @commands.has_role('Staff')
    @commands.command()
    async def clearraffles(self, ctx):
        await ctx.redis.delete(*await self.bot.redis.keys('raffle:*'))

    async def generate_embed(self, message_id):
        # fetch raffle info
        raffle_id, reward, cost, end = await self.bot.redis.hmget(f'raffle:{message_id}', 'raffle_id', 'reward', 'cost',
                                                                  'end', encoding='utf8')
        num_entries = await self.bot.redis.llen(f'raffle_entries:{message_id}')
        embed = discord.Embed(title=f"Raffle #{raffle_id} | Enter by reacting with 💎")
        embed.colour = 0x33cccc
        embed.add_field(name='Prize', value=str(reward or '?'))
        embed.add_field(name='Entry cost', value=str(cost or '?')+'g')
        embed.add_field(name='Entries', value=num_entries)
        # embed.add_field(name='Latest entries', value=f"", inline=False)
        embed.timestamp = datetime.datetime.utcfromtimestamp(float(end))
        embed.set_footer(text=f'⏰ Ends in {custom_format(datetime.datetime.utcfromtimestamp(float(end))-datetime.datetime.utcnow())} at')
        return embed

    async def generate_end_embed(self, message_id, winners):
        # fetch raffle info
        raffle_id, reward, cost, end = await self.bot.redis.hmget(f'raffle:{message_id}', 'raffle_id', 'reward', 'cost',
                                                                  'end', encoding='utf8')
        num_entries = await self.bot.redis.llen(f'raffle_entries:{message_id}')
        embed = discord.Embed(title=f"Raffle #{raffle_id}")
        embed.colour = 0xf25e9d
        embed.add_field(name='Prize', value=str(reward or '?'))
        embed.add_field(name='Entry cost', value=str(cost or '?')+'g')
        embed.add_field(name='Entries', value=num_entries)
        winners = [f"<@{winner}> {self.bot.get_user(int(winner))}" for winner in winners]
        embed.add_field(name='Winners' if len(winners)>1 else "Winner", value='\n'.join(winners), inline=False)
        embed.timestamp = datetime.datetime.utcfromtimestamp(float(end))
        embed.set_footer(text=f'⏰ Ended')
        return embed

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        if payload.channel_id not in [self.raffle_channel.id, self.alt_raffle_channel.id]:
            return
        if str(payload.emoji) != '💎':
            return

        # Get the entry cost, and also if a raffle exists in the first place
        cost, prize = await self.bot.redis.hmget(f'raffle:{payload.message_id}', 'cost', 'reward', encoding='utf8')
        if cost is None:
            return
        cost = int(cost)

        user = self.bot.get_user(payload.user_id)

        # Check if the user already entered
        if str(payload.user_id) in await self.bot.redis.lrange(f'raffle_entries:{payload.message_id}', 0, -1, encoding='utf8'):
            return await user.send("You already entered that raffle.")

        async with self.profiles.get_lock(payload.user_id):
            # Check if the user has enough gold
            profile = await self.profiles.get_profile(payload.user_id, ('coins',))
            if profile.coins < int(cost):
                return await user.send(f"Sorry, it costs {cost}g to enter for `{prize}`. You only have {profile.coins}g.")
            profile.coins -= int(cost)
            await profile.save()

        await self.bot.redis.rpush(f'raffle_entries:{payload.message_id}', payload.user_id)
        await self.update_raffle(payload.message_id)
        await user.send(f"Thanks! You've entered the `{prize}` raffle for {cost}g.")


def setup(bot):
    bot.add_cog(Raffle(bot))
