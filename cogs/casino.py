import random

import discord
from discord.ext import commands

from cogs.utils.cooldowns import basic_cooldown

class Fruit:
    __slots__ = ('name', 'weight', 'payout')

    def __init__(self, name, weight, payout):
        self.name = name
        self.weight = weight
        self.payout = payout

class Slotmachine:
    lines = [
        (1, 1, 1, 1, 1),  # mid
        (0, 0, 0, 0, 0),  # top
        (2, 2, 2, 2, 2),  # bot
        (0, 1, 2, 1, 0),  # zigzoggle
        (2, 1, 0, 1, 2),  # zigzoggle inv
        (1, 0, 0, 0, 1),  # bridge top
        (1, 2, 2, 2, 1),  # bridge inv
        (0, 0, 1, 2, 2),  #
        (2, 2, 1, 0, 0),  #
        (1, 0, 1, 2, 1),  #
        (1, 2, 1, 0, 1),  #
    ]
    def __init__(self):
        self.reels = [[], [], [], [], []]
        self.fruits = [
            Fruit('🍐', (12, 13, 10, 10, 12), (0, 1, 5, 10, 20)),
            Fruit('🍌', (8, 7, 9, 9, 8), (0, 2, 10, 25, 50)),
            Fruit('🍇', (5, 6, 6, 6, 5), (0, 4, 10, 100, 200)),
            Fruit('🍉', (4, 4, 3, 4, 3), (0, 10, 100, 1000, 2500)),
            Fruit('🍰', (2, 1, 3, 2, 3), (0, 65, 250, 2500, 5000)),
            Fruit('💎', (1, 1, 1, 1, 1), (0, 100, 1000, 10000, 100000)),
        ]
        for i, fruit in enumerate(self.fruits):
            for r in range(5):
                self.reels[r] += [i]*fruit.weight[r]
        self.outcome = self.shuffle()

    def shuffle(self):
        for reel in self.reels:
            random.shuffle(reel)
        self.outcome = [reel[:3] for reel in self.reels]
        return self.outcome

    def get_representation(self):
        return '\n'.join([''.join([self.fruits[self.outcome[slot][row]].name for slot in range(5)]) for row in range(3)])

    def get_wins(self, lines=1):
        winnings = []
        total = 0
        for line in self.lines[:lines]:
            first = self.outcome[0][line[0]]
            for i, col in enumerate(line):
                if i == 4:
                    continue
                if self.outcome[i+1][col] != first:
                    break
            print("Total images =", i+1)
            if i > 0:
                total += self.fruits[first].payout[i]
                winnings += [f"You got {self.fruits[first].name} x{i+1} which is {self.fruits[first].payout[i]}"]
        return total, winnings

