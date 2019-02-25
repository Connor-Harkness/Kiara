import asyncio
import datetime
import re

import discord
from discord.ext import commands

INVITE_REGEX = "(https?:\/\/)?(www\.)?(discord\.(gg|io|me|li)|discordapp\.com\/invite)\/.+"
LINK_REGEX = "(https?:\/\/[^\s<]+[^<.,:;\"')\]\s])"


class Automod(commands.Cog):
    """Kiara attempting to detect cunts and deal with them"""

    def __init__(self, bot):
        self.bot = bot
        self.inviteregex = re.compile(INVITE_REGEX)
        self.linkregex = re.compile(LINK_REGEX)

        self.moderation = bot.get_cog("Moderation")

        self.bg_task = bot.loop.create_task(self.update_user_log())

    def __unload(self):
        self.bg_task.cancel()

    async def update_user_log(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(497088811486937098)
        try:
            while not self.bot.is_closed():
                await channel.edit(name=f"✨Users: {len(channel.guild.members)}")
                await asyncio.sleep(3600)
        except Exception as e:
            print(e)

    async def invite_check(self, msg):
        # Check if message content contains an invite url
        invite = self.inviteregex.search(msg.content)
        if invite:
            # Ignore staff though
            if discord.utils.get(msg.author.roles, name="Staff") is None:
                await msg.delete()
                await msg.channel.send(f"{msg.author.mention} you sent an invite link, I deleted it for you.")
                return True

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild:
            return

        # Ignore kiara
        if msg.author.id == self.bot.user.id:
            return

        # Waifu submissions
        if msg.channel.id in [467174606122516480]:
            if not msg.attachments and not self.linkregex.search(msg.content):
                await msg.delete()
                warnmsg = "Please post the image of the character you wish to submit."
                try:
                    await msg.author.send(warnmsg)
                except discord.Forbidden:
                    await msg.channel.send(warnmsg, delete_after=6)
            else:
                for r in ['Yes:393865045005697034', 'No:393864998365167627']:
                    await msg.add_reaction(r)

        # Tributes
        if msg.channel.id == 529036544435027969:
            if discord.utils.get(msg.author.roles, name="Tributes") is None:
                await msg.author.add_roles(discord.utils.get(msg.guild.roles, name="Tributes"))

        # Ignore staff for everything else
        if discord.utils.get(msg.author.roles, id=293008190843387911):
            return

        # Invite filter
        if await self.invite_check(msg):
            await self.moderation.mute_user_id(msg.author.id, 10, "Auto mute")
            await self.moderation.warn_user(msg.author.id, self.bot.user.id, "Auto-mute: Sent an invite link")

        # Mention spam filter
        if len(msg.mentions) >= 10:
            await self.moderation.mute_user_id(msg.author.id, 10, "Auto mute")
            await self.moderation.warn_user(msg.author.id, self.bot.user.id, "Auto-mute: Possible spam (Mentions)")

        # Message filter in NSFW channels
        exempt_channels = [447050781544153089, 274230637538574337, 399017427897155604, 487134988031098881, 534240765526933514]  # comments, links, fiction, non-fiction, sauce
        if msg.channel.category_id == 360707378275942400 and msg.channel.id not in exempt_channels:
            if not msg.attachments and not self.linkregex.search(msg.content):
                await msg.delete()
                warnmsg = "Please refrain from talking in the NSFW image channels, " \
                          "you can leave any comments in <#447050781544153089>."
                try:
                    await msg.author.send(warnmsg)
                except discord.Forbidden:
                    await msg.channel.send(warnmsg, delete_after=6)
                await self.moderation.warn_user(msg.author.id, self.bot.user.id, "Talking in NSFW image channels")
                if len(await self.moderation.get_recent_warns(msg.author.id)) >= 3:
                    await self.moderation.mute_user_id(msg.author.id, 60, "Auto mute")

        # Message filter in waifu image channels
        exempt_channels = [478166208219316224, 467174606122516480, 467174534794182657]  # faq, submissions, discussion
        if msg.channel.category_id == 467658509224378388 and msg.channel.id not in exempt_channels:
            if not msg.attachments and not self.linkregex.search(msg.content):
                await msg.delete()
                warnmsg = "Please refrain from talking in the waifu image channels, " \
                          "you can leave any comments in <#467174534794182657>."
                try:
                    await msg.author.send(warnmsg)
                except discord.Forbidden:
                    await msg.channel.send(warnmsg, delete_after=6)
                await self.moderation.warn_user(msg.author.id, self.bot.user.id, "Talking in waifu image channels")
                if len(await self.moderation.get_recent_warns(msg.author.id)) >= 3:
                    await self.moderation.mute_user_id(msg.author.id, 60, "Auto mute")

        # Spam filter
        exempt_categories = [360699183851896833, 360707378275942400, 467658509224378388]  # Media, NSFW, Waifu
        if msg.channel.category_id in exempt_categories:
            return

        exempt_roles = [326644349607739393, 457213160504426496]  # Bot, Faithful
        if discord.utils.find(lambda r: r.id in exempt_roles, msg.author.roles):
            return
        
        if len(list(filter(lambda m: m.author.id == msg.author.id and m.created_at > datetime.datetime.now() - datetime.timedelta(seconds=2), self.bot._connection._messages))) >= 5:
            await self.moderation.mute_user_id(msg.author.id, 5, "Auto mute")
            await self.moderation.warn_user(msg.author.id, self.bot.user.id, "Auto-mute: Possible spam")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        await self.invite_check(after)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.created_at > datetime.datetime.now() - datetime.timedelta(days=1):
            await member.send("Your account has been kicked for being under a day old to prevent malicious users joining the server.")
            await member.kick(reason="Auto-kick for suspicious account")
            return

        # Mute re-joining users that are supposed to be muted
        qry = 'SELECT expires FROM timers WHERE event="unmute" AND json_extract(data, "$[1]") = %s'
        if await self.bot.db.fetchone(qry, (member.id,)):
            await member.add_roles(discord.utils.get(member.guild.roles, id=348331525479071745), reason="Re-join mute")


def setup(bot):
    bot.add_cog(Automod(bot))
