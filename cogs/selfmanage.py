import asyncio
import traceback

import discord
import datetime
from discord.ext import commands

from cogs.utils.cooldowns import basic_cooldown


def get_color_role(member):
    for role in member.roles:
        if role.color == member.color:
            return role

GUILD_ID = 215424443005009920

base_colors = [
     ("Red", 424579184216506368, 30),
     ("Yellow", 424579315066208276, 30),
     ("Green", 424579385983762432, 30),
     ("Orange", 424579446578872332, 30),
     ("Cyan", 424579523363733507, 30),
     ("Blue", 424579641802752000, 30),
     ("Purple", 424579707573633024, 30),
     ("Pink", 424579770240466951, 30),
     ("Charcoal", 424579833994149888, 30),
     ("Light Grey", 488187345565122565, 30),
 ]


class Selfmanage(commands.Cog):
    """A cog for managing yourself"""

    all_roles = [
        353019520983629824, 347689132908085248, 371251751564869632,
        373135777955315712, 373135762230607882, 389376686745059329
    ]
    legal = "Welcome to Waifu Worshipping, the home of all your lewd socialising needs! " \
            "Please make sure to read over #information and #rules to learn the essentials.\n" \
            "Also understand that due to the content of the server, all users are required to be over the age of 18.\n"\
            "By continuing with these questions, you confirm that you are of legal age.\n\n" \
            "**When you're ready to receive your roles, please reply with the following: **`begin`"
    questions = [
        ('Are you happy to receive messages from other users in the server?', 353019520983629824),
        ('Are you interested in being informed about all future server-wide events? (Movie nights, gaming events, and other fun activities)', 347689132908085248),
        ('Are you interested in seeing NSFW content?', 371251751564869632),
        ('Are you interested in roleplay channels?', 389376686745059329)
    ]

    def __init__(self, bot):
        self.bot = bot
        self.active_intros = []
        self.profiles = bot.get_cog("Economy")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id == GUILD_ID:
            try:
                msg = await self.bot.wait_for('message', check=lambda m: m.author.id == member.id, timeout=300)
                if 'intro' in msg.content:
                    return
            except asyncio.TimeoutError:
                pass
            await self.questionare(member.guild, member)

    @commands.command()
    async def intro(self, ctx):
        if ctx.author.id in self.active_intros:
            return await ctx.send("You're already doing the intro.")
        guild = self.bot.get_guild(GUILD_ID) or ctx.guild
        if not guild:
            return
        if ctx.guild:
            await ctx.send(f'{ctx.author.mention} I sent you a DM!')
        await self.questionare(guild, guild.get_member(ctx.author.id))

    async def questionare(self, guild, member):
        if member.id in self.active_intros:
            return
        else:
            try:
                await member.send(self.legal)
            except discord.errors.Forbidden:
                return
            self.active_intros += [member.id]
        roles_to_add = []

        fresh = discord.utils.get(member.roles, id=373122164544765953) is None

        try:
            await self.bot.wait_for('message', check=lambda m: m.content.lower() == 'begin' and m.author == member, timeout=300)
            for question, role in self.questions:
                if await self.ask_question(member, question):
                    roles_to_add.append(discord.utils.get(guild.roles, id=role))

            # If the user hasn't claimed a free color
            if not await self.bot.redis.exists(f"claimedcolor:{member.id}"):
                if await self.ask_question(member, 'Would you like a colored name for on the server?'):
                    owned = [r[0] for r in await self.bot.db.fetch(f'SELECT color FROM colors WHERE user_id={member.id}')]
                    await member.send("Which of the following colors would you like?\n"
                                      f"{', '.join([i[0] for i in base_colors])} or `none`")
                    c = await self.bot.wait_for('message', check=lambda m: m.author.id == member.id and m.guild is None,
                                                timeout=120)
                    for name, color_code, price in base_colors:
                        if c.content.lower() == name.lower() and color_code not in owned:
                            await self.bot.db.execute(f"INSERT INTO colors (user_id, color) VALUES ({member.id}, {color_code})")
                            await self.bot.redis.set(f"claimedcolor:{member.id}", f"{name}")
                            roles_to_add.append(discord.utils.get(guild.roles, id=color_code))
                            break
        except asyncio.TimeoutError:
            try:
                await member.send('Sorry, you took too long to answer. Use `~intro` if you want to start over.')
            except discord.errors.Forbidden:
                pass
            self.active_intros.remove(member.id)
        else:
            try:
                roles_to_add.append(discord.utils.get(guild.roles, id=373122164544765953))
                await member.send("Please give me a few seconds to finalize everything.")
                await member.remove_roles(*[discord.utils.get(guild.roles, id=x) for x in self.all_roles])
                await member.add_roles(*roles_to_add)
                await member.send('Thank you for answering, the appropriate roles have been assigned to you! If there are any issues, please contact a staff member and they will happily assist you.')
                if fresh:
                    monitorlog = self.bot.get_cog('Monitor')
                    await monitorlog.post_member_log(member)
            except Exception as e:
                traceback.print_tb(e.__traceback__)
            self.active_intros.remove(member.id)
    @commands.command()
    async def welcome_image(self, member=None):
        general = self.bot.get_channel(501064326786973699)
        embed = discord.Embed(title=f"Welcome {member.author}", colour=discord.Colour(0xcc49e7))

        embed.set_image(url="https://media.giphy.com/media/bcKmIWkUMCjVm/giphy.gif")
        # embed.set_footer(text=f"Joined at: {datetime.datetime.now().time()}", icon_url=f"{member.author.avatar_url}")
        await general.send(embed = embed)

    async def ask_question(self, user, question):
        def check(m):
            return isinstance(m.channel, discord.DMChannel) and m.author == user and is_answer(m.content)

        def is_answer(c):
            return 'y' in c.lower() or 'n' in c.lower()

        await user.send(question+' `yes / no`')

        m = await self.bot.wait_for('message', check=check, timeout=120)
        if 'y' in m.content.lower():
            await m.add_reaction('✅')
            return True
        else:
            return False

    @commands.command(aliases=['tributes'], hidden=True)
    @commands.guild_only()
    @basic_cooldown(60)
    async def tribute(self, ctx):
        rolename = "Tributes"
        if discord.utils.get(ctx.author.roles, name=rolename) is None:
            await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, name=rolename))
            await ctx.send(f'I gave you the {rolename} role.')
        else:
            await ctx.author.remove_roles(discord.utils.get(ctx.guild.roles, name=rolename))
            await ctx.send(f'I removed your {rolename} role.')

    @commands.command(hidden=True)
    @commands.guild_only()
    @basic_cooldown(60)
    async def pokemon(self, ctx):
        rolename = "Pokemon"
        if discord.utils.get(ctx.author.roles, name=rolename) is None:
            await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, name=rolename))
            await ctx.send(f'I gave you the {rolename} role.')
        else:
            await ctx.author.remove_roles(discord.utils.get(ctx.guild.roles, name=rolename))
            await ctx.send(f'I removed your {rolename} role.')


def setup(bot):
    bot.add_cog(Selfmanage(bot))
