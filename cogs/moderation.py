import datetime

from io import BytesIO

from .utils import time
from discord.ext import commands
import parsedatetime as pdt
import asyncio
import discord
import random


STAFF_CHANNEL = 231008480079642625
MUTED_ROLE = 348331525479071745
BUMP_CHANNEL = 407581915726610443


def get_date(text):
    cal = pdt.Calendar()
    time, res = cal.parseDT(text, datetime.datetime.utcnow())
    return time if res else None


class MemberID(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            m = await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                return int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(f"{argument} is not a valid member or member ID.") from None
        else:
            can_execute = ctx.author.id == ctx.bot.owner_id or \
                          ctx.author == ctx.guild.owner or \
                          ctx.author.top_role > m.top_role

            if not can_execute:
                raise commands.BadArgument('You cannot do this action on this user due to role hierarchy.')
            return m.id


class IDConverter(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            m = await commands.MemberConverter().convert(ctx, argument)
            return m.id
        except commands.BadArgument:
            try:
                return int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(f"{argument} is not a valid member or member ID.") from None


class BannedMember(commands.Converter):
    async def convert(self, ctx, argument):
        ban_list = await ctx.guild.bans()
        try:
            member_id = int(argument, base=10)
            entity = discord.utils.find(lambda u: u.user.id == member_id, ban_list)
        except ValueError:
            entity = discord.utils.find(lambda u: str(u.user) == argument, ban_list)

        if entity is None:
            raise commands.BadArgument("Not a valid previously-banned member.")
        return entity


class Moderation(commands.Cog):
    """Moderation commands"""

    def __init__(self, bot):
        self.bot = bot
        self.timers = bot.get_cog('Timers')
        self.stafflog = bot.get_cog('Stafflog')

    async def get_recent_warns(self, user_id):
        qry = 'SELECT * FROM warns ' \
              'WHERE user_id=%s AND date > (%s)'
        warns = await self.bot.db.fetchdicts(qry, (user_id, datetime.datetime.utcnow()-datetime.timedelta(days=30)))
        return warns

    async def get_all_warns(self, user_id):
        qry = 'SELECT * FROM warns ' \
              'WHERE user_id=%s'
        warns = await self.bot.db.fetchdicts(qry, (user_id,))
        return warns

    @commands.command()
    @commands.has_any_role('Staff')
    async def kick(self, ctx, member: MemberID, *, reason=None):
        """Kick a user."""
        permissions = ctx.channel.permissions_for(ctx.author)
        if getattr(permissions, 'kick_members', None):
            try:
                await ctx.guild.kick(discord.Object(id=member), reason=reason)
                member = await self.bot.get_user_info(member)
                await ctx.send(f'Kicked {member}!')
            except Exception as e:
                await ctx.send(e)
        else:
            ch = self.bot.get_channel(STAFF_CHANNEL)
            await ch.send(f"<@&293008190843387911> {ctx.author.mention} requests kicking {member.mention}.")
            await ctx.send('Your kick request has been received.')

    @commands.command()
    @commands.has_any_role('Staff')
    async def ban(self, ctx, member: MemberID, *, reason=None):
        """Ban a user."""
        permissions = ctx.channel.permissions_for(ctx.author)
        if getattr(permissions, 'ban_members', None):
            try:
                await ctx.guild.ban(discord.Object(id=member), reason=f"{ctx.author}: {reason}" if reason else None)
                member = await self.bot.get_user_info(member)
                await ctx.send(f'Banned {member}!')
            except Exception as e:
                await ctx.send(e)
        else:
            ch = self.bot.get_channel(STAFF_CHANNEL)
            member = await self.bot.get_user_info(member)
            await ch.send(f"<@&293008190843387911> {ctx.author.mention} requests banning {member.mention}.")
            await ctx.send('Your ban request has been received.')

    @commands.command(aliases=['multiban'])
    @commands.has_any_role('Staff')
    async def massban(self, ctx, *members: MemberID):
        """Mass ban a ton of users at once.
        Using user ids is recommended."""
        permissions = ctx.channel.permissions_for(ctx.author)
        if getattr(permissions, 'ban_members', None):
            for member in members:
                try:
                    await ctx.guild.ban(discord.Object(id=member), reason="Mass ban")
                    member = await self.bot.get_user_info(member)
                    await ctx.send(f'Banned {member}!')
                except Exception as e:
                    await ctx.send(e)
        else:
            ch = self.bot.get_channel(STAFF_CHANNEL)
            await ch.send(f"<@&293008190843387911> {ctx.author.mention} requests mass banning {' '.join(members)}.")

    @commands.command()
    @commands.has_any_role('Staff')
    async def unban(self, ctx, member: BannedMember, *, reason=None):
        """Unban a user."""
        permissions = ctx.channel.permissions_for(ctx.author)
        if getattr(permissions, 'ban_members', None):
            try:
                await ctx.guild.unban(member.user, reason=reason)
                await ctx.send(f'Unbanned {member.user}!')
            except Exception as e:
                await ctx.send(e)
        else:
            ch = self.bot.get_channel(STAFF_CHANNEL)
            await ch.send(f"{ctx.author.mention} requests unbanning {member.user.mention}.")
            await ctx.send('Your uban request has been received.')

    async def mute_user_id(self, user_id, minutes, reason):
        guild = self.bot.get_guild(215424443005009920)
        member = guild.get_member(user_id)

        if member is None:
            return False

        await member.add_roles(discord.utils.get(guild.roles, id=MUTED_ROLE))
        await self.timers.create_timer('unmute', datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes),
                                       [guild.id, member.id])
        # await self.stafflog.make_case(member, f'Mute ({minutes} minute{"s" if minutes!=1 else ""})', reason, 'Kiara')

    @commands.command()
    @commands.has_role('Staff')
    async def mute(self, ctx, member: discord.Member, minutes: int = 5, *, reason=None):
        """Mute a user.
        Defaults to 5 minutes."""
        await member.add_roles(discord.utils.get(ctx.guild.roles, id=MUTED_ROLE))
        await self.timers.create_timer('unmute', datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes),
                                       [ctx.guild.id, member.id])
        await self.stafflog.make_case(member, f'Mute ({minutes} minute{"s" if minutes!=1 else ""})', reason, ctx.author)

    @commands.Cog.listener()
    async def on_unmute_event(self, guild_id, user_id):
        guild = self.bot.get_guild(guild_id)
        member = guild.get_member(user_id)
        await member.remove_roles(discord.utils.get(guild.roles, id=MUTED_ROLE))

    @commands.command(aliases=['finduser'])
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    async def userfind(self, ctx, *, search):
        found = []

        if not ctx.guild.chunked:
            await self.bot.request_offline_members(ctx.guild)

        for m in ctx.guild.members:
            if search.lower() in m.name.lower():
                found += [m]
        if found:
            await ctx.send('Matches users:```\n'+'\n'.join([f'{m} ({m.id})' for m in found])+'```')
        else:
            await ctx.send('Found nothing')

    @commands.command(aliases=['newmembers'])
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    async def newusers(self, ctx, *, count=5):
        """Tells you the newest members of the server.
        This is useful to check if any suspicious members have
        joined.
        The count parameter can only be up to 25.
        """
        count = max(min(count, 25), 5)

        if not ctx.guild.chunked:
            await self.bot.request_offline_members(ctx.guild)

        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)[:count]

        e = discord.Embed(title='New Members', colour=discord.Colour.green())

        for member in members:
            body = f'joined {time.time_ago(member.joined_at)}, created {time.time_ago(member.created_at)}'
            e.add_field(name=f'{member} (ID: {member.id})', value=body, inline=False)

        await ctx.send(embed=e)

    @commands.command(aliases=['infouser'])
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    async def userinfo(self, ctx, *, member: IDConverter):
        try:
            member = ctx.guild.get_member(member) or await self.bot.get_user_info(member)
        except discord.NotFound:
            return await ctx.send("Unknown user")

        if member.id == 73389450113069056:
            member.joined_at = ctx.guild.created_at
        if member.id == 129034173305454593:
            member.joined_at = datetime.datetime(2017, 9, 3, 8, 48)

        e = discord.Embed(title=f'{member} (ID: {member.id})', colour=discord.Colour.green())
        e.set_thumbnail(url=member.avatar_url_as(size=128))
        e.add_field(name=f'Created', value=time.time_ago(member.created_at), inline=True)
        if isinstance(member, discord.Member):
            e.add_field(name=f'Joined', value=time.time_ago(member.joined_at), inline=True)
            e.add_field(name=f'Nickname', value=member.nick or "None", inline=False)
            e.add_field(name=f'Roles', value=' '.join([role.mention for role in member.roles[1:]]) or "None", inline=False)
        warns = await self.get_recent_warns(member.id)
        if warns:
            e.add_field(name=f'Recent warnings', value='\n'.join([f"- {warn['reason']}" for warn in warns]) or "None", inline=False)
        await ctx.send(embed=e)

    @commands.command(aliases=['bumped'])
    @commands.has_role('Staff')
    async def bump(self, ctx, *, time_till_bump='5h 59m'):
        """Tell kiara you bumped the server so she can remind you.
        Defaults to 6 hours if you leave the time out.

        You can copy the exact time as shown on discord.me as time input, for example:
        ~bump 4h 21m 54s
        """
        t = get_date(time_till_bump)
        if t:
            await self.timers.create_timer('bumpreminder', t)
            await ctx.send(f'Bump reminder set for {t} (UTC) <a:twitch:406319471272263681>')
        else:
            await ctx.send(f'Please supply a better time format.')

    @commands.Cog.listener()
    async def on_bumpreminder_event(self):
        ch = self.bot.get_channel(BUMP_CHANNEL)
        e = discord.Embed(title="Server can be bumped!", colour=discord.Colour.purple(),
                          description=f'Click [here](https://discord.me/server/bump-servers/8742) for the bump page!')
        e.timestamp = datetime.datetime.utcnow()
        await ch.send(f"<@&407767148660916227>", embed=e)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def say(self, ctx, *, msg=None):
        """Make Kiara say something."""
        if ctx.message.attachments:
            file = BytesIO()
            att = ctx.message.attachments[0]
            await att.save(file)
            file.seek(0)
            await ctx.send(msg, file=discord.File(file, filename=att.filename))
        else:
            await ctx.send(msg)
        await ctx.message.delete()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def edit(self, ctx, message_id, *, msg=None):
        """Edit one of Kiara's old messages.
        Doesn't support images."""
        message = await ctx.channel.get_message(message_id)
        await message.edit(content=msg)
        await ctx.message.delete()

    @commands.command(aliases=['dm'])
    @commands.has_permissions(administrator=True)
    async def message(self, ctx, user: discord.User, *, msg=None):
        """Make Kiara message a user."""
        try:
            await user.send(msg)
            await ctx.send(f"Message sent to {user.mention}!")
        except discord.Forbidden:
            await ctx.send("The user has DMs disabled.")


    @commands.group(invoke_without_command=True, aliases=['purge'])
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 10):
        """Clear messages in a channel"""
        amount = max(1, min(amount, 50))
        messages = await ctx.channel.history(limit=amount+1).flatten()
        await ctx.channel.delete_messages(messages)
        await ctx.send(f'Deleted {len(messages)} messages', delete_after=4)

    @clear.command(name="member", aliases=['user'])
    @commands.has_permissions(manage_messages=True)
    async def clear_member(self, ctx, member: discord.Member, amount: int = 10):
        """Clear messages from a specific user"""
        messages = await ctx.channel.history(limit=amount+1).filter(lambda m: m.author.id==member.id).flatten()

        await ctx.channel.delete_messages(messages)
        await ctx.send(f'Deleted {len(messages)} messages', delete_after=4)

    @clear.command(name="nonimage", aliases=['text'])
    @commands.has_permissions(manage_messages=True)
    async def clear_nonimage(self, ctx, amount: int = 10):
        """Clear messages without attachments"""
        def check(message):
            if message.embeds:
                data = message.embeds[0]
                if data.type == 'image':
                    return False
                if data.type == 'rich':
                    return False

            if message.attachments:
                return False
            return True

        messages = await ctx.channel.history(limit=amount+1).filter(check).flatten()

        await ctx.channel.delete_messages(messages)
        await ctx.send(f'Deleted {len(messages)} messages', delete_after=4)

    @clear.command(name="bot")
    @commands.has_permissions(manage_messages=True)
    async def clear_bot(self, ctx, amount: int = 10):
        """Clear bot messages"""
        messages = await ctx.channel.history(limit=amount+1).filter(lambda m: m.author.bot).flatten()

        await ctx.channel.delete_messages(messages)
        await ctx.send(f'Deleted {len(messages)} messages', delete_after=4)

    @commands.command()
    @commands.has_role('Staff')
    async def kiarahistory(self, ctx, member: IDConverter, limit: int = 15):
        """Get someone's chat history with Kiara.
        Defaults to max 15 messages"""
        try:
            member = self.bot.get_user(member) or await self.bot.get_user_info(member)
        except discord.NotFound:
            return await ctx.send("Unknown user")
        pag = commands.Paginator('```diff')

        async for m in member.history(reverse=True, limit=limit):
            content = ''.join(m.content.replace('`', '\`').splitlines())
            pag.add_line(
                f"{'-' if m.author.id == self.bot.user.id else '+'} {m.created_at.strftime('%d-%b-%Y %H:%M:%S')} "
                f"{m.author.name}: {content}")
        for page in pag.pages:
            await ctx.send(page)

    async def warn_user(self, user_id, issuer_id, reason):
        qry = "INSERT INTO warns (date, user_id, issuer, reason) VALUES (%s, %s, %s, %s)"
        await self.bot.db.execute(qry, (datetime.datetime.utcnow(), user_id, issuer_id, reason))

        warns = await self.get_recent_warns(user_id)
        all_warns = await self.get_all_warns(user_id)

        em = discord.Embed(title=f"{self.bot.get_user(user_id)} (ID: {user_id})")
        em.add_field(name="Warned by", value=self.bot.get_user(issuer_id))
        em.add_field(name="Reason", value=reason)

        if len(warns) >= 3:
            em.colour = 0xbb2124
        elif len(warns) >= 2:
            em.colour = 0xf0ad4e
        else:
            em.colour = 0xe6f266

        em.set_footer(text=f"{len(warns)} recent warning(s), {len(all_warns)} total")
        em.timestamp = datetime.datetime.utcnow()

        warn_channel = self.bot.get_guild(215424443005009920).get_channel(488632843711414282)
        await warn_channel.send(embed=em)

    @commands.command()
    @commands.has_role('Staff')
    async def warn(self, ctx, member: discord.Member, *, reason):
        """Warn a user.
        The warning will show up in #s-warns for mods to see.

        A warning is considered "recent" if it hasn't been at least 30 days since the warning.
        """
        await self.warn_user(member.id, ctx.author.id, reason)
        await ctx.message.add_reaction('Yes:393865045005697034')

    @commands.command()
    @commands.has_role('Staff')
    async def warns(self, ctx, member: IDConverter):
        """Show all warnings of a user, no matter how recent it is."""
        warns = await self.get_all_warns(member)
        member = await self.bot.get_user_info(member)

        em = discord.Embed(title=f"Warns from {member} (ID: {member.id})")
        for warning in warns[:25]:
            issuer = self.bot.get_user(warning['issuer']) or warning['issuer']
            em.add_field(name=f"Warn by {issuer} - {warning['date']}", value=warning['reason'])

        em.timestamp = datetime.datetime.utcnow()

        await ctx.send(embed=em)

    @commands.command(aliases=['roleping', 'enableping'])
    @commands.guild_only()
    @commands.has_role('Staff')
    async def toggleping(self, ctx, *, role: discord.Role):
        ping_roles=[347689132908085248, 533931119695888384]

        if role.id not in ping_roles:
            await ctx.send("No role found to toggle. Either the role name was incorrect or you need to request this role to be added!")
        else:
            await role.edit(mentionable=True, reason=f"{ctx.author}: making @{role.name} Pingable")
            await ctx.send(f"{role.name} ping mentionable till pinged, or 60 seconds pass")
            try:
                await self.bot.wait_for('message', check=lambda m: role in m.role_mentions, timeout=60)
            except asyncio.TimeoutError:
                await ctx.send("Role wasn't pinged for 60 seconds, so turing it off.")
            await role.edit(mentionable=False, reason=f"{ctx.author}: Making @{role.name} Unpingable")
            await ctx.send("Requested role no longer pingable.")

    @commands.command()
    @commands.guild_only()
    @commands.has_role('Staff')
    async def verify(self, ctx, *, member: discord.Member):
        await member.add_roles(discord.utils.get(ctx.guild.roles, id=373461042208178177))
        await ctx.send(f"User {member} has been verified")

def setup(bot):
    bot.add_cog(Moderation(bot))
