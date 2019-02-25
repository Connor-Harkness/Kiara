import random
import datetime

import discord
from discord.ext import commands

from cogs.utils.cooldowns import basic_cooldown


class Mansion(commands.Cog):
    """Spooky"""

    def __init__(self, bot):
        self.bot = bot

    @basic_cooldown(86400)  # 24 hours
    @commands.guild_only()
    @commands.command()
    async def investigate(self, ctx):
        profiles = self.bot.get_cog("Profiles")
        em = discord.Embed()
        em.set_footer(text=f"@{ctx.author}")
        rand = random.random()
        if rand < 0.5:  # Mid tier reward(50%)
            msg = "*After working your way through most of the mansion, you stumble across... " \
                  "A handful of old, dusty trinkets. Maybe they're worth something...*\n" \
                  "**+15 Gold**"
            async with profiles.get_lock(ctx.author.id):
                profile = await profiles.get_profile(ctx.author.id, ('coins',))
                profile.coins += 15
                await profile.save(self.bot.db)
        elif rand < 0.8:  # Low tier reward (30%)
            msg = "*After absentmindedly investigating a few places around the mansion, you stumble across... " \
                  "A few coins... Riveting.*\n" \
                  "**+5 Gold**"
            async with profiles.get_lock(ctx.author.id):
                profile = await profiles.get_profile(ctx.author.id, ('coins',))
                profile.coins += 5
                await profile.save(self.bot.db)
        elif rand < 0.95:  # High tier reward (15%)
            msg = "*After some hours of meticulously searching through every room and drawer, you stumble across... " \
                  "A heavy bag, filled with golden coins and shiny gemstones...*\n" \
                  "**+50 gold**"
            async with profiles.get_lock(ctx.author.id):
                profile = await profiles.get_profile(ctx.author.id, ('coins',))
                profile.coins += 50
                await profile.save(self.bot.db)
        else:  # Ghost tier (5%)
            msg = "*You work late into the night rummaging throughout the mansion, unable to sate your curiosity. " \
                  "Finally, you arrive at the attic. The room is small and cramped, with random objects and loose " \
                  "papers being more visible than the old carpet. Two bookshelves line the walls to the left and " \
                  "right, and directly ahead sits a long desk, with a large arching window behind for a nice view. " \
                  "As you continue climbing up the ladder, a glimmer of light catches your attention. At first, you " \
                  "mistake it for the bright full moon, shining through the window, and look away. However, the " \
                  "light catches your attention again. You focus on the window for a moment, and manage to make out " \
                  "the faint form of... A ghost? The creature returns your gaze, and quickly notices it has been " \
                  "seen. Without a pause, it floats through a wall, and is suddenly gone.\nYou collect your thoughts " \
                  "and head over to the desk. On it, you find a white, transparent object, shaped almost like a " \
                  "tear. The colour and transparency distinctly remind you of the creature you just saw. Maybe you " \
                  "will find a use for this later...*\n" \
                  "**+1 Ghost Droplet**"
            await self.bot.db.execute("INSERT INTO inventory (user_id, item_id) VALUES (%s, %s)",
                                      (ctx.author.id, 1))
            em.colour = 0x4fbbff
        em.description = msg
        await ctx.send(embed=em)

    @investigate.error
    async def investigate_error(self, ctx, error):
        m, s = divmod(error.retry_after, 60)
        h, m = divmod(m, 60)

        t = f"{h:.0f} hour(s)" if h else f"{m:.0f} minute(s) and {s:.0f} second(s)" if m else f"{s:.0f} second(s)"
        msg = "There's nothing to investigate at the moment.\nTry again in " + t

        await ctx.send(msg)

def setup(bot):
    bot.add_cog(Mansion(bot))
