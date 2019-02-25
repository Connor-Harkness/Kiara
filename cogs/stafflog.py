import asyncio
import datetime

import discord
from discord.ext import commands

GUILD_ID = 215424443005009920
LOG_CHANNEL = 364983647087886336

async def poll_audit_log(guild, action, after, *, poll=1, **kwargs):
    for i in range(poll):
        log = await guild.audit_logs(action=action, after=after).get(**kwargs)
        if log:
            return log
        await asyncio.sleep(1)
    return None


class Stafflog(commands.Cog):
    """Logging the bans~"""

    def __init__(self, bot):
        self.bot = bot

    async def make_case(self, user, action, reason=None, responsible=None):
        date = datetime.datetime.utcnow()
        ch = self.bot.get_channel(LOG_CHANNEL)
        msg = await ch.send('Case')
        _, c_id = await self.bot.db.execute(f'INSERT INTO stafflog (message_id, user_id, action, reason, date) '
                                            f'VALUES (%s,%s,%s,%s,%s)', (msg.id, user.id, action, reason, date))

        if reason is None:
            reason = f'`~reason {c_id} [reason]`'
        fmt = f"User: {user} ({user.id})\nAction: {action}\nReason: {reason}"
        em = discord.Embed(description=fmt)
        em.timestamp = date
        em.set_footer(text=f'{responsible} | Case #{c_id}')

        await msg.edit(content='', embed=em)

    @commands.command()
    @commands.has_role('Staff')
    async def reason(self, ctx, case_id: int, *, reason):
        m_id, = await self.bot.db.fetchone(
            f'SELECT message_id FROM stafflog WHERE id={case_id}')
        msg = await self.bot.get_channel(LOG_CHANNEL).get_message(m_id)
        em = msg.embeds[0].to_dict()
        # Keep the old info, so the username doesn't change in case it's changed.
        em['description'] = '\n'.join(em['description'].split('\n')[:2]) + f"\nReason: {ctx.author}: {reason}"
        await msg.edit(embed=discord.Embed.from_data(em))
        await ctx.message.delete()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id != GUILD_ID:
            return
        await asyncio.sleep(2)
        log = await member.guild.audit_logs(action=discord.AuditLogAction.kick).get(target__id=member.id)
        if log:
            if 'Auto-kick' in log.reason:
                return
            await self.make_case(member, 'Kick', log.reason, log.user)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, member):
        if guild.id != GUILD_ID:
            return
        
        time = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
        log = await poll_audit_log(guild, discord.AuditLogAction.ban, time, poll=5, target__id=member.id)
        if log:
            await self.make_case(member, 'Ban', log.reason, log.user)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, member):
        if guild.id != GUILD_ID:
            return
        await asyncio.sleep(2)
        log = await guild.audit_logs(action=discord.AuditLogAction.unban).get(target__id=member.id)
        if log:
            await self.make_case(member, 'Unban', log.reason, log.user)

def setup(bot):
    bot.add_cog(Stafflog(bot))