class Casino(commands.Cog):
    """Temporary casino so you can start gambling"""

    def __init__(self, bot):
        self.bot = bot
        self.profiles = bot.get_cog("Economy")

    @commands.command(aliases=['cf'])
    async def coinflip(self, ctx, amount: int, choice=None):
        """Bet some money on flipping a coin"""
        if amount <= 0:
            return await ctx.send("Please bet more than 0")
        if choice:
            if choice.lower() not in ['heads', 'tails']:
                return await ctx.send("Please pick either `heads` or `tails`.")
        else:
            choice = 'heads'

        profile = await self.profiles.get_profile(ctx.author.id, ('coins',))
        if profile.coins < amount:
            return await ctx.send("You don't have enough gold to bet that much.")

        win = random.choice(['heads', 'tails'])
        emote = '<:aa:474567347588431893>' if win == 'tails' else '<:aa:474567346833588244>'

        async with self.profiles.get_lock(ctx.author.id):
            profile = await self.profiles.get_profile(ctx.author.id, ('coins',))

            if win == choice.lower():
                await ctx.send(f"The coin landed on {win}. {emote}\nCongrats you won {amount} gold.")
                profile.coins += amount
            else:
                await ctx.send(f"The coin landed on {win}. {emote}\nSorry, you lost {amount} gold")
                profile.coins -= amount
            await profile.save()

    @commands.command()
    async def russianroulette(self, ctx, *participants: discord.Member):
        """Play an innocent game of russian roulette. Winner dies."""
        chamber = [0, 0, 0, 0, 0, 1]
        random.shuffle(chamber)
        participants = list(participants)
        random.shuffle(participants)
        for i, b in enumerate(chamber):
            current = participants[i % len(participants)]
            await ctx.send(embed=discord.Embed(description=f"{current} is next, type `shoot` or literally anything else"))
            msg = await self.bot.wait_for('message', check=lambda m: m.author in participants)
            if b:
                await ctx.send(embed=discord.Embed(description=f"{current} lost"))
                break
            else:
                await ctx.send(embed=discord.Embed(description="Lucky"))

    @commands.command(aliases=['roulette', 'spin'])
    async def classicroulette(self, ctx, amount:int, choice):

        roulette = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14]
        spinemotes = [
        '<:r0:451726112423149568>', '<:r1:451726112381206538>','<:r2:451726112238600202>', '<:r3:451726112343719937>',
        '<:r4:451726111643140109>', '<:r5:451726112201113620>', '<:r6:451726112213696512>',
        '<:r7:451726112163102731>', '<:r8:451726112314097704>', '<:r9:451726111949193219>', '<:r10:451726112100450305>',
        '<:r11:451726111970295809>', '<:r12:451726112284868618>', '<:r13:451726112414892032>', '<:r14:451726112343588864>'
        ]
        pointer = ['<:line:451728056764334081>', '<:arrowup:451727652219518986>']

        colors = ['red', 'black', 'green']

        if amount<=0:
            return await ctx.send("Please bet more than 0")
        if choice:
            if choice.lower() not in colors:
                return await ctx.send("Please specify the color you wish to bet on. These are red, black, or green.")

        profile = await self.profiles.get_profile(ctx.author.id, ('coins',))
        if profile.coins < amount:
            return await ctx.send("You don't have enough gold to bet that much.")

        hit = random.choice(roulette)
        val1 = ((hit-1) % len(roulette))
        val3 = ((hit+1) % len(roulette))

        hitcolor = None
        if hit == 0:
            hitcolor = 'green'

        elif (hit % 2) == 0:
            hitcolor = 'red'

        elif (hit % 2) > 0:
            hitcolor = 'black'

        async with self.profiles.get_lock(ctx.author.id):
            profile = await self.profiles.get_profile(ctx.author.id, ('coins',))
            if hitcolor != None:
                if hitcolor == choice.lower():
                    if choice.lower() == "green":
                        await ctx.send(f"{spinemotes[val1]} {spinemotes[hit]} {spinemotes[val3]}\n"
                                       f"{pointer[0]} {pointer[1]} {pointer[0]}\n"
                                       f"It landed on {hitcolor}! You win {amount*15} gold!")
                        profile.coins += (amount*15)

                    else:
                        await ctx.send(f"{spinemotes[val1]} {spinemotes[hit]} {spinemotes[val3]}\n"
                                       f"{pointer[0]} {pointer[1]} {pointer[0]}\n"
                                       f"The roulette landed on {hit}! You bet on {hitcolor}, you win {amount} gold!")
                        profile.coins += (amount)

                else:
                    await ctx.send(f"{spinemotes[val1]} {spinemotes[hit]} {spinemotes[val3]}\n"
                                   f"{pointer[0]} {pointer[1]} {pointer[0]}\n"
                                   f"The roulette landed on {hit} which is {hitcolor}! Sorry, you lose {amount} gold.")
                    profile.coins -= amount

            await profile.save()

    @commands.command(enabled=False, aliases=['slots'])
    async def slotmachine(self, ctx, bet_per_line: int = 1, lines: int = 1):
        """Spin the slotmachine"""
        if discord.utils.get(ctx.author.roles, name="Staff") is None:
            lines = 1
        if bet_per_line <= 0:
            return await ctx.send("Please bet more than 0")
        if lines <= 0:
            return await ctx.send("Please bet on more than one line")

        async with self.profiles.transaction(ctx.author.id) as profile:
            if profile.coins < bet_per_line*lines:
                return await ctx.send("You don't have enough gold")

            profile.coins -= bet_per_line*lines

            slotmachine = Slotmachine()
            total, info = slotmachine.get_wins(lines)
            if total > 0:
                profile.coins += total*bet_per_line

        await ctx.send(slotmachine.get_representation(),
                       embed=discord.Embed(description='\n'.join(info)+f"\nTotal gain: {bet_per_line*total-bet_per_line*lines}"))


def setup(bot):
    bot.add_cog(Casino(bot))
